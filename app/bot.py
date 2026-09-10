# bot.py
import asyncio
import logging
import os
import re
import socket
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ChatType, ParseMode
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, Message
from pydantic import ValidationError

from app import media, messages, preview
from app.config import settings

from .models import URLMessage
from .url_processing import DownloadResult, process_url_request

logger = logging.getLogger(__name__)


# #UFB-0036
def _build_session() -> AiohttpSession | None:
    """A session pointed at a self-hosted local Bot API server when
    TELEGRAM_API_URL is configured, else None (aiogram's default cloud-API
    session)."""
    if not settings.TELEGRAM_API_URL:
        return None
    return AiohttpSession(
        api=TelegramAPIServer.from_base(settings.TELEGRAM_API_URL, is_local=True)
    )


# #UFB-0036
def _make_bot(use_local: bool) -> Bot:
    """A fresh Bot instance on the requested backend. A Telegram bot token
    is logged into exactly one Bot API backend at a time — built once in
    start_polling(), never rebuilt afterward (see its docstring)."""
    return Bot(
        token=settings.BOT_TOKEN, session=_build_session() if use_local else None
    )


bot = _make_bot(use_local=bool(settings.TELEGRAM_API_URL))
dp = Dispatcher()
_using_local_api = bool(settings.TELEGRAM_API_URL)


# #UFB-0034, #UFB-0036
def is_telegram_api_reachable(timeout: float = 1.0) -> bool | None:
    """Whether the local Bot API server configured via TELEGRAM_API_URL is
    accepting TCP connections. None when TELEGRAM_API_URL is unset — there
    is nothing to check, and that must not read as either healthy or
    unhealthy. A plain TCP connect (not an HTTP request) since the server
    has no unauthenticated route that returns 2xx — every real endpoint
    404s/401s without a valid bot token, which would make an HTTP-status
    check falsely report "down" for a server that is actually up."""
    if not settings.TELEGRAM_API_URL:
        return None
    parsed = urlparse(settings.TELEGRAM_API_URL)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((parsed.hostname, port), timeout=timeout):
            return True
    except OSError:
        return False


GROUP_CHAT_TYPES = [ChatType.GROUP, ChatType.SUPERGROUP]

polling_task: asyncio.Task | None = None


# #UFB-0020
def _on_polling_done(task: asyncio.Task) -> None:
    if task.cancelled():
        logger.info("Bot polling cancelled")
        return
    exc = task.exception()
    if exc is not None:
        logger.error("Bot polling stopped unexpectedly", exc_info=exc)


# #UFB-0020, #UFB-0036
def start_polling() -> None:
    """Start the bot's polling loop as an observable background task, on
    the local Bot API server if TELEGRAM_API_URL is configured and
    reachable right now, else the cloud API.

    No in-process fallback/recovery runs after this: aiogram's own
    `getUpdates` loop already retries with backoff against whichever
    backend was picked here and self-heals once it's reachable again, and
    moving the bot *back* onto the cloud API mid-run isn't possible without
    an explicit `logOut` call against the local server first (see
    docs/telegram-bot-api-setup.md) — a dead local server can't answer
    that, so an earlier attempt at an automatic swap was removed."""
    global bot, polling_task, _using_local_api
    _using_local_api = (
        bool(settings.TELEGRAM_API_URL) and is_telegram_api_reachable() is True
    )
    bot = _make_bot(_using_local_api)
    polling_task = asyncio.create_task(dp.start_polling(bot))
    polling_task.add_done_callback(_on_polling_done)


# #UFB-0020
async def stop_polling() -> None:
    """Cancel the polling task (if running) and close its resources."""
    if polling_task is not None:
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
    await dp.storage.close()
    await bot.session.close()


# #UFB-0020, #UFB-0034
def is_polling_alive() -> bool:
    return polling_task is not None and not polling_task.done()


# #UFB-0001
@dp.message(CommandStart())
async def start(message: Message):
    await message.reply(messages.start(), parse_mode=ParseMode.HTML)


# #UFB-0036
async def _fits_native_send(size_mb: float) -> bool:
    """Whether a file this size should be attempted as a native video
    reply. A Telegram bot token is logged into exactly one Bot API backend
    at a time (cloud xor a self-hosted local one — the local server
    rejects requests with "Unauthorized" until the bot logs out of the
    cloud API, and vice versa), so this never picks between two backends
    per message; it only decides whether the one backend currently active
    should be trusted with a file this size:
    - at or under CLOUD_SEND_VIDEO_MAX_MB: always — small enough that
      either backend handles it.
    - up to LOCAL_SEND_VIDEO_MAX_MB: only when a local server is
      configured (TELEGRAM_API_URL) AND currently reachable — otherwise
      whatever backend is active (cloud, or a dead local server) has no
      business being handed a file this size.
    - above LOCAL_SEND_VIDEO_MAX_MB: never."""
    if size_mb <= settings.CLOUD_SEND_VIDEO_MAX_MB:
        return True
    if size_mb > settings.LOCAL_SEND_VIDEO_MAX_MB:
        return False
    return bool(await asyncio.to_thread(is_telegram_api_reachable))


