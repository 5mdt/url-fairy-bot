# main.py
# -*- coding: utf-8 -*-

import asyncio
import logging

from fastapi import FastAPI

from app.config import settings

from .api import api_router
from .bot import bot, dp  # Import the bot and dispatcher directly

# Initialize FastAPI app
app = FastAPI()

# Add router
app.include_router(api_router)

# Logging configuration
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def on_startup():
    # Start the bot's polling in a background task
    asyncio.create_task(dp.start_polling(bot))


@app.on_event("shutdown")
async def on_shutdown():
    # Shutdown the dispatcher when FastAPI stops
    await dp.storage.close()
    await bot.session.close()


logger.info("✨ URL Fairy bot initialized with FastAPI")
