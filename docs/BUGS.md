# Bugs & debt

Defects, quirks, tech debt, and chores on already-shipped behavior. New, not-yet-built
behavior goes in `docs/TODO.md` instead. Entries are deleted when fixed (the fix gets a
`docs/CHANGELOG.md` bullet); IDs are never reused or renumbered, so deletions leave gaps.
Next free ID: **BUG-0062**.

Each entry ends with a `[P#/D#]` marker:

```text
Priority:   P1 = high     P2 = medium   P3 = low
Difficulty: D1 = trivial  D2 = small    D3 = medium   D4 = large
```

## Bugs & quirks

Automation/behavior misbehaving today.

### Bot / entrypoint

- #BUG-0006 blocking network/CPU calls run directly on the asyncio event loop — the
  redirect-following `requests.head()` (`app/url_processing.py:49`) and yt-dlp's `ydl.download()`
  (`app/download.py:74-84`) are both synchronous calls invoked from `async def` functions with no
  `run_in_executor`/thread offload. A single slow redirect or large download blocks the whole
  process, since the FastAPI event loop and the Telegram polling loop share one thread — one user's
  request stalls every other in-flight request. Run both via `loop.run_in_executor(None, ...)` or
  switch to async-native clients (`httpx.AsyncClient`) [P2/D3]
- #BUG-0016 Markdown replies can still break Telegram's parser for URLs — the reply-to-bot shrug
  text itself is correct today (`"¯\\_(ツ)_/¯"`, `app/bot.py:37`), but every `[text](url)` link built
  from a `final_url`/`modified_url` (`app/url_processing.py:157,184,189-190,196-198,213-215`) is
  still an unescaped f-string, so any URL containing `)` or `_` (common in TikTok/Instagram share
  links) breaks the surrounding Markdown link syntax. Telegram either mangles the message or rejects
  `sendMessage` outright (`can't parse entities`), so the bot silently fails to reply for an
  otherwise-successful request. Escape user-derived URL text, or switch to `MarkdownV2`/HTML with
  proper escaping [P2/D2]

### Downloads / cache

- #BUG-0014 cache filenames are unbounded and non-deduplicated — the output filename
  (`app/download.py:56-57,112-113`, `sanitize_subfolder_name`) is the *entire* input URL with
  non-alphanumeric characters replaced by `_`, with no length cap and no lock/mutex around "does
  this file already exist" (`:59-61`). A sufficiently long URL can exceed the filesystem's
  ~255-byte filename limit and raise `OSError`; two concurrent requests for the same
  not-yet-cached URL both start a download. (The public `/cache/` listing that used to make these
  URL-derived filenames browsable, and the missing `CACHE_DIR` creation, are both gone — see
  [UFB-0031](features/UFB-0031-landing-page-and-cache-index.md) and
  [UFB-0033](features/UFB-0033-static-page-generation.md).) Hash the URL (e.g. truncated sha256)
  instead of transliterating it, and add an `asyncio.Lock` per in-flight URL [P2/D2]
- #BUG-0015 downloaded files are always saved with a `.mp4` extension — `outtmpl`
  (`app/download.py:57,64-67`) is hardcoded to end in `.mp4` while `"format": "best"` lets yt-dlp
  choose whatever container the best available stream is in (webm, mkv, etc.), and the Docker image
  installs no `ffmpeg`, so yt-dlp can't remux/merge into a real `.mp4` when needed. Files are
  frequently mislabeled and can fail to play in strict players/browsers. Now that
  [UFB-0032](features/UFB-0032-telegram-instant-view-embeds.md)'s `/watch/<file>` page declares
  `og:video:type: video/mp4` unconditionally, a mislabeled file also fails to play in Telegram's
  inline preview card, not just in strict browsers. Let yt-dlp choose the real
  extension (`%(ext)s`) and install `ffmpeg` if format merging is desired [P3/D2]
