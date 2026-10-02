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

- #BUG-0014 cache filenames are unbounded and non-deduplicated — the output filename (`app/download.py:56-57,112-113`, `sanitize_subfolder_name`) is the *entire* input URL with non-alphanumeric characters replaced by `_`, with no length cap and no lock/mutex around "does this file already exist" (`:59-61`). A sufficiently long URL can exceed the filesystem's ~255-byte filename limit and raise `OSError`; two concurrent requests for the same not-yet-cached URL both start a download. (The public `/cache/` listing that used to make these URL-derived filenames browsable, and the missing `CACHE_DIR` creation, are both gone — see [UFB-0031](features/UFB-0031-landing-page-and-cache-index.md) and [UFB-0033](features/UFB-0033-static-page-generation.md).) Hash the URL (e.g. truncated sha256) instead of transliterating it, and add an `asyncio.Lock` per in-flight URL [P2/D2]

### Previews

- #BUG-0062 [UFB-0035](features/UFB-0035-per-file-preview-images.md)'s frame extraction always grabs a fixed timestamp, so a black frame or a fade-in produces a useless preview for some clips. Consider a smarter pick (skip near-black frames, sample a few candidates) if this turns out to be common in practice [P3/D3]
- #BUG-0063 [UFB-0035](features/UFB-0035-per-file-preview-images.md)'s `generate_preview` runs synchronously inside `attempt_download` (`app/url_processing.py`), adding an `ffmpeg` invocation to the reply latency of every successful download. Move it off the request path (background task, or lazy generation on first `/preview/<file>` request) if this latency matters in practice [P3/D2]
- #BUG-0071 `tests/preview_test.py` fully mocks `subprocess.run`, so the only guard against a BUG-0066-class regression (ffmpeg silently rejecting the invocation's actual args) is an argv assertion (`-f`/`mjpeg` present). A future change to the ffmpeg args that ffmpeg itself rejects would pass this suite the same way BUG-0066 did. Add at least one test that runs real `ffmpeg` against a tiny fixture clip, skipped when the binary isn't available [P3/D2]

### Deploy / infra

- #BUG-0067 the generated 404 page (`app/pages.py:render_404_page`, [UFB-0033](features/UFB-0033-static-page-generation.md)) is never actually served — verified live: `GET /watch/<unknown file>.html` returns stock nginx's default 404 body, not `CACHE_DIR/404.html`. Both `docker-compose.yml` and the deployed stack run `nginx:stable-alpine-slim` with no custom config anywhere in the repo, so `error_page 404 /404.html;` is never set — contradicting [UFB-0025](features/UFB-0025-themed-download-file-server.md)/ [UFB-0033](features/UFB-0033-static-page-generation.md)'s documented behavior. Add an `error_page` directive via a mounted `nginx.conf` (or switch to an image that supports one via env/template) [P3/D2]
- #BUG-0012 the unauthenticated API is an SSRF-capable open proxy — `POST /process_url/` (`app/api.py:11-24`) takes an arbitrary string URL with no auth or rate limit, and `follow_redirects()` (`app/url_processing.py:47-66`) issues a server-side `HEAD` request to it. It can be used to probe internal/link-local addresses (e.g. cloud metadata endpoints) and enumerate reachability of internal hosts. The bot path is safer since `URLMessage.url: HttpUrl` (`app/models.py:6`) validates the URL, but the API's `URLRequest.url: str` (`app/api.py:12`) does not. Validate `URLRequest.url` as `HttpUrl` too, block private/link-local/loopback ranges before outbound requests, and add auth/rate limiting [P2/D3]

## Tech debt

Complexity, cleanup, and missing coverage in shipped behavior.

### Business logic

Design intent, confirmed against `process_url_request`'s decision tree: `DOWNLOAD_ALLOWED_DOMAINS` gates real `yt-dlp` downloads only — empty means every domain is allowed, the default. Mirror-link rewriting is a separate, independent gate, `REWRITE_ALLOWED_DOMAINS` (see [UFB-0023](features/UFB-0023-rewrite-domain-allowlist.md)) — empty there also means every platform is rewritten. Neither list affects the other, and YouTube is no longer special-cased: it is subject to both gates exactly like every other platform (2026-08-22).

