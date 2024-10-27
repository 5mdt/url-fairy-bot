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
    # Check if the message is a reply to the bot in a group chat
    if message.chat.type in ["group", "supergroup"] and message.reply_to_message:
        if message.reply_to_message.from_user.id == bot.id:
            # Reply with "PANIC" if the bot was the original sender
            await message.reply(
                "Please do not be mad at me 🥺. I am not very clever bot 👉👈"
                + "\n\n"
                + "I am very sorry if i did not help you"
                + "\n\n"
                + "Sometimes i use external tools to help you, but they can "
                + "be offline or could not parse media too. "
                + "Espescially if we are talking about Facebook 🤬"
                + "\n\n"
                + "Please donate to [Centre T](https://translyaciya.com/help_eng)",
                parse_mode=types.ParseMode.MARKDOWN,
            )
            return

    # Regular expression to find URLs in the message text
    url_pattern = r"(https?://\S+)"
    urls = re.findall(url_pattern, message.text.strip())

    # If no URLs are found in a group chat, ignore the message
    if not urls:
        if message.chat.type in ["group", "supergroup"]:
            return
        else:
            # If in a private chat, prompt the user to send a valid URL
            await message.reply("Please send a valid URL to process!")
            return

    # Process each URL and reply with individual messages
    for url in urls:
        # Pass `is_group_chat=True` if the message is in a group
        is_group_chat = message.chat.type in ["group", "supergroup"]
        result = await process_url_request(url, is_group_chat=is_group_chat)

        # If result is None, do not reply
        if result is not None:
            await message.reply(
                result,
                parse_mode=types.ParseMode.MARKDOWN,
            )


def start_bot():
    dp.register_message_handler(start, commands="start")
    executor.start_polling(dp, skip_updates=False)