- #BUG-0030 seeded permanent pages only survive until the next TTL sweep — `seed_static_pages`
  (`app/pages.py`) writes the landing page, 404 page, and the Instant View sample clip/page into
  `CACHE_DIR` at startup only ([UFB-0033](features/UFB-0033-static-page-generation.md)), and the
  cron cleanup (`docker-compose.yml`) deletes anything in `CACHE_DIR` older than `FILE_TTL` with no
  exemption. On a long-running deployment that isn't restarted within `FILE_TTL` days, `/`,
  the 404 page, and the registered Instant View sample URL all start 404ing until the app next
  restarts. Exclude the seeded filenames from the cleanup `find`, or have the app re-seed on an
  interval instead of only at startup [P2/D2]
- #BUG-0061 large downloads don't render in Telegram's `og:video`/Instant View player —
  reported against a 34 MB cached file (confirmed via `HEAD`: `content-length: 35818823`,
  `content-type: video/mp4`, `accept-ranges: bytes`, so the file itself and its response headers
  are correct) whose `/watch/<file>.html` page ([UFB-0032](features/UFB-0032-telegram-instant-view-embeds.md))
  has structurally correct `og:video`/`twitter:player:stream` tags, yet Telegram shows no inline
  player — only the plain download link works. No official Telegram documentation states an exact
  `og:video`/Instant View size cutoff; a ~10 MB threshold is commonly cited informally but
  unconfirmed. Reproduce with a range of file sizes to find where playback actually breaks, then
  either transcode/cap downloads above that size or fall back to a plain (non-video) watch page
  for files over the threshold [P2/D3]

### Deploy / infra

- #BUG-0010 `cleanup.sh` (repo root, 207 lines) is a complete, argument-parsing, env-validating
  cache-cleanup script — more correct than the inline `cron` service's `find` one-liner, which now
  relies on `restart: unless-stopped` re-running it every ~60 minutes after `sleep 60m` exits the
  container, rather than looping internally. Note the double slash in
  `/tmp/url-fairy-bot-cache//`, and that `FILE_TTL` is commented `#days` in `docker-compose.yml`
  but treated as **seconds** by `cleanup.sh:135` — the two cleanup mechanisms disagree on units.
  `cleanup.sh` itself is never `COPY`'d into the Docker image and no compose service invokes it,
  so it has no effect at runtime. Either wire it into the `cron` service (`entrypoint: ["/cleanup.sh",
  "--serve"]`, resolving the unit mismatch in the process) or remove it if superseded [P3/D2]
- #BUG-0012 the unauthenticated API is an SSRF-capable open proxy — `POST /process_url/`
  (`app/api.py:11-24`) takes an arbitrary string URL with no auth or rate limit, and
  `follow_redirects()` (`app/url_processing.py:47-66`) issues a server-side `HEAD` request to it.
  It can be used to probe internal/link-local addresses (e.g. cloud metadata endpoints) and
  enumerate reachability of internal hosts. The bot path is safer since `URLMessage.url: HttpUrl`
  (`app/models.py:6`) validates the URL, but the API's `URLRequest.url: str` (`app/api.py:12`) does
  not. Validate `URLRequest.url` as `HttpUrl` too, block private/link-local/loopback ranges before
  outbound requests, and add auth/rate limiting [P2/D3]

## Tech debt

Complexity, cleanup, and missing coverage in shipped behavior.

### Business logic

Design intent, confirmed against `process_url_request`'s decision tree: `DOWNLOAD_ALLOWED_DOMAINS`
gates real `yt-dlp` downloads only — empty means every domain is allowed, the default. Mirror-link
rewriting is a separate, independent gate, `REWRITE_ALLOWED_DOMAINS` (see
[UFB-0023](features/UFB-0023-rewrite-domain-allowlist.md)) — empty there also means every platform
is rewritten. Neither list affects the other, and YouTube is no longer special-cased: it is subject
to both gates exactly like every other platform (2026-08-22).

