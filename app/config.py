# config.py
import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings  # Updated import

load_dotenv()


class Settings(BaseSettings):
    BASE_URL: str = os.getenv("BASE_URL", "")
    IV_RHASH: str = os.getenv("IV_RHASH", "")
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    CACHE_DIR: str = os.getenv("CACHE_DIR", "/tmp/url-fairy-bot-cache/")
    FILE_TTL: int = int(os.getenv("FILE_TTL", 3))  # days untouched before deletion
    CLEANUP_INTERVAL: int = int(os.getenv("CLEANUP_INTERVAL", 3600))  # seconds
    COOKIES_DIR: str = os.getenv("COOKIES_DIR", "/config/")
    DOWNLOAD_ALLOWED_DOMAINS: str = os.getenv("DOWNLOAD_ALLOWED_DOMAINS", "")
    REWRITE_ALLOWED_DOMAINS: str = os.getenv("REWRITE_ALLOWED_DOMAINS", "")
    FOLLOW_REDIRECT_TIMEOUT: int = int(os.getenv("FOLLOW_REDIRECT_TIMEOUT", 10))
    COOKIE_JAR_ENABLED: bool = os.getenv("COOKIE_JAR_ENABLED", "false").lower() not in (
        "false",
        "0",
        "no",
    )
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # Domain-rewrite mirror destinations (source-matching regex stays in code)
    SPOTIFY_MIRROR_DOMAIN: str = os.getenv("SPOTIFY_MIRROR_DOMAIN", "fxspotify.com")
    INSTAGRAM_MIRROR_DOMAIN: str = os.getenv(
        "INSTAGRAM_MIRROR_DOMAIN", "kkinstagram.com"
    )
    REDDIT_MIRROR_DOMAIN: str = os.getenv("REDDIT_MIRROR_DOMAIN", "rxddit.com")
    THREADS_MIRROR_DOMAIN: str = os.getenv("THREADS_MIRROR_DOMAIN", "fx.akitsuki.me")
    TIKTOK_MIRROR_DOMAIN: str = os.getenv("TIKTOK_MIRROR_DOMAIN", "tfxktok.com")
    TWITTER_MIRROR_DOMAIN: str = os.getenv("TWITTER_MIRROR_DOMAIN", "fxtwitter.com")
    YOUTUBE_MIRROR_DOMAIN: str = os.getenv("YOUTUBE_MIRROR_DOMAIN", "yfxtube.com")
    YOUTUBE_SHORT_MIRROR_DOMAIN: str = os.getenv(
        "YOUTUBE_SHORT_MIRROR_DOMAIN", "fxyoutu.be"
    )


settings = Settings()
