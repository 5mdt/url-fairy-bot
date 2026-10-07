# duplicates_test.py
# #UFB-0050: duplicate link detection.

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramBadRequest

from app import bot as bot_module
from app import duplicates
from app.bot import handle_message
from app.config import settings
from app.url_processing import DownloadResult


@pytest.fixture(autouse=True)
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path) + "/")
    monkeypatch.setattr(settings, "DUPLICATE_WINDOW", 3600)


# --- normalization and store ---


# #UFB-0050
@pytest.mark.parametrize(
    "a,b",
    [
        ("HTTPS://Example.COM/v/1", "https://example.com/v/1"),
        ("https://example.com/v/1/", "https://example.com/v/1"),
        ("https://example.com/v/1#t=5", "https://example.com/v/1"),
        ("https://example.com/v/1?utm_source=x&a=1", "https://example.com/v/1?a=1"),
        ("https://example.com/v/1?fbclid=zz", "https://example.com/v/1"),
    ],
)
def test_normalize_url_equates_same_links(a, b):
    assert duplicates.normalize_url(a) == duplicates.normalize_url(b)


# #UFB-0050
def test_normalize_url_keeps_different_links_apart():
    assert duplicates.normalize_url("https://e.com/v?id=1") != duplicates.normalize_url(
        "https://e.com/v?id=2"
    )


# #UFB-0050
def test_record_then_lookup_uses_normalized_url_and_chat():
    duplicates.record(1, "https://Example.com/v/1/", 42, now=1000)
    assert duplicates.lookup(1, "https://example.com/v/1?utm_x=1", now=1100) == 42
    assert duplicates.lookup(2, "https://example.com/v/1", now=1100) is None


# #UFB-0050
def test_lookup_expires_after_window():
    duplicates.record(1, "https://e.com/a", 42, now=1000)
    assert duplicates.lookup(1, "https://e.com/a", now=1000 + 3599) == 42
    assert duplicates.lookup(1, "https://e.com/a", now=1000 + 3600) is None


# #UFB-0050
def test_window_zero_disables(monkeypatch):
    monkeypatch.setattr(settings, "DUPLICATE_WINDOW", 0)
    duplicates.record(1, "https://e.com/a", 42)
    assert duplicates.lookup(1, "https://e.com/a") is None
    assert not os.path.exists(duplicates.replies_dir())


# #UFB-0050
def test_record_keeps_other_chats_and_prunes_expired():
    duplicates.record(1, "https://e.com/a", 10, now=0)
    duplicates.record(2, "https://e.com/a", 20, now=5000)
    assert duplicates.lookup(1, "https://e.com/a", now=5001) is None
    assert duplicates.lookup(2, "https://e.com/a", now=5001) == 20


# #UFB-0050
def test_corrupt_record_reads_as_miss():
    duplicates.record(1, "https://e.com/a", 10)
    path = duplicates._path("https://e.com/a")
    with open(path, "w") as f:
        f.write("{not json")
    assert duplicates.lookup(1, "https://e.com/a") is None


# #UFB-0050
def test_forget_removes_entry():
    duplicates.record(1, "https://e.com/a", 10)
    duplicates.forget(1, "https://e.com/a")
    assert duplicates.lookup(1, "https://e.com/a") is None


# #UFB-0050
def test_sweep_file_removes_only_fully_expired_records():
    duplicates.record(1, "https://e.com/a", 10, now=1000)
    path = duplicates._path("https://e.com/a")
    assert duplicates.sweep_file(path, now=1100) is False
    assert os.path.exists(path)
    assert duplicates.sweep_file(path, now=1000 + 3600) is True
    assert not os.path.exists(path)


# --- ReplyRecorder ---


# #UFB-0050
@pytest.mark.asyncio
async def test_recorder_keeps_first_reply_id_and_delegates():
    msg = MagicMock()
    msg.text = "hi"
    msg.reply = AsyncMock(return_value=MagicMock(message_id=7))
    msg.reply_audio = AsyncMock(return_value=MagicMock(message_id=8))
    rec = duplicates.ReplyRecorder(msg)
    assert rec.text == "hi"
    await rec.reply("a")
    await rec.reply_audio("b")
    assert rec.first_id == 7


