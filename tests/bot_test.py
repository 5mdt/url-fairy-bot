# bot_test.py

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.enums import ParseMode

from app import bot as bot_module
from app import messages, preview
from app.bot import (
    _build_session,
    _fits_native_send,
    _reply_with_video,
    dp,
    handle_message,
    is_telegram_api_reachable,
    start,
)
from app.config import settings
from app.url_processing import DownloadResult


def make_message(text, chat_type="private", reply_to_message=None):
    message = MagicMock()
    message.text = text
    message.chat.type = chat_type
    message.reply_to_message = reply_to_message
    message.reply = AsyncMock()
    return message


# --- /start greeting (BUG-0004) ---


@pytest.mark.asyncio
async def test_start_in_private_chat_gets_greeting():
    message = make_message("/start", chat_type="private")
    await start(message)
    message.reply.assert_awaited_once_with(
        messages.start(), parse_mode=ParseMode.HTML
    )


@pytest.mark.asyncio
async def test_start_in_group_chat_gets_greeting():
    message = make_message("/start", chat_type="group")
    await start(message)
    message.reply.assert_awaited_once_with(
        messages.start(), parse_mode=ParseMode.HTML
    )


def test_start_is_registered_before_the_catch_all_text_handler():
    """
    Regression test for BUG-0004: `start` must be registered ahead of
    `handle_message` (`@dp.message(F.text)`), or `/start` — which is valid
    text — gets routed to the catch-all handler first, since aiogram
    dispatches to the first registered handler whose filters match.
    """
    callbacks = [h.callback for h in dp.message.handlers]
    assert start in callbacks
    assert handle_message in callbacks
    assert callbacks.index(start) < callbacks.index(handle_message)


# --- no URL in the message ---


@pytest.mark.asyncio
async def test_private_chat_no_url_gets_error_reply():
    message = make_message("just some text", chat_type="private")
    await handle_message(message)
    message.reply.assert_awaited_once_with(
        messages.no_url_prompt(), parse_mode=ParseMode.HTML
    )


@pytest.mark.asyncio
async def test_group_chat_no_url_is_silent():
    message = make_message("just some text", chat_type="group")
    await handle_message(message)
    message.reply.assert_not_awaited()


# --- process_url_request returns None ---


@pytest.mark.asyncio
async def test_group_chat_none_result_is_silent():
    message = make_message("https://example.com/x", chat_type="group")
    with patch("app.bot.process_url_request", new=AsyncMock(return_value=None)):
        await handle_message(message)
    message.reply.assert_not_awaited()


# --- process_url_request returns a string ---


@pytest.mark.asyncio
async def test_private_chat_result_is_replied_with_html():
    message = make_message("https://example.com/x", chat_type="private")
    with patch(
        "app.bot.process_url_request", new=AsyncMock(return_value="the reply text")
    ):
        await handle_message(message)
    message.reply.assert_awaited_once_with(
        "the reply text", parse_mode=ParseMode.HTML
    )


# --- multiple URLs in one message ---


@pytest.mark.asyncio
async def test_multi_url_message_replies_once_per_url():
    text = "https://example.com/a and https://example.org/b"
    message = make_message(text, chat_type="private")
    with patch(
        "app.bot.process_url_request", new=AsyncMock(return_value="reply")
    ) as mock_process:
        await handle_message(message)
    assert mock_process.await_count == 2
    assert message.reply.await_count == 2


# --- reply-to-bot easter egg ---


@pytest.mark.asyncio
async def test_reply_to_bot_in_group_sends_shrug():
    from app.bot import bot

    reply_to = MagicMock()
    reply_to.from_user.id = bot.id
    message = make_message("anything", chat_type="group", reply_to_message=reply_to)

    await handle_message(message)

    message.reply.assert_awaited_once()
    args, kwargs = message.reply.await_args
    assert kwargs.get("parse_mode") == ParseMode.HTML


@pytest.mark.asyncio
async def test_reply_to_bot_shrug_text_is_well_formed():
    from app.bot import bot

    reply_to = MagicMock()
    reply_to.from_user.id = bot.id
    message = make_message("anything", chat_type="group", reply_to_message=reply_to)

    await handle_message(message)

    args, kwargs = message.reply.await_args
    assert args[0] == messages.shrug()
    assert args[0] == "¯\\_(ツ)_/¯"


@pytest.mark.asyncio
async def test_reply_to_other_user_in_group_is_not_the_easter_egg():
    reply_to = MagicMock()
    reply_to.from_user.id = 999999  # not the bot
    message = make_message(
        "https://example.com/x", chat_type="group", reply_to_message=reply_to
    )
    with patch("app.bot.process_url_request", new=AsyncMock(return_value="reply")):
        await handle_message(message)
    # Falls through to normal URL handling, not the shrug.
    message.reply.assert_awaited_once_with("reply", parse_mode=ParseMode.HTML)


