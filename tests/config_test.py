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
