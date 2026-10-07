# UFB-0021. Environment-based configuration

**Tags:** #config

## User Story

As an operator, I want all settings read from environment variables with sensible defaults, so that I configure the app without touching code.

## Behavior

All operator-facing settings are configured via environment variables (or a `.env` file), each documented under the name it's actually read from, with a sensible default when unset. Boolean settings accept only recognized true/false spellings — an unrecognized value is a startup error, not a silent default.

## Implementation

- Settings are loaded once at startup from the environment / `.env`. Every `Settings` field is a plain typed default (e.g. `BOT_TOKEN: str = ""`); `pydantic_settings.BaseSettings` itself reads the environment, so there is no per-field `os.getenv(...)` ([BUG-0037](../BUGS.md)). `load_dotenv()` still runs first so `.env` values reach the process environment.
- Documented variables: `BOT_TOKEN`, `BASE_URL`, `CACHE_DIR`, `COOKIES_DIR`, `COOKIE_JAR_ENABLED`, `DOWNLOAD_ALLOWED_DOMAINS`, `REWRITE_ALLOWED_DOMAINS`, `FOLLOW_REDIRECT_TIMEOUT`, `LOG_LEVEL`, `API_KEY`, `API_RATE_LIMIT`, `API_RATE_WINDOW`, `REPORT_RATE_LIMIT`, `REPORT_RATE_WINDOW` ([UFB-0051](UFB-0051-report-broken-link.md)), `TRUSTED_PROXIES` ([UFB-0056](UFB-0056-api-auth-rate-limiting.md)), `FILE_TTL`, `CLEANUP_INTERVAL`, and the `*_MIRROR_DOMAIN` values.

## Quirks & Decisions

Known gaps:

- `COOKIES_DIR` actually reads the environment variable `COOKIES_FILE`, not `COOKIES_DIR` ([BUGS #3](../BUGS.md#3-cookies_dir-reads-the-wrong-environment-variable-high-p1d1)).
- Boolean parsing treats any unrecognized string as `True` instead of raising (see `TODO.md`, Config).
- `LOG_LEVEL` isn't validated against known logging levels (see `TODO.md` addition below).

## Testing

### Unit

- Each documented variable, when set, is read under that exact name.
- An unrecognized boolean value → startup error, not a silent `True`.
- A bool, an int, and a float field each parse from the environment into their declared type.

## Status

Implemented
