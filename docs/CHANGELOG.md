# Changelog

## 2026-08-22

- Change: replaced the five `*_REWRITE_ENABLED` booleans with a single
  `REWRITE_ALLOWED_DOMAINS` domain allow-list (empty = every platform
  rewritten), and flipped `DOWNLOAD_ALLOWED_DOMAINS`'s empty-list meaning
  from "nothing allowed" to "everything allowed" so both allow-lists are
  opt-in restrictions with consistent semantics. YouTube is no longer
  hard-blocked from real downloads or special-cased ahead of the allow-list
  gate — it's folded into the shared rewrite map and governed by the same
  two settings as every other platform (closes BUG-0023; note this changes
  default behavior: a YouTube link is now downloaded via yt-dlp rather than
  mirrored unless an operator restricts `DOWNLOAD_ALLOWED_DOMAINS`)

## 2026-08-21

- Fix: `follow_redirects` rebuilds the query string against an allow-list of
  content-identifying parameters instead of dropping it entirely (closes BUG-0001)
- Fix: `apply_rewrite_map` now gates each mirror-domain rewrite on its
  corresponding `*_REWRITE_ENABLED` setting (closes BUG-0002)
- Fix: `COOKIES_DIR` now reads the `COOKIES_DIR` environment variable instead
  of the mismatched `COOKIES_FILE` (closes BUG-0003)
- Fix: domain allow-list entries are trimmed, lower-cased, and empties
  dropped; matching requires an exact or subdomain-boundary match instead of a
  raw `endswith` (closes BUG-0005)
- Fix: `black`/`isort` re-run and committed against `app/` so CI lint is green
  again (closes BUG-0008)
- Fix: `follow_redirects` also catches `requests.RequestException` broadly
  instead of only `requests.Timeout` (closes BUG-0011)
- Fix: the test suite no longer requires a real `BOT_TOKEN` to collect —
  `tests/conftest.py` sets a dummy token before any `app.*` module import
  (closes BUG-0018)
- Fix: `bot_test.py` was rewritten to parametrize over chat type and mocked
  `process_url_request` results instead of asserting on an unreachable code
  path (closes BUG-0019)
- Fix: `url_processing_test.py`'s "defaults" tests are now isolated from
  ambient environment variables via an autouse `conftest.py` fixture (closes
  BUG-0020)
- Fix: `api_test.py` now mocks `process_url_request` instead of performing
  live outbound network I/O (closes BUG-0021)
- Fix: escaped the literal dot in the Spotify rewrite pattern (`spotify\.com`)
  (closes BUG-0022)
- Fix: URL extraction trims trailing `.,;:!?)]}'"` characters before
  processing (closes BUG-0024)
- Fix: the reply-to-bot shrug now sends the correct `"¯\_(ツ)_/¯"` text
  (closes BUG-0025)
- Fix: YouTube rewrite patterns accept an optional `www.`/`m.` host prefix,
  bare `youtube.com`, and `/shorts/<id>` (closes BUG-0026)
- Fix: raw pydantic `ValidationError` text is no longer replied to the user; a
  fixed short message is sent instead (closes BUG-0027)
- Fix: `yt_dlp.PostProcessingError` reference corrected to
  `yt_dlp.utils.PostProcessingError` (closes BUG-0028)
- Fix: removed the unreachable generic `except Exception` branch in
  `process_url_request` (closes BUG-0029)
- Fix: `dependabot.yml` moved from `.github/workflows/` to `.github/` (the
  only path GitHub reads) and given valid `pip`/`docker`/`github-actions`
  ecosystems instead of an empty `package-ecosystem` (closes BUG-0017)
- UFB-0028: Multi-arch CI image publishing
- UFB-0027: Docker Compose stack with Traefik routing
- UFB-0026: Cached-file TTL cleanup
- UFB-0025: Themed download file server
- UFB-0024: Configurable log level
- UFB-0023: Per-platform rewrite toggles
- UFB-0022: Configurable mirror domains
- UFB-0021: Environment-based configuration
- UFB-0020: In-process bot polling
- UFB-0019: REST URL-processing endpoint
- UFB-0018: Persistent cookie jar
- UFB-0017: Cookie file merging
- UFB-0016: Download caching
- UFB-0015: yt-dlp media download
- UFB-0014: Markdown reply formatting
- UFB-0013: Download-failure fallback
- UFB-0012: YouTube mirror rewrites
- UFB-0011: Platform mirror-domain rewrites
- UFB-0010: Mirror link for disallowed domains
- UFB-0009: Download allow-list
- UFB-0008: Query-string stripping
- UFB-0007: Redirect resolution
- UFB-0006: URL validation errors
- UFB-0005: Reply-to-bot easter egg
- UFB-0004: Group-chat quietness
- UFB-0003: Private-chat no-URL prompt
- UFB-0002: Multi-URL message scanning
- UFB-0001: `/start` greeting
