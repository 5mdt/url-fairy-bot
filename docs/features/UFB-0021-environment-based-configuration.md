# UFB-0021. Environment-based configuration

**Tags:** #config

## Behavior

All operator-facing settings are configured via environment variables (or a
`.env` file), each documented under the name it's actually read from, with a
sensible default when unset. Boolean settings accept only recognized
true/false spellings — an unrecognized value is a startup error, not a
silent default.

## Implementation

- Settings are loaded once at startup from the environment / `.env`.
- Documented variables: `BOT_TOKEN`, `BASE_URL`, `CACHE_DIR`, `COOKIES_DIR`,
  `COOKIE_JAR_ENABLED`, `DOWNLOAD_ALLOWED_DOMAINS`, `REWRITE_ALLOWED_DOMAINS`,
  `FOLLOW_REDIRECT_TIMEOUT`, `LOG_LEVEL`, and the `*_MIRROR_DOMAIN` values.

## Testing

### Unit

- Each documented variable, when set, is read under that exact name.
- An unrecognized boolean value → startup error, not a silent `True`.

## Status

Implemented — with known gaps:

- `COOKIES_DIR` actually reads the environment variable `COOKIES_FILE`, not
  `COOKIES_DIR`
  ([BUGS #3](../BUGS.md#3-cookies_dir-reads-the-wrong-environment-variable-high-p1d1)).
- Boolean parsing treats any unrecognized string as `True` instead of
  raising (see `TODO.md`, Config).
- `LOG_LEVEL` isn't validated against known logging levels (see `TODO.md`
  addition below).