# --- validation errors ---


@pytest.mark.asyncio
async def test_invalid_url_logs_and_replies():
    message = make_message("https:///", chat_type="private")
    await handle_message(message)
    message.reply.assert_awaited_once()
    args, kwargs = message.reply.await_args
    assert "Invalid URL provided" in args[0]
    assert kwargs.get("parse_mode") == ParseMode.HTML


@pytest.mark.asyncio
async def test_invalid_url_reply_is_user_friendly():
    message = make_message("https:///", chat_type="private")
    await handle_message(message)
    args, _ = message.reply.await_args
    assert "pydantic.dev" not in args[0]
    assert "\n" not in args[0]


# --- URL extraction edge cases ---


@pytest.mark.asyncio
async def test_url_extraction_trims_trailing_punctuation():
    message = make_message("Look at https://x.com/a).", chat_type="private")
    with patch(
        "app.bot.process_url_request", new=AsyncMock(return_value="reply")
    ) as mock_process:
        await handle_message(message)
    called_url = mock_process.await_args.args[0]
    assert str(called_url) == "https://x.com/a"


# --- UFB-0036: native video replies ---


@pytest.mark.asyncio
async def test_small_file_tries_video_reply():
    message = make_message("https://example.com/x", chat_type="private")
    result = DownloadResult(text="caption", media_path="/tmp/clip.mp4")
    with (
        patch("app.bot.process_url_request", new=AsyncMock(return_value=result)),
        patch("app.bot.os.path.getsize", return_value=1024),
        patch(
            "app.bot._reply_with_video", new=AsyncMock(return_value=True)
        ) as mock_video,
    ):
        await handle_message(message)
    mock_video.assert_awaited_once_with(message, "/tmp/clip.mp4", "caption")
    message.reply.assert_not_awaited()


@pytest.mark.asyncio
async def test_video_reply_failure_falls_back_to_text_reply():
    message = make_message("https://example.com/x", chat_type="private")
    result = DownloadResult(text="caption", media_path="/tmp/clip.mp4")
    with (
        patch("app.bot.process_url_request", new=AsyncMock(return_value=result)),
        patch("app.bot.os.path.getsize", return_value=1024),
        patch("app.bot._reply_with_video", new=AsyncMock(return_value=False)),
    ):
        await handle_message(message)
    message.reply.assert_awaited_once_with("caption", parse_mode=ParseMode.HTML)


@pytest.mark.asyncio
async def test_missing_media_file_falls_back_to_text_reply():
    """os.path.getsize raising (already swept, permission error) must not
    crash the reply — it just skips the native-send attempt."""
    message = make_message("https://example.com/x", chat_type="private")
    result = DownloadResult(text="caption", media_path="/no/such/clip.mp4")
    with patch("app.bot.process_url_request", new=AsyncMock(return_value=result)):
        await handle_message(message)
    message.reply.assert_awaited_once_with("caption", parse_mode=ParseMode.HTML)


@pytest.mark.asyncio
async def test_oversized_file_gets_too_large_notice_with_links(monkeypatch):
    monkeypatch.setattr(settings, "LOCAL_SEND_VIDEO_MAX_MB", 500)
    message = make_message("https://example.com/x", chat_type="private")
    links = messages.download_result(
        "https://example.test/watch/clip.html", "https://example.com/x"
    )
    result = DownloadResult(text=links, media_path="/tmp/clip.mp4")
    oversized_bytes = 501 * 1024 * 1024
    with (
        patch("app.bot.process_url_request", new=AsyncMock(return_value=result)),
        patch("app.bot.os.path.getsize", return_value=oversized_bytes),
        patch("app.bot._reply_with_video", new=AsyncMock()) as mock_video,
    ):
        await handle_message(message)
    mock_video.assert_not_awaited()
    message.reply.assert_awaited_once_with(
        messages.too_large(links),
        parse_mode=ParseMode.HTML,
    )


# --- UFB-0036: _fits_native_send tiering ---


@pytest.mark.asyncio
async def test_fits_native_send_true_at_or_under_cloud_threshold(monkeypatch):
    monkeypatch.setattr(settings, "CLOUD_SEND_VIDEO_MAX_MB", 10)
    assert await _fits_native_send(10) is True
    assert await _fits_native_send(1) is True


@pytest.mark.asyncio
async def test_fits_native_send_false_above_local_threshold(monkeypatch):
    monkeypatch.setattr(settings, "CLOUD_SEND_VIDEO_MAX_MB", 10)
    monkeypatch.setattr(settings, "LOCAL_SEND_VIDEO_MAX_MB", 500)
    assert await _fits_native_send(501) is False


