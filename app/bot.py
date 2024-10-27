# bot.py
# -*- coding: utf-8 -*-

import logging

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
    url = message.text.strip()
    result = await process_url_request(url)
    await message.reply(result)


def start_bot():
    dp.register_message_handler(start, commands="start")
    executor.start_polling(dp, skip_updates=True)
