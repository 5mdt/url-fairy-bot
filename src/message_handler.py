# message_handler.py
# -*- coding: utf-8 -*-

import logging
import domain_replacements
from aiogram import types
from healthcheck import perform_healthcheck
import time
import asyncio

logger = logging.getLogger(__name__)


async def message_handle(message: types.Message):
    """
    Handle incoming messages.

    Args:
        message (types.Message): Incoming message.
    """
    logger.debug(f"Received message: {message.text}")

    if message.text.strip() == "/healthcheck":
        healthcheck_result = perform_healthcheck()
        await message.reply(healthcheck_result)
        return
    if (message.text.strip() == "/start") or (message.text.strip() == "/help"):
        await message.reply(
            f"✨ I help to watch content from TikTok, Shorts, Twitter and Instagram Reels more convenient inside telegram.\n\n"
            f"✨ Send me the link here or add me to chatgroup.",
            parse_mode=types.ParseMode.MARKDOWN,
        )
        return

    logger.debug("✨ Message received: %s", message.text)

    error_messages = []
    if message.chat.type == types.ChatType.PRIVATE:
        if not any(word.startswith(("http", "www")) for word in message.text.split()):
            error_messages.append(f"There is no links in your message: {message.text}")
            await message.reply("\n".join(error_messages))
            return
    urls = message.text.split()

    # Create a list of coroutines
    tasks = [handle_url(url, message) for url in urls]

    # Run all coroutines concurrently and gather results
    results = await asyncio.gather(*tasks)

    await echo(message)
    return results

async def handle_url(url, message):
    logger.debug("✨ Handling url: %s from %s", url, message)
    time.sleep(5)
    await message.reply(url)

async def echo(message: types.Message):
    """
    Handle incoming messages.

    Args:
        message (types.Message): Incoming message.
    """
    await message.answer(message.text)
