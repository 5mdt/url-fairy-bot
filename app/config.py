# config.py
from typing import Literal

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings  # Updated import

load_dotenv()


# #UFB-0021, #BUG-0037: plain typed defaults; BaseSettings reads the env itself.
class Settings(BaseSettings):
    BASE_URL: str = ""
    IV_RHASH: str = ""
    INLINE_VIDEO_MAX_MB: int = 10
    # #UFB-0036
    TELEGRAM_API_URL: str = ""
    CLOUD_SEND_VIDEO_MAX_MB: int = 10
    LOCAL_SEND_VIDEO_MAX_MB: int = 500
    BOT_TOKEN: str = ""
    CACHE_DIR: str = "/tmp/url-fairy-bot-cache/"
    FILE_TTL: int = 3  # days untouched before deletion
    CLEANUP_INTERVAL: int = 3600  # seconds
    COOKIES_DIR: str = "/config/"
    DOWNLOAD_ALLOWED_DOMAINS: str = ""
    REWRITE_ALLOWED_DOMAINS: str = ""
    FOLLOW_REDIRECT_TIMEOUT: int = 10
    COOKIE_JAR_ENABLED: bool = False
    # #UFB-0038
    COOKIE_KEEPALIVE_INTERVAL: int = 3600
    COOKIE_HEALTHCHECK: bool = False
    # #UFB-0040
    AUDIO_NORMALIZE_ENABLED: bool = False
    AUDIO_NORMALIZE_BELOW_LUFS: float = -40.0
    # #BUG-0038: restricted so a typo fails at settings load, not in basicConfig
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def _upper_log_level(cls, v):
        return v.upper() if isinstance(v, str) else v

    # #UFB-0037
    MESSAGE_LOCALE: str = "en"

    # Domain-rewrite mirror destinations (source-matching regex stays in code)
    # #UFB-0022
    SPOTIFY_MIRROR_DOMAIN: str = "fxspotify.com"
    INSTAGRAM_MIRROR_DOMAIN: str = "kkinstagram.com"
    REDDIT_MIRROR_DOMAIN: str = "rxddit.com"
    THREADS_MIRROR_DOMAIN: str = "fx.akitsuki.me"
    TIKTOK_MIRROR_DOMAIN: str = "tfxktok.com"
    TWITTER_MIRROR_DOMAIN: str = "fxtwitter.com"
    YOUTUBE_MIRROR_DOMAIN: str = "yfxtube.com"
    YOUTUBE_SHORT_MIRROR_DOMAIN: str = "fxyoutu.be"


settings = Settings()