- #BUG-0031 Instagram is the only mirror platform scoped to specific paths — `apply_rewrite_map`
  (`app/url_processing.py`) matches Spotify/Reddit/TikTok/Twitter/YouTube against their whole
  domain, but Instagram only against `/p/` and `/reel/`. A plain Instagram profile or story link
  therefore gets no mirror treatment at all, unlike every other platform. Either document why
  Instagram is deliberately narrower or widen it to the domain-wide pattern used for the rest
  [P3/D1]
- #BUG-0032 Spotify has no yt-dlp extractor, so if an operator ever allow-lists `spotify.com` for
  real downloads, every request pays for a full `yt-dlp` startup and failure
  (`attempt_download` → `UnsupportedUrlError`, `app/url_processing.py`) before falling back
  to the mirror link — pure overhead with no chance of succeeding. Special-case Spotify (and any
  other known non-video platform) to skip the download attempt and go straight to the mirror
  rewrite [P3/D2]
- #BUG-0033 the download-failure fallback overclaims an "alternative" that isn't one —
  `process_url_request`'s reply when `modified_url == final_url` after a download failure
  (`app/url_processing.py:212-216`) still says "Here is an alternative link, which Telegram may
  parse better," even though the link offered is byte-for-byte identical to the original. Either
  drop the "alternative" framing for this case or state plainly that the download failed [P3/D1]
- #BUG-0034 the platform/YouTube rewrite rules in `apply_rewrite_map` (`app/url_processing.py`)
  are a hardcoded list of `(regex, replacement)` tuples, one per platform — adding a new mirror
  site means editing code. Consider making rewrite rules dynamically configurable, e.g. an
  operator-supplied list of `{match_regex, mirror_domain}` rules (via env var or config file)
  instead of one Python tuple per platform [P3/D3]
- #BUG-0035 evaluate [cobalt](https://github.com/imputnet/cobalt) as an alternative (or
  additional) downloader to `yt-dlp` (`app/download.py`) — cobalt runs as its own API service,
  which could simplify per-platform quirks currently handled via cookie merging and yt-dlp
  extractor options, but would add a network dependency (or a second container) instead of the
  current in-process `yt-dlp` call [P3/D3]
- #BUG-0036 split the "head" (bot/API request handling) role from the "downloader" role into
  separate processes/services, with queue management between them — currently `attempt_download`
  runs `yt-dlp` synchronously in-process (`app/url_processing.py`), so a slow or stuck download
  blocks the request path with no queueing, concurrency limits, or backpressure. Introduce a job
  queue (e.g. a task queue or message broker) so the head enqueues download work and one or more
  separate downloader workers process it [P2/D4]

### Config (`app/config.py`)

- #BUG-0037 every field hand-rolls its own `os.getenv(...)` default instead of letting
  `pydantic_settings.BaseSettings` read the environment itself. This mostly works in practice —
  `tests/config_test.py` confirms that when an env var *is* set, pydantic-settings' own env source
  still overrides the hand-rolled default and applies pydantic's stricter coercion/validation (a
  bad `COOKIE_JAR_ENABLED` value raises `pydantic.ValidationError` at startup, it does not silently
  default to `True` as an earlier version of this doc assumed) — but the pattern is still redundant
  with what `BaseSettings` already does, and the class-level `os.getenv(...)` default is frozen at
  import time regardless. Use plain typed fields (`BOT_TOKEN: str = ""`) [P3/D2]
- #BUG-0038 `LOG_LEVEL` (`app/config.py:37`) isn't validated against the documented set (`DEBUG`,
  `INFO`, `WARNING`, `ERROR`) — an unrecognized value reaches `logging.basicConfig`
  (`app/main.py:16`) and raises `ValueError` there instead of failing with a clear configuration
  error at the point the setting is read. Restrict the field to a `Literal` of the documented
  levels [P3/D1]

