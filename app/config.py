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
    # #UFB-0056
    API_KEY: str = ""  # comma-separated; empty = endpoint open
    API_RATE_LIMIT: int = 30  # requests per window per client; 0 disables
    API_RATE_WINDOW: int = 60  # seconds
    TRUSTED_PROXIES: str = ""  # comma-separated IPs/CIDRs
    # #UFB-0051
    REPORT_RATE_LIMIT: int = 3  # broken-link reports per window per user; 0 disables
    REPORT_RATE_WINDOW: int = 3600  # seconds
    # #UFB-0050
    DUPLICATE_WINDOW: int = (
        3600  # seconds a repeat link is answered by a pointer; 0 off
    )
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

    # #UFB-0054, #UFB-0049
    ADMIN_CHAT_ID: str = ""  # comma-separated chat IDs; empty = alerts and /stats off

    @property
    def admin_chat_ids(self) -> list[int]:
        """#UFB-0054, #UFB-0049: parsed ADMIN_CHAT_ID; blank entries are skipped."""
        return [int(p) for p in self.ADMIN_CHAT_ID.split(",") if p.strip()]

    # #UFB-0054: per-kind switches; None = on when ADMIN_CHAT_ID is set
    ALERT_COOKIES: bool | None = None
    ALERT_FAILURE_SPIKE: bool | None = None
    ALERT_BOT_API: bool | None = None
    ALERT_YTDLP: bool | None = None
    ALERT_CACHE: bool | None = None

    @field_validator(
        "ALERT_COOKIES",
        "ALERT_FAILURE_SPIKE",
        "ALERT_BOT_API",
        "ALERT_YTDLP",
        "ALERT_CACHE",
        mode="before",
    )
    @classmethod
    def _blank_switch_is_auto(cls, v):
        """#UFB-0054: an empty env value (docker-compose default) means auto."""
        return None if isinstance(v, str) and not v.strip() else v

    ALERT_CHECK_INTERVAL: int = 60  # seconds between checks
    ALERT_MIN_INTERVAL: int = 3600  # seconds between alerts for one fault
    ALERT_FAILURE_SPIKE_MIN_ATTEMPTS: int = 5
    ALERT_FAILURE_SPIKE_WINDOW_MINUTES: int = 10
    ALERT_FAILURE_SPIKE_RATIO: float = 0.5
    ALERT_YTDLP_MAX_AGE_DAYS: int = 60
    ALERT_CACHE_FULL_PERCENT: int = 90

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
