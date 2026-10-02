# Bugs & debt

Defects, quirks, tech debt, and chores on already-shipped behavior. New, not-yet-built behavior goes in `docs/TODO.md` instead. Entries are deleted when fixed (the fix gets a `docs/CHANGELOG.md` bullet); IDs are never reused or renumbered, so deletions leave gaps. (BUG-0065 was allocated but never recorded here or in `CHANGELOG.md` — left as a gap rather than reused, per the policy above.)

Next free ID: **BUG-0081**.

Each entry ends with a `[P#/D#]` marker:

```text
Priority:   P1 = high     P2 = medium   P3 = low
Difficulty: D1 = trivial  D2 = small    D3 = medium   D4 = large
```

## Bugs

Automation/behavior misbehaving today.

### Bot / entrypoint

- #BUG-0006 blocking network/CPU calls run directly on the asyncio event loop — the redirect-following `requests.head()` (`app/url_processing.py:49`) and yt-dlp's `ydl.download()` (`app/download.py:74-84`) are both synchronous calls invoked from `async def` functions with no `run_in_executor`/thread offload. A single slow redirect or large download blocks the whole process, since the FastAPI event loop and the Telegram polling loop share one thread — one user's request stalls every other in-flight request. Run both via `loop.run_in_executor(None, ...)` or switch to async-native clients (`httpx.AsyncClient`) [P2/D3]
- #BUG-0076 a local-mode native video send can fail with `Bad Request: invalid file HTTP URL specified: URL host is empty` (`app/bot.py`'s `_reply_with_video`) even for a file confirmed — live, in the same failing container — to exist, be readable, and resolve correctly when the exact same request shape is replayed by hand against the real local `telegram-bot-api` server. Root cause undiagnosed: direct reproduction couldn't isolate it, because the local server validates `chat_id` before it resolves the `video` field, so every safe reproduction attempt (necessarily against a fake chat id) short-circuited on "chat not found" before ever reaching file resolution, and re-sending to a real chat wasn't an option for debugging. Currently masked by a retry (attempt the local path once, then a real upload) rather than fixed — see [UFB-0036](features/UFB-0036-native-video-replies.md#local-path-send-failures). If it recurs with a pattern (file size, filename shape, timing relative to download completion, server load), narrow it from there [P2/D3]

### Downloads / cache

### Previews

- #BUG-0062 [UFB-0035](features/UFB-0035-per-file-preview-images.md)'s frame extraction always grabs a fixed timestamp, so a black frame or a fade-in produces a useless preview for some clips. Consider a smarter pick (skip near-black frames, sample a few candidates) if this turns out to be common in practice [P3/D3]
- #BUG-0063 [UFB-0035](features/UFB-0035-per-file-preview-images.md)'s `generate_preview` runs synchronously inside `attempt_download` (`app/url_processing.py`), adding an `ffmpeg` invocation to the reply latency of every successful download. Move it off the request path (background task, or lazy generation on first `/preview/<file>` request) if this latency matters in practice [P3/D2]

### Deploy / infra

- #BUG-0012 the unauthenticated API is an SSRF-capable open proxy — `POST /process_url/` (`app/api.py:11-24`) takes an arbitrary string URL with no auth or rate limit, and `follow_redirects()` (`app/url_processing.py:47-66`) issues a server-side `HEAD` request to it. It can be used to probe internal/link-local addresses (e.g. cloud metadata endpoints) and enumerate reachability of internal hosts. The bot path is safer since `URLMessage.url: HttpUrl` (`app/models.py:6`) validates the URL, but the API's `URLRequest.url: str` (`app/api.py:12`) does not. Validate `URLRequest.url` as `HttpUrl` too, block private/link-local/loopback ranges before outbound requests, and add auth/rate limiting [P2/D3]

## Tech debt

Complexity, cleanup, and missing coverage in shipped behavior.

### Business logic

