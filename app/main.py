# main.py
# -*- coding: utf-8 -*-

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings

from . import alerts, api_security, bot, cleanup, cookie_keepalive, pages
from .api import api_router

# Logging configuration
# #UFB-0024
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


# #UFB-0020, #UFB-0026, #UFB-0033, #UFB-0038, #UFB-0054, #UFB-0056
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        pages.seed_static_pages()
    except OSError as e:
        logger.warning(f"Failed to seed static pages: {e}")
    api_security.warn_if_open()
    bot.start_polling()
    cleanup.start_cleanup()
    cookie_keepalive.start_keepalive()
    alerts.start_alerts()
    yield
    await alerts.stop_alerts()
    cookie_keepalive.stop_keepalive()
    cleanup.stop_cleanup()
    await bot.stop_polling()


# Initialize FastAPI app
app = FastAPI(lifespan=lifespan)

# Add router
app.include_router(api_router)

logger.info("✨ URL Fairy bot initialized with FastAPI")
