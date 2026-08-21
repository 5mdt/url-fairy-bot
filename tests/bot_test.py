# bot_test.py

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.enums import ParseMode

from app.bot import handle_message


def make_message(text, chat_type="private", reply_to_message=None):
    message = MagicMock()
    message.text = text
    message.chat.type = chat_type
    message.reply_to_message = reply_to_message
    message.reply = AsyncMock()
    return message


# --- no URL in the message ---


@pytest.mark.asyncio
async def test_private_chat_no_url_gets_error_reply():
    message = make_message("just some text", chat_type="private")
    await handle_message(message)
    message.reply.assert_awaited_once_with("Please send a valid URL to process!")


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
async def test_private_chat_result_is_replied_with_markdown():
    message = make_message("https://example.com/x", chat_type="private")
    with patch(
        "app.bot.process_url_request", new=AsyncMock(return_value="the reply text")
    ):
        await handle_message(message)
    message.reply.assert_awaited_once_with(
        "the reply text", parse_mode=ParseMode.MARKDOWN
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
    assert kwargs.get("parse_mode") == ParseMode.MARKDOWN


@pytest.mark.asyncio
async def test_reply_to_bot_shrug_text_is_well_formed():
    from app.bot import bot

    reply_to = MagicMock()
    reply_to.from_user.id = bot.id
    message = make_message("anything", chat_type="group", reply_to_message=reply_to)

    await handle_message(message)

    args, kwargs = message.reply.await_args
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
    message.reply.assert_awaited_once_with("reply", parse_mode=ParseMode.MARKDOWN)


# --- validation errors ---


@pytest.mark.asyncio
async def test_invalid_url_logs_and_replies():
    message = make_message("https:///", chat_type="private")
    await handle_message(message)
    message.reply.assert_awaited_once()
    args, _ = message.reply.await_args
    assert "Invalid URL provided" in args[0]


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
