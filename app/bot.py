# bot.py
import asyncio
import logging
import re

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatType, ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message
from pydantic import ValidationError

from app.config import settings

from .models import URLMessage
from .url_processing import process_url_request

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()
logger = logging.getLogger(__name__)

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


# #UFB-0020
def start_polling() -> None:
    """Start the bot's polling loop as an observable background task."""
    global polling_task
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
    await message.reply("Hello! Send me a URL to process!")


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
                "¯\\_(ツ)_/¯",
                parse_mode=ParseMode.MARKDOWN,
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
            await message.reply("Please send a valid URL to process!")
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
                await message.reply(result, parse_mode=ParseMode.MARKDOWN)

        except ValidationError as e:
            logger.warning(f"Validation error for URL: {url} - {e}")
            await message.reply(
                "Invalid URL provided — that doesn't look like a valid URL."
            )