@pytest.mark.asyncio
async def test_fits_native_send_mid_tier_requires_reachable_local_server(monkeypatch):
    monkeypatch.setattr(settings, "CLOUD_SEND_VIDEO_MAX_MB", 10)
    monkeypatch.setattr(settings, "LOCAL_SEND_VIDEO_MAX_MB", 500)

    with patch("app.bot.is_telegram_api_reachable", return_value=True):
        assert await _fits_native_send(100) is True
    with patch("app.bot.is_telegram_api_reachable", return_value=False):
        assert await _fits_native_send(100) is False
    with patch("app.bot.is_telegram_api_reachable", return_value=None):
        # TELEGRAM_API_URL unset — nothing to send this tier through.
        assert await _fits_native_send(100) is False


# --- UFB-0036: _reply_with_video send mechanics ---


@pytest.mark.asyncio
async def test_reply_with_video_sends_with_probe_info(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"0" * 1024)
    message = MagicMock()
    message.reply_video = AsyncMock()

    with patch(
        "app.bot.media.probe",
        return_value={"width": 100, "height": 200, "duration": 5},
    ):
        sent = await _reply_with_video(message, str(clip), "caption")

    assert sent is True
    message.reply_video.assert_awaited_once()
    _, kwargs = message.reply_video.await_args
    assert kwargs["supports_streaming"] is True
    assert kwargs["width"] == 100
    assert kwargs["height"] == 200
    assert kwargs["duration"] == 5
    assert kwargs["caption"] == "caption"


@pytest.mark.asyncio
async def test_reply_with_video_returns_false_on_send_error(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"0" * 1024)
    message = MagicMock()
    message.reply_video = AsyncMock(side_effect=RuntimeError("boom"))

    with patch("app.bot.media.probe", return_value=None):
        sent = await _reply_with_video(message, str(clip), "caption")

    assert sent is False


@pytest.mark.asyncio
async def test_reply_with_video_sends_fsinputfile_on_cloud_backend(
    monkeypatch, tmp_path
):
    """Over the cloud API, the video must be wrapped in FSInputFile — a
    bare path string has no meaning to Telegram's cloud servers, only to a
    local-mode Bot API server (#UFB-0036/H2)."""
    from aiogram.types import FSInputFile

    monkeypatch.setattr(bot_module, "_using_local_api", False)
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"0" * 1024)
    message = MagicMock()
    message.reply_video = AsyncMock()

    with patch("app.bot.media.probe", return_value=None):
        await _reply_with_video(message, str(clip), "caption")

    args, _ = message.reply_video.await_args
    assert isinstance(args[0], FSInputFile)


@pytest.mark.asyncio
async def test_reply_with_video_sends_plain_path_on_local_backend(
    monkeypatch, tmp_path
):
    """Over a local Bot API server, the video is handed through as a plain
    path string so aiogram passes it straight to `sendVideo` as a local
    file path instead of reading and uploading the bytes itself — this is
    what makes the shared `cache` volume mount (docker-compose.yml)
    actually matter (#UFB-0036/H2)."""
    monkeypatch.setattr(bot_module, "_using_local_api", True)
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"0" * 1024)
    message = MagicMock()
    message.reply_video = AsyncMock()

    with patch("app.bot.media.probe", return_value=None):
        await _reply_with_video(message, str(clip), "caption")

    args, _ = message.reply_video.await_args
    assert args[0] == str(clip)


@pytest.mark.asyncio
async def test_reply_with_video_retries_as_upload_when_local_path_send_fails(
    monkeypatch, tmp_path
):
    """A local-path send that fails for any reason (observed live: `Bad
    Request: invalid file HTTP URL specified: URL host is empty`, against
    an otherwise valid, readable file — root cause undiagnosed) is retried
    once as a real upload before giving up, rather than immediately falling
    back to the plain text reply (#UFB-0036 follow-up)."""
    from aiogram.types import FSInputFile

    monkeypatch.setattr(bot_module, "_using_local_api", True)
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"0" * 1024)
    message = MagicMock()
    message.reply_video = AsyncMock(
        side_effect=[RuntimeError("invalid file HTTP URL specified"), None]
    )

    with patch("app.bot.media.probe", return_value=None):
        sent = await _reply_with_video(message, str(clip), "caption")

    assert sent is True
    assert message.reply_video.await_count == 2
    first_args, _ = message.reply_video.await_args_list[0]
    second_args, _ = message.reply_video.await_args_list[1]
    assert first_args[0] == str(clip)
    assert isinstance(second_args[0], FSInputFile)