# #UFB-0036
async def _reply_with_video(message: Message, media_path: str, caption: str) -> bool:
    """Best-effort native video reply for `media_path`. Returns True once
    sent; any failure (probe error, send error) returns False so the
    caller falls back to a plain text reply — this must never be a new
    way for a reply to fail outright.

    When the active session is the local Bot API server (`_using_local_api`),
    `video` is tried first as a plain path string instead of `FSInputFile` —
    aiogram hands a bare string straight through to the local server's
    `sendVideo` as a file path on its own disk, instead of reading and
    uploading the bytes itself. That only resolves to the right file
    because `app` and `telegram-bot-api` share the `cache` volume at the
    same mount path (see docker-compose.yml). If that attempt fails for
    any reason (observed live: `Bad Request: invalid file HTTP URL
    specified: URL host is empty` — root cause undiagnosed, the local
    server sometimes doesn't take the path-based branch for an otherwise
    valid, readable file), it's retried once as a real upload
    (`FSInputFile`) before giving up. `thumbnail` is always `FSInputFile`,
    on both backends and both attempts — aiogram's `SendVideo.thumbnail`
    field is typed strictly as `InputFile`, unlike `video`
    (`str | InputFile`), so a bare path there fails pydantic validation
    regardless of backend; the thumbnail is small (≤200 KB) anyway, so
    always uploading it costs nothing."""
    info = media.probe(media_path) or {}
    thumb_path = preview.preview_path(os.path.basename(media_path))
    thumbnail = FSInputFile(thumb_path) if os.path.exists(thumb_path) else None

    videos = [media_path] if _using_local_api else []
    videos.append(FSInputFile(media_path))

    last_error: Exception | None = None
    for video in videos:
        try:
            await message.reply_video(
                video,
                caption=caption,
                parse_mode=ParseMode.HTML,
                supports_streaming=True,
                width=info.get("width"),
                height=info.get("height"),
                duration=info.get("duration"),
                thumbnail=thumbnail,
            )
            return True
        except Exception as e:
            last_error = e

    logger.warning(f"Failed to send native video for {media_path}: {last_error}")
    return False


# #UFB-0014, #UFB-0036
async def _deliver_result(message: Message, result: str | DownloadResult) -> None:
    """Reply with `result`: a native video when its media_path is small
    enough to attempt and the send succeeds; otherwise plain text — a
    "too large to upload" notice above LOCAL_SEND_VIDEO_MAX_MB, or the
    reply text as-is for everything else (no media, send declined, or send
    failed). The reply text always carries the Download/Source links, so
    every outcome leaves the user with a way to get the file."""
    text = result.text if isinstance(result, DownloadResult) else result
    media_path = result.media_path if isinstance(result, DownloadResult) else None

    if media_path:
        try:
            size_mb = os.path.getsize(media_path) / (1024 * 1024)
        except OSError:
            size_mb = None

        if size_mb is not None and size_mb > settings.LOCAL_SEND_VIDEO_MAX_MB:
            await message.reply(messages.too_large(text), parse_mode=ParseMode.HTML)
            return

        if size_mb is not None and await _fits_native_send(size_mb):
            if await _reply_with_video(message, media_path, text):
                return

    await message.reply(text, parse_mode=ParseMode.HTML)


# #UFB-0002, #UFB-0003, #UFB-0004, #UFB-0005, #UFB-0006, #UFB-0014
@dp.message(F.text)
async def handle_message(message: Message):
    """
    Process and respond to URLs extracted from incoming messages.

    In group chats, if the message is a reply to the bot's own message, replies with an emoji and returns. Otherwise, extracts URLs from the message text. If no URLs are found, silently returns in group chats or replies with an error message in private chats. For each valid URL, processes it and sends the processing result as a reply. Logs validation errors and reports them to the user.
    """
    if message.chat.type in GROUP_CHAT_TYPES and message.reply_to_message:
        if message.reply_to_message.from_user.id == bot.id:
            await message.reply(
                messages.shrug(),
                parse_mode=ParseMode.HTML,
            )
            return

    url_pattern = r"(https?://\S+)"
    urls = [
        url.rstrip(".,;:!?)]}'\"")
        for url in re.findall(url_pattern, message.text.strip())
    ]

    if not urls:
        if message.chat.type in GROUP_CHAT_TYPES:
            return
        else:
            await message.reply(messages.no_url_prompt(), parse_mode=ParseMode.HTML)
            return

    for url in urls:
        try:
            url_message = URLMessage(
                url=url, is_group_chat=message.chat.type in GROUP_CHAT_TYPES
            )
            result = await process_url_request(
                url_message.url, url_message.is_group_chat
            )
            if result is not None:
                await _deliver_result(message, result)

        except ValidationError as e:
            logger.warning(f"Validation error for URL: {url} - {e}")
            await message.reply(messages.invalid_url(), parse_mode=ParseMode.HTML)
