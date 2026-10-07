# config_test.py

import importlib

import pydantic
import pytest


@pytest.fixture
def reload_settings(monkeypatch):
    """
    app/config.py evaluates os.getenv(...) as field defaults at
    class-definition time, so values are frozen at import. Re-import the
    module under a patched environment to observe how a given env var value
    is actually parsed.
    """

    set_keys = []

    def _reload(**env):
        for key, value in env.items():
            monkeypatch.setenv(key, value)
            set_keys.append(key)
        import app.config as config_module

        importlib.reload(config_module)
        return config_module.settings

    yield _reload

    # Undo the env changes *before* reloading, so a deliberately-invalid
    # value used by a test doesn't also raise during teardown here.
    for key in set_keys:
        monkeypatch.delenv(key, raising=False)
    import app.config as config_module

    importlib.reload(config_module)


# NOTE: docs/TODO.md:47-50 claims the hand-rolled
# `os.getenv(X, "true").lower() not in ("false", "0", "no")` idiom treats any
# unrecognized string as True. That claim was written without accounting for
# `Settings` being a `pydantic_settings.BaseSettings` subclass: whenever the
# env var is actually *set*, pydantic-settings' own env source reads it and
# coerces it with pydantic's stricter bool parser, which OVERRIDES the
# hand-rolled expression entirely (that expression only ever supplies the
# class-level default used when the var is unset). Verified directly:
# `COOKIE_JAR_ENABLED=off` correctly parses to False (pydantic recognizes
# "off" as falsy), and `COOKIE_JAR_ENABLED=banana` or `=""` raise
# `pydantic_core.ValidationError` at `Settings()` construction time
# (`app/config.py:39`) instead of silently defaulting to True. This is a real
# behavior not yet reflected in docs/TODO.md or docs/BUGS.md: bad input
# crashes app startup with a validation error rather than silently
# misconfiguring the bot. The tests below encode the verified behavior.


@pytest.mark.parametrize(
    "value,expected",
    [
        ("true", True),
        ("false", False),
        ("0", False),
        ("no", False),
        ("1", True),
        ("off", False),  # pydantic's own bool coercion recognizes this
        ("on", True),
    ],
)
def test_cookie_jar_enabled_recognized_values(reload_settings, value, expected):
    settings = reload_settings(COOKIE_JAR_ENABLED=value)
    assert settings.COOKIE_JAR_ENABLED is expected


@pytest.mark.parametrize("value", ["banana", "maybe", "yolo"])
def test_cookie_jar_enabled_rejects_unparseable_value(reload_settings, value):
    with pytest.raises(pydantic.ValidationError):
        reload_settings(COOKIE_JAR_ENABLED=value)


def test_cookie_jar_enabled_rejects_empty_string(reload_settings):
    with pytest.raises(pydantic.ValidationError):
        reload_settings(COOKIE_JAR_ENABLED="")


# --- UFB-0036: TELEGRAM_API_URL / CLOUD_SEND_VIDEO_MAX_MB / LOCAL_SEND_VIDEO_MAX_MB ---


def test_telegram_api_url_defaults_to_empty(reload_settings):
    settings = reload_settings()
    assert settings.TELEGRAM_API_URL == ""


def test_telegram_api_url_reads_env(reload_settings):
    settings = reload_settings(TELEGRAM_API_URL="http://telegram-bot-api:8081")
    assert settings.TELEGRAM_API_URL == "http://telegram-bot-api:8081"


def test_cloud_send_video_max_mb_defaults_to_10(reload_settings):
    settings = reload_settings()
    assert settings.CLOUD_SEND_VIDEO_MAX_MB == 10


def test_cloud_send_video_max_mb_reads_env(reload_settings):
    settings = reload_settings(CLOUD_SEND_VIDEO_MAX_MB="20")
    assert settings.CLOUD_SEND_VIDEO_MAX_MB == 20


def test_local_send_video_max_mb_defaults_to_500(reload_settings):
    settings = reload_settings()
    assert settings.LOCAL_SEND_VIDEO_MAX_MB == 500


def test_local_send_video_max_mb_reads_env(reload_settings):
    settings = reload_settings(LOCAL_SEND_VIDEO_MAX_MB="2000")
    assert settings.LOCAL_SEND_VIDEO_MAX_MB == 2000


# #UFB-0038
def test_cookie_keepalive_defaults(reload_settings):
    settings = reload_settings()
    assert settings.COOKIE_KEEPALIVE_INTERVAL == 3600
    assert settings.COOKIE_HEALTHCHECK is False


# #UFB-0038
def test_cookie_keepalive_values_parse(reload_settings):
    settings = reload_settings(COOKIE_KEEPALIVE_INTERVAL="0", COOKIE_HEALTHCHECK="true")
    assert settings.COOKIE_KEEPALIVE_INTERVAL == 0
    assert settings.COOKIE_HEALTHCHECK is True


# --- #UFB-0040 ---


def test_audio_normalize_defaults(reload_settings):
    settings = reload_settings()
    assert settings.AUDIO_NORMALIZE_ENABLED is False
    assert settings.AUDIO_NORMALIZE_BELOW_LUFS == -40.0


def test_audio_normalize_parses_env(reload_settings):
    settings = reload_settings(
        AUDIO_NORMALIZE_ENABLED="true", AUDIO_NORMALIZE_BELOW_LUFS="-35.5"
    )
    assert settings.AUDIO_NORMALIZE_ENABLED is True
    assert settings.AUDIO_NORMALIZE_BELOW_LUFS == -35.5


# --- BUG-0038: LOG_LEVEL validation ---


# #UFB-0024, #BUG-0038
def test_log_level_rejects_invalid_value(reload_settings):
    with pytest.raises(pydantic.ValidationError):
        reload_settings(LOG_LEVEL="VERBOSE")


# #UFB-0024, #BUG-0038
def test_log_level_accepts_lowercase(reload_settings):
    assert reload_settings(LOG_LEVEL="debug").LOG_LEVEL == "DEBUG"


# --- BUG-0037: BaseSettings reads the env itself (no import-time os.getenv) ---


# #UFB-0021, #BUG-0037
def test_settings_read_env_at_construction_not_import(monkeypatch):
    import app.config as config_module

    monkeypatch.setenv("COOKIE_JAR_ENABLED", "true")
    monkeypatch.setenv("AUDIO_NORMALIZE_BELOW_LUFS", "-12.5")
    monkeypatch.setenv("BOT_TOKEN", "tok")
    fresh = config_module.Settings()
    assert fresh.COOKIE_JAR_ENABLED is True
    assert fresh.AUDIO_NORMALIZE_BELOW_LUFS == -12.5
    assert fresh.BOT_TOKEN == "tok"


# #UFB-0054, #UFB-0049
def test_admin_chat_ids_default_empty(reload_settings):
    assert reload_settings(ADMIN_CHAT_ID="").admin_chat_ids == []


# #UFB-0054, #UFB-0049
def test_admin_chat_ids_parses_comma_list(reload_settings):
    s = reload_settings(ADMIN_CHAT_ID="123, -1001,,456")
    assert s.admin_chat_ids == [123, -1001, 456]
