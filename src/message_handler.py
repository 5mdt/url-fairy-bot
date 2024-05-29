# message_handler.py
import logging
from aiogram import types
from healthcheck import perform_healthcheck

logger = logging.getLogger(__name__)


async def message_handle(message: types.Message):
    logger.debug(f"Received message: {message.text}")

    if message.text.strip() == "/healthcheck":
        healthcheck_result = perform_healthcheck()
        await message.reply(healthcheck_result)
        return
    if message.text.strip() == "/start":
        await message.reply(
            f"This bot helps to watch content from TikTok, Shorts, Twitter and Instagram Reels more convenient inside telegram.\n\n"
            f"Send me the link here or add me to chatgroup.",
            parse_mode=types.ParseMode.MARKDOWN,
        )
        return
    await echo(message)



async def echo(message: types.Message):
    await message.answer(message.text)
