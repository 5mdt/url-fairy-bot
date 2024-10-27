# bot.py
# -*- coding: utf-8 -*-

import logging
import re

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

from app.config import settings

from .url_processing import process_url_request

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher(bot)
logger = logging.getLogger(__name__)


async def start(message: types.Message):
    await message.reply("Hello! Send me a URL to process!")


@dp.message_handler(content_types=types.ContentType.TEXT)
async def handle_message(message: types.Message):
    # Regular expression to find URLs in the message text
    url_pattern = r'(https?://\S+)'
    urls = re.findall(url_pattern, message.text.strip())

    # If no URLs are found, reply with an instruction message
    if not urls:
        await message.reply("Please send a valid URL to process!")
        return

    # Process each URL and reply with individual messages
    for url in urls:
        result = await process_url_request(url)
        await message.reply(
            result,
            parse_mode=types.ParseMode.MARKDOWN,
        )


def start_bot():
    dp.register_message_handler(start, commands="start")
    executor.start_polling(dp, skip_updates=True)