### Code structure

- #BUG-0039 `sanitize_subfolder_name` (`app/download.py:112-113`) is named as if it produces a
  subfolder but actually produces a filename; rename for clarity [P3/D1]
- #BUG-0040 `attempt_download`'s success-path reconstruction of the filename
  (`os.path.join(*video_os_path.split(os.path.sep)[-1:])`, `app/url_processing.py:156`) is a
  convoluted way to write `os.path.basename(video_os_path)` [P3/D1]
- #BUG-0041 `is_domain_allowed`, `is_rewrite_allowed`, and `follow_redirects`
  (`app/url_processing.py`) each re-derive `urlparse(...)` multiple times on the same string;
  minor, but worth consolidating now that the allow-list matching itself is correct [P3/D1]

### Docker / Deploy

- #BUG-0042 `uv sync --no-dev --no-editable` (`Dockerfile:16`) runs *before* `COPY ./app /app/app`
  (`:19`), so the project's own package is installed empty/stale; the app only works at all because
  `ENV PYTHONPATH="/app"` makes the later-copied `app/` importable directly, bypassing the
  installed (empty) distribution. Reorder the `COPY`s or accept that `uv sync` is only installing
  third-party deps (fine, but worth a comment) [P3/D1]
- #BUG-0043 the container runs as root (no `USER` directive in `Dockerfile`). Add a non-root user
  [P2/D2]

### Cookie handling (`app/download.py`)

- #BUG-0044 once `COOKIE_JAR_PATH` (`cookie_jar.txt`) exists, it is never refreshed from
  `cookies*.txt` again (`_resolve_cookie_path`, `app/download.py:37-45`) — rotating/updating
  cookies requires an operator to manually delete the jar file. Document this clearly (or add a
  periodic refresh/merge) [P3/D2]
- #BUG-0045 the comment-stripping filter in `_write_merged_cookies`
  (`not line.startswith("# ") and line.strip() != "#"`, `app/download.py:31`) is subtle — it keeps
  lines starting with a single `#` but no space, which is how Netscape cookie files often mark the
  `HttpOnly` prefix (`#HttpOnly_domain...`). `tests/download_test.py` now covers this behavior, but
  the code itself still has no comment explaining the intent — worth adding one [P3/D1]

### Cron / Cleanup

- #BUG-0046 rewrite the cleanup cron task to monitor file access time (not just mtime/age since
  creation) and delete files from the download directory once they've gone untouched longer than a
  configurable TTL, instead of whatever criteria the current task uses [P3/D2]

## Chores

Maintenance work — CI, dependencies, test/doc hygiene — with no runtime behavior impact.

### Tooling / CI

- #BUG-0047 three overlapping/inconsistent linters are configured: `.flake8` (not run in CI — no
  flake8 job exists, only referenced from `.pre-commit-config.yaml`), a black CI job
  (`lint-python-black.yml`), a ruff CI job (`lint-python-ruff.yml`) with no `ruff` configuration
  anywhere in `pyproject.toml`, and pre-commit running black + isort + flake8 + pytest. Consolidate
  onto one tool (e.g. `ruff format` + `ruff check`, which subsumes flake8/isort/black) and delete
  the rest [P2/D3]