- #BUG-0032 Spotify has no yt-dlp extractor, so if an operator ever allow-lists `spotify.com` for real downloads, every request pays for a full `yt-dlp` startup and failure (`attempt_download` → `UnsupportedUrlError`, `app/url_processing.py`) before falling back to the mirror link — pure overhead with no chance of succeeding. Special-case Spotify (and any other known non-video platform) to skip the download attempt and go straight to the mirror rewrite [P3/D2]
- #BUG-0034 the platform/YouTube rewrite rules in `apply_rewrite_map` (`app/url_processing.py`) are a hardcoded list of `(regex, replacement)` tuples, one per platform — adding a new mirror site means editing code. Consider making rewrite rules dynamically configurable, e.g. an operator-supplied list of `{match_regex, mirror_domain}` rules (via env var or config file) instead of one Python tuple per platform [P3/D3]
- #BUG-0035 evaluate [cobalt](https://github.com/imputnet/cobalt) as an alternative (or additional) downloader to `yt-dlp` (`app/download.py`) — cobalt runs as its own API service, which could simplify per-platform quirks currently handled via cookie merging and yt-dlp extractor options, but would add a network dependency (or a second container) instead of the current in-process `yt-dlp` call [P3/D3]
- #BUG-0036 split the "head" (bot/API request handling) role from the "downloader" role into separate processes/services, with queue management between them — currently `attempt_download` runs `yt-dlp` synchronously in-process (`app/url_processing.py`), so a slow or stuck download blocks the request path with no queueing, concurrency limits, or backpressure. Introduce a job queue (e.g. a task queue or message broker) so the head enqueues download work and one or more separate downloader workers process it [P2/D4]

### Config (`app/config.py`)

- #BUG-0037 every field hand-rolls its own `os.getenv(...)` default instead of letting `pydantic_settings.BaseSettings` read the environment itself. This mostly works in practice — `tests/config_test.py` confirms that when an env var *is* set, pydantic-settings' own env source still overrides the hand-rolled default and applies pydantic's stricter coercion/validation (a bad `COOKIE_JAR_ENABLED` value raises `pydantic.ValidationError` at startup, it does not silently default to `True` as an earlier version of this doc assumed) — but the pattern is still redundant with what `BaseSettings` already does, and the class-level `os.getenv(...)` default is frozen at import time regardless. Use plain typed fields (`BOT_TOKEN: str = ""`) [P3/D2]

### Code structure

### Docker / Deploy

- #BUG-0043 the container runs as root (no `USER` directive in `Dockerfile`). Add a non-root user [P2/D2]

### Cookie handling (`app/download.py`)

## Chores

Maintenance work — CI, dependencies, test/doc hygiene — with no runtime behavior impact.

### Tooling / CI

- #BUG-0078 the `markdownfmt` pre-commit hook (`language: golang`) fails to install with `error obtaining VCS status: exit status 128` on any machine where `$HOME` is itself a git working tree (e.g. a dotfiles repo checked out at `~`) — Go's build-VCS-stamping walks up from pre-commit's placeholder module directory, finds that `.git`, and errors instead of skipping it. Doesn't affect CI (runner `$HOME` isn't a git repo) or a normal checkout-only machine. Workaround: export `GOFLAGS=-buildvcs=false` before running `pre-commit`. Fix upstream would be pre-commit passing `-buildvcs=false` itself for its own placeholder `go install ./...` call [P3/D2]

### Dependencies (`pyproject.toml`)

### Tests

- #BUG-0051 import-time side effects still make parts of the app hard to test cleanly — `Bot(...)` /`Dispatcher()` run at import time in `app/bot.py:16-17`, and `settings = Settings()` runs at import time in `app/config.py:53`. `tests/conftest.py` now works around the resulting collection failure with `os.environ.setdefault("BOT_TOKEN", ...)` before any `app.*` import, which is sufficient for the test suite, but a factory function (e.g. `create_bot()` called from `main.py`) or lazy initialization would remove the need for that workaround entirely [P2/D3]
- #BUG-0052 no coverage measurement — no `pytest-cov` (or equivalent) in the dev dependency group, no coverage threshold, no report published from CI, so any remaining gaps are invisible to contributors until manually audited [P3/D2]

### Docs

- #BUG-0059 an `ADMIN_CHAT_ID` environment variable is set in the maintainer's local `.env` but is never read anywhere in `app/`, never mentioned in `README.md`, and never passed through `docker-compose.yml`. Either it's a leftover from a removed/never-finished feature (e.g. error reporting to an admin chat) and should be dropped from `.env`, or it's an undocumented planned feature that should be implemented and documented [P3/D1]
- #BUG-0080 `UFB-0039` relies on yt-dlp's private `TikTokIE._extract_web_data_and_status` to read a photo post's images; a yt-dlp refactor may break it. Isolated in `app.download._tiktok_item` [P3/D2]
- #BUG-0079 the watch page (`app/templates/watch.html`, Instant View) for a TikTok photo post (#UFB-0039) shows none of the post's images and renders the audio track as a `<video>` block. `_attempt_gallery_download` writes the watch page for the post's `.mp3`, and the template assumes video media: `og:video`/`twitter:player` and `<video src>` point at the mp3, and the images (`CACHE_DIR/gallery/<stem>/NN.jpg`, not served by any page) are never referenced. Fix: give the template an audio/gallery mode — `<audio controls>` for the track, an `<img>` per gallery image (and `og:image` of the first), no `og:video` tags [P2/D2]