# #UFB-0050
@pytest.mark.asyncio
async def test_recorder_handles_media_group_list_and_failure():
    msg = MagicMock()
    msg.reply_media_group = AsyncMock(
        return_value=[MagicMock(message_id=3), MagicMock(message_id=4)]
    )
    msg.reply_video = AsyncMock(side_effect=RuntimeError("boom"))
    rec = duplicates.ReplyRecorder(msg)
    with pytest.raises(RuntimeError):
        await rec.reply_video("v")
    assert rec.first_id is None
    await rec.reply_media_group([])
    assert rec.first_id == 3


# --- handler integration ---


def make_message(text, chat_type="private", chat_id=5):
    message = MagicMock()
    message.text = text
    message.chat.type = chat_type
    message.chat.id = chat_id
    message.reply_to_message = None
    message.reply = AsyncMock(return_value=MagicMock(message_id=100))
    message.answer = AsyncMock(return_value=MagicMock(message_id=101))
    return message


# #UFB-0050
@pytest.mark.asyncio
async def test_repeat_link_gets_short_reply_to_earlier_one(monkeypatch):
    process = AsyncMock(return_value="full reply")
    monkeypatch.setattr(bot_module, "process_url_request", process)

    first = make_message("https://e.com/v/1")
    await handle_message(first)
    assert process.await_count == 1
    first.reply.assert_awaited_once()

    second = make_message("https://E.com/v/1/?utm_source=x")
    await handle_message(second)
    assert process.await_count == 1  # no second download
    second.reply.assert_not_awaited()
    second.answer.assert_awaited_once()
    kwargs = second.answer.await_args.kwargs
    assert kwargs["reply_parameters"].message_id == 100
    assert kwargs["reply_parameters"].allow_sending_without_reply is False


# #UFB-0050
@pytest.mark.asyncio
async def test_repeat_in_another_chat_gets_full_reply(monkeypatch):
    process = AsyncMock(return_value="full reply")
    monkeypatch.setattr(bot_module, "process_url_request", process)
    await handle_message(make_message("https://e.com/v/1", chat_id=1))
    other = make_message("https://e.com/v/1", chat_id=2)
    await handle_message(other)
    assert process.await_count == 2
    other.reply.assert_awaited_once()


# #UFB-0050
@pytest.mark.asyncio
async def test_deleted_earlier_reply_falls_back_to_normal_reply(monkeypatch):
    process = AsyncMock(return_value="full reply")
    monkeypatch.setattr(bot_module, "process_url_request", process)
    await handle_message(make_message("https://e.com/v/1"))

    second = make_message("https://e.com/v/1")
    second.answer = AsyncMock(
        side_effect=TelegramBadRequest(
            method=MagicMock(), message="message to be replied not found"
        )
    )
    await handle_message(second)
    assert process.await_count == 2
    second.reply.assert_awaited_once()
    # the fresh reply replaced the stale entry
    assert duplicates.lookup(5, "https://e.com/v/1") == 100


# #UFB-0050
@pytest.mark.asyncio
async def test_quiet_group_link_records_nothing(monkeypatch):
    process = AsyncMock(return_value=None)
    monkeypatch.setattr(bot_module, "process_url_request", process)
    await handle_message(make_message("https://e.com/v/1", chat_type="group"))
    assert duplicates.lookup(5, "https://e.com/v/1") is None


# #UFB-0050
@pytest.mark.asyncio
async def test_group_repeat_is_detected(monkeypatch):
    process = AsyncMock(return_value="full reply")
    monkeypatch.setattr(bot_module, "process_url_request", process)
    await handle_message(make_message("https://e.com/v/1", chat_type="supergroup"))
    again = make_message("https://e.com/v/1", chat_type="supergroup")
    await handle_message(again)
    assert process.await_count == 1
    again.answer.assert_awaited_once()


# #UFB-0050
@pytest.mark.asyncio
async def test_detection_disabled_always_processes(monkeypatch):
    monkeypatch.setattr(settings, "DUPLICATE_WINDOW", 0)
    process = AsyncMock(return_value="full reply")
    monkeypatch.setattr(bot_module, "process_url_request", process)
    await handle_message(make_message("https://e.com/v/1"))
    await handle_message(make_message("https://e.com/v/1"))
    assert process.await_count == 2


# #UFB-0050
@pytest.mark.asyncio
async def test_download_result_reply_is_recorded(monkeypatch):
    result = DownloadResult(text="t", media_path=None)
    monkeypatch.setattr(
        bot_module, "process_url_request", AsyncMock(return_value=result)
    )
    await handle_message(make_message("https://e.com/v/9"))
    assert duplicates.lookup(5, "https://e.com/v/9") == 100