- #BUG-0048 no GitHub Actions workflow runs `pytest` — it only runs via the local `pre-commit`
  hook (`.pre-commit-config.yaml`'s `run-pytest`), which is opt-in per contributor. Add a CI
  workflow (e.g. `.github/workflows/test-python.yml`) so the suite actually gates merges [P1/D2]
- #BUG-0049 `.pre-commit-config.yaml`'s `name-tests-test` hook expects `test_*.py` naming, but
  every test file in the repo uses the `*_test.py` suffix (`api_test.py`, `bot_test.py`,
  `config_test.py`, `download_test.py`, `url_processing_test.py`) — this hook must be failing (or
  was never actually run) since the tests were added [P3/D1]

### Dependencies (`pyproject.toml`)

- #BUG-0050 `pyyaml` is a runtime dependency (`pyproject.toml:18`) but nothing under `app/`
  imports `yaml` (only `tests/test_messages.yml` exists, and it's not loaded by any test — see
  Tests section). Drop it, or move it to the `dev` group if it's meant for future fixture loading
  [P3/D1]

### Tests

- #BUG-0051 import-time side effects still make parts of the app hard to test cleanly — `Bot(...)`
  /`Dispatcher()` run at import time in `app/bot.py:16-17`, and `settings = Settings()` runs at
  import time in `app/config.py:53`. `tests/conftest.py` now works around the resulting collection
  failure with `os.environ.setdefault("BOT_TOKEN", ...)` before any `app.*` import, which is
  sufficient for the test suite, but a factory function (e.g. `create_bot()` called from
  `main.py`) or lazy initialization would remove the need for that workaround entirely [P2/D3]
- #BUG-0052 no coverage measurement — no `pytest-cov` (or equivalent) in the dev dependency
  group, no coverage threshold, no report published from CI, so any remaining gaps are invisible to
  contributors until manually audited [P3/D2]
- #BUG-0053 `pytest.ini`'s `addopts = --ignore=lib/python3.11/site-packages` refers to a
  pre-`uv` venv layout (`lib/`) that no longer exists now that the project uses `.venv/` — dead
  option, safe to remove [P3/D1]
- #BUG-0054 `httpx<0.28` and `pytest-asyncio<0.25` (`pyproject.toml`) are still pinned as if
  `tests/api_test.py` used the deprecated `AsyncClient(app=app, ...)` constructor, but it already
  uses the modern `ASGITransport` — `AsyncClient(transport=ASGITransport(app=app), ...)`. The pins
  look like leftovers from before that migration; verify current `httpx`/`pytest-asyncio` majors
  work and drop the upper bounds [P3/D1]
- #BUG-0055 `pytest.ini` does not set `asyncio_mode` (relies on `pytest.mark.asyncio` per-test,
  which is fine, but worth being explicit given `pytest-asyncio`'s strict/auto mode footguns)
  [P3/D1]
- #BUG-0056 `tests/test_messages.yml` is a stale manual fixture file: it references
  `ddinstagram.com` (current mirror default is `kkinstagram.com`, `app/config.py:42`) and reply
  text ("I failed to download the file by myself") that no longer matches any string in
  `app/url_processing.py`. Nothing in the test suite loads this file. Either wire it into a real
  parametrized test or delete it [P3/D1]

### Docs

- #BUG-0058 the README's "Example Response" for the REST API
  (`{"status": "success", "data": "https://example.com/processed-url"}`) doesn't match the actual
  response shape produced by `process_url_request` (a Markdown string with emoji and
  `[text](url)` links, per `tests/test_messages.yml`'s captured examples) — misleading for anyone
  integrating against the API from the docs alone [P3/D1]
- #BUG-0059 an `ADMIN_CHAT_ID` environment variable is set in the maintainer's local `.env` but is
  never read anywhere in `app/`, never mentioned in `README.md`, and never passed through
  `docker-compose.yml`. Either it's a leftover from a removed/never-finished feature (e.g. error
  reporting to an admin chat) and should be dropped from `.env`, or it's an undocumented planned
  feature that should be implemented and documented [P3/D1]
- #BUG-0060 `CLAUDE.md` requires "FRD feature id must be added to functions as comments for easier
  tracking," but the codebase barely follows it — only one `UFB-` reference exists under `app/`
  (`app/url_processing.py:19`, and it points at a doc, not a function). Either add the ID comments
  the convention calls for across `app/`, or drop the rule from `CLAUDE.md` if it isn't meant to be
  enforced [P3/D2]
