# bot.py
import asyncio
import logging
import os
import re
import socket
import time
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ChatType, ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InputMediaPhoto,
    Message,
    ReplyParameters,
)
from pydantic import ValidationError

from app import duplicates, media, messages, metrics, preview, reports, stats
from app.config import settings

from .models import URLMessage
from .url_processing import BlockedUrlError, DownloadResult, process_url_request

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


# #UFB-0020, #UFB-0036, #BUG-0075
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
    global polling_task
    polling_task = asyncio.create_task(_pick_backend_and_poll())
    polling_task.add_done_callback(_on_polling_done)


# #UFB-0020, #UFB-0036, #BUG-0075
async def _pick_backend_and_poll() -> None:
    """Pick the backend (the blocking reachability probe runs off the
    event loop via asyncio.to_thread, like every other call site), then
    poll on it."""
    global bot, _using_local_api
    _using_local_api = (
        bool(settings.TELEGRAM_API_URL)
        and await asyncio.to_thread(is_telegram_api_reachable) is True
    )
    bot = _make_bot(_using_local_api)
    await dp.start_polling(bot)


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


# #UFB-0049: admin-only; anyone else (and an empty admin list) is ignored
# silently, in every chat type, so the command is not discoverable.
@dp.message(Command("stats"))
async def stats_command(message: Message):
    if not stats.is_admin(message.chat.id, settings.admin_chat_ids):
        return
    await message.reply(
        stats.format_stats(metrics.snapshot()), parse_mode=ParseMode.HTML
    )


# #UFB-0051: the "Report broken link" button on failure replies.
@dp.callback_query(F.data.startswith("rb:"))
async def report_broken_link(query: CallbackQuery):
    token = reports.parse_callback(query.data)
    kind = reports.submit(query.from_user.id, token) if token else "expired"
    await query.answer(messages.report(kind))


# #UFB-0055: Telegram clears a chat action after ~5 s, so refresh sooner.
CHAT_ACTION_INTERVAL_SECONDS = 4.0
# The first send waits this long, so an instant (cache-hit) reply shows nothing.
CHAT_ACTION_START_DELAY_SECONDS = 0.5


# #UFB-0055
class ChatActionIndicator:
    """Keeps a Telegram chat action ("typing", "upload_video") alive in a
    background task until `stop()`. `send(action)` is an async callable;
    a failing send is logged and never propagates. Change `action` while
    running to switch what is shown."""

    def __init__(self, send, interval: float | None = None, delay: float | None = None):
        self._send = send
        self._interval = interval
        self._delay = delay
        self._task: asyncio.Task | None = None
        self.action = "typing"

    async def _run(self) -> None:
        interval = self._interval
        if interval is None:
            interval = CHAT_ACTION_INTERVAL_SECONDS
        delay = self._delay
        if delay is None:
            delay = CHAT_ACTION_START_DELAY_SECONDS
        await asyncio.sleep(delay)
        while True:
            try:
                await self._send(self.action)
            except Exception as e:
                logger.debug(f"Failed to send chat action {self.action}: {e}")
            await asyncio.sleep(interval)

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


# #UFB-0036, #BUG-0070
async def _fits_native_send(size_mb: float) -> bool:
    """Whether a file this size should be attempted as a native video
    reply. Gating is by size tier and reachability only; it does not look
    at which backend is currently polling (deliberate, see UFB-0036):
    - at or under CLOUD_SEND_VIDEO_MAX_MB: always.
    - up to LOCAL_SEND_VIDEO_MAX_MB: only when a local server is
      configured (TELEGRAM_API_URL) AND currently reachable
      (`is_telegram_api_reachable`). The bot may still be polling on the
      cloud API after the local server recovers (no in-process backend
      swap); the send then fails and falls back to the text reply.
    - above LOCAL_SEND_VIDEO_MAX_MB: never."""
    if size_mb <= settings.CLOUD_SEND_VIDEO_MAX_MB:
        return True
    if size_mb > settings.LOCAL_SEND_VIDEO_MAX_MB:
        return False
    return bool(await asyncio.to_thread(is_telegram_api_reachable))


# #UFB-0036, #UFB-0055
async def _reply_with_video(
    message: Message,
    media_path: str,
    caption: str,
    indicator: ChatActionIndicator | None = None,
) -> bool:
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
    # #BUG-0006: ffprobe runs off the event loop
    info = await asyncio.to_thread(media.probe, media_path) or {}
    thumb_path = preview.preview_path(os.path.basename(media_path))
    thumbnail = FSInputFile(thumb_path) if os.path.exists(thumb_path) else None

    videos = [media_path] if _using_local_api else []
    videos.append(FSInputFile(media_path))

    if indicator:
        indicator.action = "upload_video"  # #UFB-0055

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


# Telegram's sendMediaGroup limit.
_MEDIA_GROUP_MAX = 10


# #UFB-0039
async def _reply_with_gallery(message: Message, result: DownloadResult) -> bool:
    """Best-effort photo-album reply (10 photos per group, caption on the
    first photo) followed by the post's audio, if any. Returns False only
    when the album itself could not be sent, so the caller falls back to
    plain text; a failed audio send is logged and the gallery still counts
    as delivered."""
    paths = result.image_paths
    try:
        for start in range(0, len(paths), _MEDIA_GROUP_MAX):
            group = [
                InputMediaPhoto(
                    media=FSInputFile(path),
                    caption=result.text if start == 0 and i == 0 else None,
                    parse_mode=ParseMode.HTML,
                )
                for i, path in enumerate(paths[start : start + _MEDIA_GROUP_MAX])
            ]
            if len(group) == 1:
                await message.reply_photo(
                    group[0].media, caption=group[0].caption, parse_mode=ParseMode.HTML
                )
            else:
                await message.reply_media_group(group)
    except Exception as e:
        logger.warning(f"Failed to send gallery for {paths[0]}: {e}")
        return False

    if result.media_path:
        try:
            size_mb = os.path.getsize(result.media_path) / (1024 * 1024)
            if await _fits_native_send(size_mb):
                await message.reply_audio(FSInputFile(result.media_path))
        except Exception as e:
            logger.warning(f"Failed to send gallery audio {result.media_path}: {e}")
    return True


