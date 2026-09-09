# main.py
# -*- coding: utf-8 -*-

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings

from . import pages
from .api import api_router
from .bot import bot, dp  # Import the bot and dispatcher directly

# Logging configuration
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        pages.seed_static_pages()
    except OSError as e:
        logger.warning(f"Failed to seed static pages: {e}")
    # Start the bot's polling in a background task
    asyncio.create_task(dp.start_polling(bot))
    yield
    # Shutdown the dispatcher when FastAPI stops
    await dp.storage.close()
    await bot.session.close()


# Initialize FastAPI app
app = FastAPI(lifespan=lifespan)

# Add router
app.include_router(api_router)

logger.info("✨ URL Fairy bot initialized with FastAPI")