Design intent, confirmed against `process_url_request`'s decision tree: `DOWNLOAD_ALLOWED_DOMAINS` gates real `yt-dlp` downloads only — empty means every domain is allowed, the default. Mirror-link rewriting is a separate, independent gate, `REWRITE_ALLOWED_DOMAINS` (see [UFB-0023](features/UFB-0023-rewrite-domain-allowlist.md)) — empty there also means every platform is rewritten. Neither list affects the other, and YouTube is no longer special-cased: it is subject to both gates exactly like every other platform (2026-08-22).

- #BUG-0034 the platform/YouTube rewrite rules in `apply_rewrite_map` (`app/url_processing.py`) are a hardcoded list of `(regex, replacement)` tuples, one per platform — adding a new mirror site means editing code. Consider making rewrite rules dynamically configurable, e.g. an operator-supplied list of `{match_regex, mirror_domain}` rules (via env var or config file) instead of one Python tuple per platform [P3/D3]
- #BUG-0035 evaluate [cobalt](https://github.com/imputnet/cobalt) as an alternative (or additional) downloader to `yt-dlp` (`app/download.py`) — cobalt runs as its own API service, which could simplify per-platform quirks currently handled via cookie merging and yt-dlp extractor options, but would add a network dependency (or a second container) instead of the current in-process `yt-dlp` call [P3/D3]
- #BUG-0036 split the "head" (bot/API request handling) role from the "downloader" role into separate processes/services, with queue management between them — currently `attempt_download` runs `yt-dlp` synchronously in-process (`app/url_processing.py`), so a slow or stuck download blocks the request path with no queueing, concurrency limits, or backpressure. Introduce a job queue (e.g. a task queue or message broker) so the head enqueues download work and one or more separate downloader workers process it [P2/D4]

### Config (`app/config.py`)

### Code structure

### Docker / Deploy

### Cookie handling (`app/download.py`)

## Chores

Maintenance work — CI, dependencies, test/doc hygiene — with no runtime behavior impact.

### Tooling / CI

- #BUG-0078 the `markdownfmt` pre-commit hook (`language: golang`) fails to install with `error obtaining VCS status: exit status 128` on any machine where `$HOME` is itself a git working tree (e.g. a dotfiles repo checked out at `~`) — Go's build-VCS-stamping walks up from pre-commit's placeholder module directory, finds that `.git`, and errors instead of skipping it. Doesn't affect CI (runner `$HOME` isn't a git repo) or a normal checkout-only machine. Workaround: export `GOFLAGS=-buildvcs=false` before running `pre-commit`. Fix upstream would be pre-commit passing `-buildvcs=false` itself for its own placeholder `go install ./...` call [P3/D2]

### Dependencies (`pyproject.toml`)

### Tests

- #BUG-0051 import-time side effects still make parts of the app hard to test cleanly — `Bot(...)` /`Dispatcher()` run at import time in `app/bot.py:16-17`, and `settings = Settings()` runs at import time in `app/config.py:53`. `tests/conftest.py` now works around the resulting collection failure with `os.environ.setdefault("BOT_TOKEN", ...)` before any `app.*` import, which is sufficient for the test suite, but a factory function (e.g. `create_bot()` called from `main.py`) or lazy initialization would remove the need for that workaround entirely [P2/D3]

### Docs

- #BUG-0059 an `ADMIN_CHAT_ID` environment variable is set in the maintainer's local `.env` but is never read anywhere in `app/`, never mentioned in `README.md`, and never passed through `docker-compose.yml`. Either it's a leftover from a removed/never-finished feature (e.g. error reporting to an admin chat) and should be dropped from `.env`, or it's an undocumented planned feature that should be implemented and documented [P3/D1]
- #BUG-0080 `UFB-0039` relies on yt-dlp's private `TikTokIE._extract_web_data_and_status` to read a photo post's images; a yt-dlp refactor may break it. Isolated in `app.download._tiktok_item` [P3/D2]
