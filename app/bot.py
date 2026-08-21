# bot.py
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


async def start(message: Message):
    await message.reply("Hello! Send me a URL to process!")


@dp.message(F.text)
async def handle_message(message: Message):
    """
    Process and respond to URLs extracted from incoming messages.

    In group chats, if the message is a reply to the bot's own message, replies with an emoji and returns. Otherwise, extracts URLs from the message text. If no URLs are found, silently returns in group chats or replies with an error message in private chats. For each valid URL, processes it and sends the processing result as a reply. Logs validation errors and reports them to the user.
    """
    if message.chat.type in GROUP_CHAT_TYPES and message.reply_to_message:
        if message.reply_to_message.from_user.id == bot.id:
            await message.reply(
                "\_ (ツ)_/",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

    url_pattern = r"(https?://\S+)"
    urls = re.findall(url_pattern, message.text.strip())

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
            await message.reply(f"Invalid URL provided: {e}")


def start_bot():
    dp.message.register(start, CommandStart())
    dp.run_polling(bot, skip_updates=False)
