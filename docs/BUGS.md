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

- #BUG-0006 blocking network and subprocess calls run directly on the asyncio event loop, from `async def` functions with no thread offload: the redirect-following `requests.head()` (`app/url_processing.py:87`), yt-dlp's `ydl.download()` (`app/download.py:215`), `preview.generate_preview` (`app/url_processing.py:228`, an `ffmpeg` call on every successful download; formerly #BUG-0063), and the `ffmpeg`/`ffprobe` calls in `app/media.py` (`probe`, `measure_loudness`, `normalize_if_quiet`, the last invoked at `app/download.py:220`). The FastAPI loop and the Telegram polling loop share one thread, so one slow redirect, download or transcode stalls every other in-flight request, and would freeze the refresh task for [UFB-0055](features/UFB-0055-progress-chat-action.md). Run each via `asyncio.to_thread` (as `app/bot.py` already does for `is_telegram_api_reachable`) or switch to async-native clients (`httpx.AsyncClient`). Moving previews to lazy generation on first `/preview/<file>` request is an optional extra [P1/D3]
- #BUG-0076 a local-mode native video send can fail with `Bad Request: invalid file HTTP URL specified: URL host is empty` (`app/bot.py`'s `_reply_with_video`) even for a file confirmed — live, in the same failing container — to exist, be readable, and resolve correctly when the exact same request shape is replayed by hand against the real local `telegram-bot-api` server. Root cause undiagnosed: direct reproduction couldn't isolate it, because the local server validates `chat_id` before it resolves the `video` field, so every safe reproduction attempt (necessarily against a fake chat id) short-circuited on "chat not found" before ever reaching file resolution, and re-sending to a real chat wasn't an option for debugging. Currently masked by a retry (attempt the local path once, then a real upload) rather than fixed — see [UFB-0036](features/UFB-0036-native-video-replies.md#local-path-send-failures). If it recurs with a pattern (file size, filename shape, timing relative to download completion, server load), narrow it from there Lowered to P3 because the retry hides it from users. Until it recurs, make the retry log the file size, filename shape and time since download completion, so the pattern can be narrowed [P3/D3]

### Downloads / cache

### Previews

- #BUG-0062 [UFB-0035](features/UFB-0035-per-file-preview-images.md)'s frame extraction always grabs a fixed timestamp, so a black frame or a fade-in produces a useless preview for some clips. Consider a smarter pick (skip near-black frames, sample a few candidates) if this turns out to be common in practice [P3/D3]

### Deploy / infra


## Tech debt

Complexity, cleanup, and missing coverage in shipped behavior.

### Business logic

Design intent, confirmed against `process_url_request`'s decision tree: `DOWNLOAD_ALLOWED_DOMAINS` gates real `yt-dlp` downloads only — empty means every domain is allowed, the default. Mirror-link rewriting is a separate, independent gate, `REWRITE_ALLOWED_DOMAINS` (see [UFB-0023](features/UFB-0023-rewrite-domain-allowlist.md)) — empty there also means every platform is rewritten. Neither list affects the other, and YouTube is no longer special-cased: it is subject to both gates exactly like every other platform (2026-08-22).

- #BUG-0034 the platform/YouTube rewrite rules in `apply_rewrite_map` (`app/url_processing.py`) are a hardcoded list of `(regex, replacement)` tuples, one per platform — adding a new mirror site means editing code. Consider making rewrite rules dynamically configurable, e.g. an operator-supplied list of `{match_regex, mirror_domain}` rules (via env var or config file) instead of one Python tuple per platform [P3/D3]

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

- #BUG-0051 import-time side effects still make parts of the app hard to test cleanly: `bot = _make_bot(...)` and `dp = Dispatcher()` are still built at module import (`app/bot.py:48-49`; the `_make_bot` factory exists but isn't called lazily), and `settings = Settings()` still runs at import in `app/config.py:58`. `tests/conftest.py` works around it with `os.environ.setdefault("BOT_TOKEN", ...)` before any `app.*` import, which is enough for the suite. Calling a factory from `main.py` (or building `bot`/`dp` lazily) would remove the workaround [P3/D3]

### Docs

- #BUG-0080 `UFB-0039` relies on yt-dlp's private `TikTokIE._extract_web_data_and_status` to read a photo post's images; a yt-dlp refactor may break it. Isolated in `app.download._tiktok_item` [P3/D2]
