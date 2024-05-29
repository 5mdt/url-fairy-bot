# message_handler.py
import logging
from aiogram import types
from healthcheck import perform_healthcheck  # Import the function for health check

logger = logging.getLogger(__name__)


async def message_handle(message: types.Message):
    logger.debug(f"Received message: {message.text}")

    # Check if the message is '/healthcheck'
    if message.text.strip() == "/healthcheck":
        healthcheck_result = perform_healthcheck()
        await message.reply(healthcheck_result)
    else:
        # Continue with regular message handling
        await echo(message)  # Assuming `echo` is the regular message handling logic


async def echo(message: types.Message):
    await message.answer(message.text)
