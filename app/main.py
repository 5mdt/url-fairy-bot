# main.py
# -*- coding: utf-8 -*-

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings

from . import bot, cleanup, pages
from .api import api_router

# Logging configuration
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        pages.seed_static_pages()
    except OSError as e:
        logger.warning(f"Failed to seed static pages: {e}")
    bot.start_polling()
    cleanup.start_cleanup()
    yield
    cleanup.stop_cleanup()
    await bot.stop_polling()


# Initialize FastAPI app
app = FastAPI(lifespan=lifespan)

# Add router
app.include_router(api_router)

logger.info("✨ URL Fairy bot initialized with FastAPI")