@pytest.mark.asyncio
async def test_reply_with_video_returns_false_when_both_local_attempts_fail(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(bot_module, "_using_local_api", True)
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"0" * 1024)
    message = MagicMock()
    message.reply_video = AsyncMock(side_effect=RuntimeError("boom"))

    with patch("app.bot.media.probe", return_value=None):
        sent = await _reply_with_video(message, str(clip), "caption")

    assert sent is False
    assert message.reply_video.await_count == 2


@pytest.mark.asyncio
async def test_reply_with_video_always_wraps_thumbnail_in_fsinputfile(
    monkeypatch, tmp_path
):
    """`SendVideo.thumbnail` is typed strictly as `InputFile` in aiogram
    (unlike `video`, which accepts `str | InputFile`) — a bare path string
    there fails pydantic validation regardless of backend
    (`is_instance_of`, observed live against a real local-mode send).
    Confirmed for both backends since this is exactly the split `video`
    gets — the thumbnail must NOT follow it (#UFB-0036/H2 regression)."""
    from aiogram.types import FSInputFile

    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"0" * 1024)
    thumb_path = preview.preview_path("clip.mp4")
    os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
    with open(thumb_path, "wb") as f:
        f.write(b"0" * 16)

    for use_local in (True, False):
        monkeypatch.setattr(bot_module, "_using_local_api", use_local)
        message = MagicMock()
        message.reply_video = AsyncMock()
        with patch("app.bot.media.probe", return_value=None):
            await _reply_with_video(message, str(clip), "caption")
        _, kwargs = message.reply_video.await_args
        assert isinstance(kwargs["thumbnail"], FSInputFile)


def test_build_session_returns_none_when_telegram_api_url_unset(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_API_URL", "")
    assert _build_session() is None


def test_build_session_builds_local_session_when_telegram_api_url_set(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_API_URL", "http://telegram-bot-api:8081")
    session = _build_session()
    assert session is not None
    assert session.api.is_local is True
    assert session.api.base == "http://telegram-bot-api:8081/bot{token}/{method}"


# --- UFB-0036: is_telegram_api_reachable ---


def test_telegram_api_reachable_returns_none_when_url_unset(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_API_URL", "")
    assert is_telegram_api_reachable() is None


def test_telegram_api_reachable_returns_true_for_a_listening_server(monkeypatch):
    import socket as socket_module

    server = socket_module.socket(socket_module.AF_INET, socket_module.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    monkeypatch.setattr(settings, "TELEGRAM_API_URL", f"http://127.0.0.1:{port}")

    try:
        assert is_telegram_api_reachable(timeout=1.0) is True
    finally:
        server.close()


def test_telegram_api_reachable_returns_false_for_a_closed_port(monkeypatch):
    import socket as socket_module

    # Bind then immediately close: the port is very unlikely to be
    # listening on anything else, so connecting should be refused.
    probe = socket_module.socket(socket_module.AF_INET, socket_module.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()

    monkeypatch.setattr(settings, "TELEGRAM_API_URL", f"http://127.0.0.1:{port}")
    assert is_telegram_api_reachable(timeout=1.0) is False


# --- UFB-0036: backend selection at startup (no in-process fallback — see
# UFB-0036-native-video-replies.md#if-the-local-server-dies) ---


def test_make_bot_local_true_builds_a_local_session(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_API_URL", "http://telegram-bot-api:8081")
    b = bot_module._make_bot(use_local=True)
    assert b.session.api.is_local is True


def test_make_bot_local_false_uses_the_default_cloud_session(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_API_URL", "http://telegram-bot-api:8081")
    b = bot_module._make_bot(use_local=False)
    assert b.session.api.is_local is False


@pytest.mark.asyncio
async def test_start_polling_picks_local_backend_when_reachable(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_API_URL", "http://telegram-bot-api:8081")
    monkeypatch.setattr(bot_module, "polling_task", None)
    monkeypatch.setattr(bot_module, "_using_local_api", False)

    with (
        patch("app.bot.is_telegram_api_reachable", return_value=True),
        patch("app.bot.dp.start_polling", new=AsyncMock()),
    ):
        bot_module.start_polling()
        assert bot_module._using_local_api is True
        await bot_module.stop_polling()

    assert bot_module.polling_task.done()


@pytest.mark.asyncio
async def test_start_polling_falls_back_to_cloud_when_local_unreachable(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_API_URL", "http://telegram-bot-api:8081")
    monkeypatch.setattr(bot_module, "polling_task", None)
    monkeypatch.setattr(bot_module, "_using_local_api", True)

    with (
        patch("app.bot.is_telegram_api_reachable", return_value=False),
        patch("app.bot.dp.start_polling", new=AsyncMock()),
    ):
        bot_module.start_polling()
        assert bot_module._using_local_api is False
        await bot_module.stop_polling()

    assert bot_module.polling_task.done()
