# main
# -*- coding: utf-8 -*-
import logging
import asyncio
from threading import Thread
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils import executor
from fastapi import FastAPI
import config
import uvicorn
from message_handler import message_handle
from healthcheck import router as healthcheck_router


# Initialize logging
logging.basicConfig(level=config.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Initialize FastAPI
REST_API = FastAPI()

# Include the health check router
REST_API.include_router(healthcheck_router)

# Initialize aiogram
bot = Bot(token=config.BOT_TOKEN)
TELEGRAM_DISPATCHER = Dispatcher(bot)
TELEGRAM_DISPATCHER.middleware.setup(LoggingMiddleware())


# Echo handler using the message_handle function from the message_handler submodule
@TELEGRAM_DISPATCHER.message_handler()
async def echo(message: types.Message):
    await message_handle(message)


if __name__ == "__main__":
    # Log startup
    logger.info("Starting bot and FastAPI server")

    # Function to start the bot
    def start_bot():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        executor.start_polling(TELEGRAM_DISPATCHER, skip_updates=False, loop=loop)

    # Function to start the FastAPI server
    def start_fastapi():
        uvicorn.run(REST_API, host="0.0.0.0", port=80)

    # Start the bot in a separate thread
    bot_thread = Thread(target=start_bot)
    bot_thread.start()

    # Start the FastAPI server in a separate thread
    fastapi_thread = Thread(target=start_fastapi)
    fastapi_thread.start()

    # Keep the main thread running
    bot_thread.join()
    fastapi_thread.join()
