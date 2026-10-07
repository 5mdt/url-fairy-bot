# conftest.py

import os

# Must run before any `app.*` module is imported: app/config.py evaluates
# `os.getenv(...)` as field defaults at class-definition time and instantiates
# `settings = Settings()` at import time, and app/bot.py constructs a real
# `Bot(token=settings.BOT_TOKEN)` at import time too. Under aiogram 3.30,
# `Bot(token="")` raises `TokenValidationError`, so a clean clone with no
# `.env` fails at collection without this. `os.environ.setdefault` means a
# developer's real `.env` (loaded later via `load_dotenv()`, which does not
# override already-set variables) never overrides this dummy value, so tests
# behave the same on every machine.
os.environ.setdefault("BOT_TOKEN", "123456:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw")

import pytest  # noqa: E402

from app.config import settings  # noqa: E402


@pytest.fixture(autouse=True)
def pinned_settings(monkeypatch):
    """
    Pin every setting the suite depends on so tests are isolated from
    whatever happens to be in the developer's `.env` or the CI environment
    (fixes BUGS.md #20 — "defaults" tests silently depending on ambient env).
    """
    monkeypatch.setattr(settings, "DOWNLOAD_ALLOWED_DOMAINS", "")
    monkeypatch.setattr(settings, "REWRITE_ALLOWED_DOMAINS", "")
    monkeypatch.setattr(settings, "BASE_URL", "example.test")
    monkeypatch.setattr(settings, "IV_RHASH", "")
    monkeypatch.setattr(settings, "TELEGRAM_API_URL", "")
    monkeypatch.setattr(settings, "CACHE_DIR", "/tmp/url-fairy-bot-cache-test/")
    monkeypatch.setattr(settings, "COOKIES_DIR", "/tmp/url-fairy-bot-cookies-test/")
    monkeypatch.setattr(settings, "FOLLOW_REDIRECT_TIMEOUT", 10)
    monkeypatch.setattr(settings, "API_KEY", "")
    monkeypatch.setattr(settings, "API_RATE_LIMIT", 30)
    monkeypatch.setattr(settings, "API_RATE_WINDOW", 60)
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", "")
    monkeypatch.setattr(settings, "DUPLICATE_WINDOW", 0)  # #UFB-0050
    monkeypatch.setattr(settings, "COOKIE_JAR_ENABLED", False)
    monkeypatch.setattr(settings, "COOKIE_KEEPALIVE_INTERVAL", 3600)
    monkeypatch.setattr(settings, "COOKIE_HEALTHCHECK", False)
    monkeypatch.setattr(settings, "SPOTIFY_MIRROR_DOMAIN", "fxspotify.com")
    monkeypatch.setattr(settings, "INSTAGRAM_MIRROR_DOMAIN", "kkinstagram.com")
    monkeypatch.setattr(settings, "REDDIT_MIRROR_DOMAIN", "rxddit.com")
    monkeypatch.setattr(settings, "TIKTOK_MIRROR_DOMAIN", "tfxktok.com")
    monkeypatch.setattr(settings, "TWITTER_MIRROR_DOMAIN", "fxtwitter.com")
    monkeypatch.setattr(settings, "YOUTUBE_MIRROR_DOMAIN", "yfxtube.com")
    monkeypatch.setattr(settings, "YOUTUBE_SHORT_MIRROR_DOMAIN", "fxyoutu.be")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """
    Fail loudly instead of silently hitting the internet if a test forgets to
    mock a network call. Individual tests that intentionally exercise
    `follow_redirects` mock `requests.head` themselves, which takes
    precedence over this fixture.
    """

    def _blocked(*args, **kwargs):
        raise AssertionError(
            "Unmocked outbound requests.head() call in a test — mock it explicitly."
        )

    monkeypatch.setattr("requests.head", _blocked)


@pytest.fixture(autouse=True)
def no_dns(monkeypatch):
    """
    #BUG-0012: follow_redirects resolves hosts before requesting them. Keep
    tests off the real resolver: IP literals resolve to themselves, every
    other name to a fixed public address. Tests needing other answers patch
    `app.url_processing.socket.getaddrinfo` themselves.
    """
    import ipaddress

    def _fake(host, port, *args, **kwargs):
        try:
            ip = str(ipaddress.ip_address(host))
        except ValueError:
            ip = "93.184.216.34"
        return [(2, 1, 6, "", (ip, port or 0))]

    monkeypatch.setattr("socket.getaddrinfo", _fake)


@pytest.fixture(autouse=True)
def fresh_rate_limiter():
    """#UFB-0056: the limiter is process-global; start every test empty."""
    from app import api_security

    api_security.reset_rate_limiter()


@pytest.fixture(autouse=True)
def fresh_metrics():
    """#UFB-0045: every test starts with zeroed usage metrics."""
    from app import metrics

    metrics.reset()
