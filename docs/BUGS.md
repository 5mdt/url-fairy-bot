# Bugs & debt

Defects, quirks, tech debt, and chores on already-shipped behavior. New, not-yet-built
behavior goes in `docs/TODO.md` instead. Entries are deleted when fixed (the fix gets a
`docs/CHANGELOG.md` bullet); IDs are never reused or renumbered, so deletions leave gaps.
Next free ID: **BUG-0077**. (BUG-0065 was allocated but never recorded here or in
`CHANGELOG.md` — left as a gap rather than reused, per the policy above.)

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
- #BUG-0068 `_deliver_result`'s final fallback (`message.reply(text, ...)`, `app/bot.py`, run after
  a declined/failed native video attempt) is unguarded, and `handle_message` only catches
  `ValidationError`. If that `reply` itself raises for any reason (a transient network error, a
  malformed `text`), the exception escapes `handle_message` entirely and the user gets no reply at
  all — contradicting `_deliver_result`'s own stated goal ("never a new way to fail outright").
  Wrap `handle_message`'s per-URL body in a broader `except Exception`, or guard the final `reply`
  directly [P3/D1]
- #BUG-0070 `_fits_native_send`'s docstring (`app/bot.py`) says the mid tier gates on which backend
  is *currently active* ("whatever backend is active — cloud, or a dead local server — has no
  business being handed a file this size"), but the code only checks
  `is_telegram_api_reachable()`, which says nothing about which backend is active for polling right
  now. `UFB-0036-native-video-replies.md` documents the reachability-only behavior as deliberate, so
  the docstring is the stale one. Practical effect: after the local server recovers, there's up to a
  `_BACKEND_CHECK_INTERVAL_SECONDS` window where the bot is still polling on the cloud API but
  `_fits_native_send` already returns `True` for a large file — the send then fails and falls back
  to text, so no crash, just a silent extra attempt/failure. Fix the docstring, or gate on the active
  backend as documented [P3/D1]
- #BUG-0075 `start_polling()` (`app/bot.py`) runs `is_telegram_api_reachable()` — a blocking
  socket connect, up to its 1s timeout — directly on the event loop, before any coroutine has
  started running. Startup-only and small, but every other call site (`/health`,
  `_fits_native_send`) correctly offloads it via `asyncio.to_thread`; this one should too for
  consistency [P4/D1]
- #BUG-0069 `CLOUD_SEND_VIDEO_MAX_MB` defaults to `10`, silently lowering the native-video-send
  ceiling from the earlier `SEND_VIDEO_MAX_MB`'s default of `50` for every deployment that doesn't
  configure a local Bot API server (`docs/CHANGELOG.md`'s UFB-0036 entry documents the old default
  but not this as a regression). Telegram's cloud API itself allows up to 50 MB; a 10–50 MB file now
  arrives as a text link instead of a native video on a stock deployment. `docker-compose.yml`'s
  comment on the `telegram-bot-api` service ("raising the video-send ceiling above the cloud API's
  50 MB") still reads as though 50 is the live default. Either default `CLOUD_SEND_VIDEO_MAX_MB` to
  `50`, or call the lower default out explicitly in `README.md`/`.env.example` as an intentional
  behavior change [P3/D1]
- #BUG-0076 a local-mode native video send can fail with `Bad Request: invalid file HTTP URL
  specified: URL host is empty` (`app/bot.py`'s `_reply_with_video`) even for a file confirmed —
  live, in the same failing container — to exist, be readable, and resolve correctly when the exact
  same request shape is replayed by hand against the real local `telegram-bot-api` server. Root
  cause undiagnosed: direct reproduction couldn't isolate it, because the local server validates
  `chat_id` before it resolves the `video` field, so every safe reproduction attempt (necessarily
  against a fake chat id) short-circuited on "chat not found" before ever reaching file resolution,
  and re-sending to a real chat wasn't an option for debugging. Currently masked by a retry (attempt
  the local path once, then a real upload) rather than fixed — see
  [UFB-0036](features/UFB-0036-native-video-replies.md#local-path-send-failures). If it recurs with
  a pattern (file size, filename shape, timing relative to download completion, server load), narrow
  it from there [P2/D3]

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
### Previews

- #BUG-0062 [UFB-0035](features/UFB-0035-per-file-preview-images.md)'s frame extraction always
  grabs a fixed timestamp, so a black frame or a fade-in produces a useless preview for some
  clips. Consider a smarter pick (skip near-black frames, sample a few candidates) if this turns
  out to be common in practice [P3/D3]
- #BUG-0063 [UFB-0035](features/UFB-0035-per-file-preview-images.md)'s `generate_preview` runs
  synchronously inside `attempt_download` (`app/url_processing.py`), adding an `ffmpeg` invocation
  to the reply latency of every successful download. Move it off the request path (background
  task, or lazy generation on first `/preview/<file>` request) if this latency matters in practice
  [P3/D2]
- #BUG-0071 `tests/preview_test.py` fully mocks `subprocess.run`, so the only guard against a
  BUG-0066-class regression (ffmpeg silently rejecting the invocation's actual args) is an argv
  assertion (`-f`/`mjpeg` present). A future change to the ffmpeg args that ffmpeg itself rejects
  would pass this suite the same way BUG-0066 did. Add at least one test that runs real `ffmpeg`
  against a tiny fixture clip, skipped when the binary isn't available [P3/D2]

### Deploy / infra

- #BUG-0067 the generated 404 page (`app/pages.py:render_404_page`,
  [UFB-0033](features/UFB-0033-static-page-generation.md)) is never actually served —
  verified live: `GET /watch/<unknown file>.html` returns stock nginx's default 404 body, not
  `CACHE_DIR/404.html`. Both `docker-compose.yml` and the deployed stack run
  `nginx:stable-alpine-slim` with no custom config anywhere in the repo, so `error_page 404
  /404.html;` is never set — contradicting [UFB-0025](features/UFB-0025-themed-download-file-server.md)/
  [UFB-0033](features/UFB-0033-static-page-generation.md)'s documented behavior. Add an
  `error_page` directive via a mounted `nginx.conf` (or switch to an image that supports one via
  env/template) [P3/D2]
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

- #BUG-0043 the container runs as root (no `USER` directive in `Dockerfile`). Add a non-root user
  [P2/D2]
- #BUG-0074 `docker-compose.yml`'s `telegram-bot-api` service carries a redundant explicit
  `networks: [default]` — `default` is already the implicit network for every service that doesn't
  declare one. Separately, `app`'s `CACHE_DIR` is env-overridable (`${CACHE_DIR:-...}`) while its
  volume mount (`cache:/tmp/url-fairy-bot-cache/`) is hardcoded — an operator who overrides
  `CACHE_DIR` silently breaks the assumption that `app` and `telegram-bot-api` share one path for
  local-mode file sends. Drop the redundant `networks:` key; document (or derive) the mount path
  from `CACHE_DIR` [P4/D1]

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
- #BUG-0064 `isort` and `black` disagree on multi-line import wrapping — neither `pyproject.toml`
  nor any `.isort.cfg` sets `profile = "black"` (or equivalent `black`-compatible options), so
  `make fmt`'s `isort` step (`app/cleanup.py`'s multi-name import, observed 2026-09-09) can produce
  a wrap `black` would then reformat differently, making `make fmt` non-idempotent. Add
  `[tool.isort] profile = "black"` to `pyproject.toml` [P3/D1]

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
  `app/messages.py`/`app/templates/messages/`, and it still shows Markdown-style `[text](url)`
  links even though replies are now HTML (UFB-0037). Nothing in the test suite loads this file.
  Either wire it into a real parametrized test or delete it [P3/D1]
- #BUG-0072 `tests/bot_test.py` no longer passes `black --check` (it was clean at the prior commit;
  the new multi-context `with (patch(...), patch(...)):` blocks in the UFB-0036 tests are
  black-formatted for a Python target newer than this repo's, and mixed with the
  older-style two-`with` form elsewhere in the same file). Not CI-enforced today — black/isort/
  flake8 are all scoped to `./app` only, in both `.pre-commit-config.yaml` and the GitHub Actions
  workflows (see BUG-0064) — but it's a regression in what was a clean file. Run `black`/`isort`
  against `./tests` too, or expand their scope in CI [P4/D1]
- #BUG-0073 UFB-0036 test coverage has a couple of gaps against its own documented test list
  (`UFB-0036-native-video-replies.md`): no assertion that `_reply_with_video` actually passes a
  `thumbnail` kwarg (`test_reply_with_video_sends_with_probe_info` checks width/height/duration/
  caption only); and no end-to-end test through `handle_message` for a mid-tier size that
  `_fits_native_send` *declines* (only the send-*failure* path is covered) [P4/D1]

### Docs

- #BUG-0058 the README's "Example Response" for the REST API
  (`{"status": "success", "data": "https://example.com/processed-url"}`) doesn't match the actual
  response shape produced by `process_url_request` (an HTML string with emoji and `<a href="...">`
  links, rendered via `app/messages.py`, UFB-0037) — misleading for anyone integrating against the
  API from the docs alone [P3/D1]
- #BUG-0059 an `ADMIN_CHAT_ID` environment variable is set in the maintainer's local `.env` but is
  never read anywhere in `app/`, never mentioned in `README.md`, and never passed through
  `docker-compose.yml`. Either it's a leftover from a removed/never-finished feature (e.g. error
  reporting to an admin chat) and should be dropped from `.env`, or it's an undocumented planned
  feature that should be implemented and documented [P3/D1]