# #UFB-0014, #UFB-0036, #UFB-0039, #UFB-0045, #UFB-0055
async def _deliver_result(
    message: Message,
    result: str | DownloadResult,
    indicator: ChatActionIndicator | None = None,
) -> None:
    """Reply with `result`: a native video when its media_path is small
    enough to attempt and the send succeeds; otherwise plain text — a
    "too large to upload" notice above LOCAL_SEND_VIDEO_MAX_MB, or the
    reply text as-is for everything else (no media, send declined, or send
    failed). The reply text always carries the Download/Source links, so
    every outcome leaves the user with a way to get the file. The reply
    kind and delivery latency are recorded (#UFB-0045)."""
    start = time.perf_counter()
    kind = "text_link"
    try:
        kind = await _send_reply(message, result, indicator)
        metrics.record_reply_kind(kind)  # only replies that went out
    finally:
        metrics.observe_reply(kind, time.perf_counter() - start)


# #UFB-0014, #UFB-0036, #UFB-0039, #UFB-0045, #UFB-0051, #UFB-0055
async def _send_reply(
    message: Message,
    result: str | DownloadResult,
    indicator: ChatActionIndicator | None = None,
) -> str:
    """Send the reply and return its kind: `native_video`, `gallery` or
    `text_link`."""
    text = result.text if isinstance(result, DownloadResult) else result
    media_path = result.media_path if isinstance(result, DownloadResult) else None

    if isinstance(result, DownloadResult) and result.image_paths:
        if await _reply_with_gallery(message, result):
            return "gallery"
        await message.reply(text, parse_mode=ParseMode.HTML)
        return "text_link"

    if media_path:
        try:
            size_mb = os.path.getsize(media_path) / (1024 * 1024)
        except OSError:
            size_mb = None

        if size_mb is not None and size_mb > settings.LOCAL_SEND_VIDEO_MAX_MB:
            await message.reply(messages.too_large(text), parse_mode=ParseMode.HTML)
            return "text_link"

        if size_mb is not None and await _fits_native_send(size_mb):
            if await _reply_with_video(message, media_path, text, indicator):
                return "native_video"

    markup = reports.keyboard_for(result)  # #UFB-0051: failure replies only
    extra = {"reply_markup": markup} if markup else {}
    await message.reply(text, parse_mode=ParseMode.HTML, **extra)
    return "text_link"


# #UFB-0050
async def _answer_duplicate(message: Message, url: str) -> bool:
    """True when `url` was already answered in this chat within the window
    and the short pointer reply went out. A pointer that fails (earlier
    message deleted) drops the entry and returns False: reply normally."""
    earlier_id = duplicates.lookup(message.chat.id, url)
    if earlier_id is None:
        return False
    try:
        await message.answer(
            messages.duplicate_link(),
            parse_mode=ParseMode.HTML,
            reply_parameters=ReplyParameters(
                message_id=earlier_id, allow_sending_without_reply=False
            ),
        )
        return True
    except Exception as e:
        logger.info(f"Earlier reply {earlier_id} unavailable for {url}: {e}")
        duplicates.forget(message.chat.id, url)
        return False


# #UFB-0002, #UFB-0003, #UFB-0004, #UFB-0005, #UFB-0006, #UFB-0014, #UFB-0050, #UFB-0055, #BUG-0068
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
        indicator = ChatActionIndicator(
            lambda action: message.bot.send_chat_action(message.chat.id, action)
        )
        try:
            url_message = URLMessage(
                url=url, is_group_chat=message.chat.type in GROUP_CHAT_TYPES
            )
            if await _answer_duplicate(message, url):  # #UFB-0050
                continue
            recorder = duplicates.ReplyRecorder(message)  # #UFB-0050
            # #UFB-0055: a group link starts it only once a download is
            # attempted (process_url_request's on_download), so quiet links
            # show nothing; a private link shows it from validation on.
            if not url_message.is_group_chat:
                indicator.start()
            result = await process_url_request(
                url_message.url,
                url_message.is_group_chat,
                on_download=indicator.start,
            )
            if result is not None:
                await _deliver_result(recorder, result, indicator)
                if recorder.first_id is not None:  # #UFB-0050
                    duplicates.record(message.chat.id, url, recorder.first_id)

        except ValidationError as e:
            logger.warning(f"Validation error for URL: {url} - {e}")
            await message.reply(messages.invalid_url(), parse_mode=ParseMode.HTML)
        except BlockedUrlError as e:
            # #BUG-0012: private/loopback target; invalid in DMs, quiet in groups.
            logger.warning(f"Blocked URL: {url} - {e}")
            if message.chat.type not in GROUP_CHAT_TYPES:
                await message.reply(messages.invalid_url(), parse_mode=ParseMode.HTML)
        except Exception:
            # A failing reply (or delivery) for one URL must never escape
            # the handler (#BUG-0068); log it and move on to the next URL.
            logger.exception(f"Failed to deliver result for URL: {url}")
        finally:
            await indicator.stop()
