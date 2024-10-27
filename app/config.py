# app/config.py
import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings  # Updated import

load_dotenv()

class Settings(BaseSettings):
    BASE_URL: str = os.getenv("BASE_URL", "")
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    CACHE_DIR: str = os.getenv("CACHE_DIR", "/tmp/url-fairy-bot-cache/")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

settings = Settings()
