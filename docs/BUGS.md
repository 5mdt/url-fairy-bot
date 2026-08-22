# Bugs

Automation/behavior misbehaving today. Complexity, cleanup, and missing coverage go in
`docs/TODO.md` instead. Entries are deleted when fixed (the fix gets a `docs/CHANGELOG.md`
bullet); IDs are never reused or renumbered, so deletions leave gaps. Next free ID: **BUG-0030**.

Each entry ends with a `[P#/D#]` marker:

```
Priority:   P1 = high     P2 = medium   P3 = low
Difficulty: D1 = trivial  D2 = small    D3 = medium   D4 = large
```

## Bot / entrypoint

- #BUG-0004 `/start` is unreachable — `start_bot()` (`app/bot.py:73-75`) is the only place that
  registers it (`dp.message.register(start, CommandStart())`) before calling
  `dp.run_polling(bot, skip_updates=False)`, but nothing calls `start_bot()`. The real entrypoint,
  `app/main.py`'s `lifespan()` (`:20-27`), imports `bot, dp` directly from `.bot` and starts polling
  itself (`asyncio.create_task(dp.start_polling(bot))`, `:23`) without ever registering the
  `CommandStart()` handler. Sending `/start` falls through to `handle_message`'s plain-text handler
  ("Please send a valid URL to process!") instead of the intended greeting; `start_bot()`/`start()`
  are dead code in production. Register the handler inside `lifespan()`, or at module import time in
  `bot.py` [P2/D1]
- #BUG-0006 blocking network/CPU calls run directly on the asyncio event loop — the
  redirect-following `requests.head()` (`app/url_processing.py:49`) and yt-dlp's `ydl.download()`
  (`app/download.py:74-84`) are both synchronous calls invoked from `async def` functions with no
  `run_in_executor`/thread offload. A single slow redirect or large download blocks the whole
  process, since the FastAPI event loop and the Telegram polling loop share one thread — one user's
  request stalls every other in-flight request. Run both via `loop.run_in_executor(None, ...)` or
  switch to async-native clients (`httpx.AsyncClient`) [P2/D3]
- #BUG-0007 bot polling failures are silent — `app/main.py`'s `lifespan()` (`:20-27`) discards the
  return value of `asyncio.create_task(dp.start_polling(bot))` with no `add_done_callback`
  observing exceptions, and the shutdown half only does `dp.storage.close()` + `bot.session.close()`
  — no `dp.stop_polling()` or task cancellation. If polling raises (network blip, invalid token,
  aiogram exception), the exception is logged nowhere and the task disappears — the app keeps
  reporting healthy while the bot has silently stopped responding. Keep a reference to the task, add
  a logging `add_done_callback`, and cancel it explicitly on shutdown [P2/D2]
- #BUG-0016 Markdown replies can still break Telegram's parser for URLs — the reply-to-bot shrug
  text itself is correct today (`"¯\\_(ツ)_/¯"`, `app/bot.py:37`), but every `[text](url)` link built
  from a `final_url`/`modified_url` (`app/url_processing.py:157,184,189-190,196-198,213-215`) is
  still an unescaped f-string, so any URL containing `)` or `_` (common in TikTok/Instagram share
  links) breaks the surrounding Markdown link syntax. Telegram either mangles the message or rejects
  `sendMessage` outright (`can't parse entities`), so the bot silently fails to reply for an
  otherwise-successful request. Escape user-derived URL text, or switch to `MarkdownV2`/HTML with
  proper escaping [P2/D2]

## Downloads / cache

- #BUG-0014 cache filenames are unbounded, non-deduplicated, and directory-unsafe — the output
  filename (`app/download.py:56-57,112-113`, `sanitize_subfolder_name`) is the *entire* input URL
  with non-alphanumeric characters replaced by `_`, with no length cap, no lock/mutex around "does
  this file already exist" (`:59-61`), and `settings.CACHE_DIR` is never created (`os.makedirs`)
  before use. A sufficiently long URL can exceed the filesystem's ~255-byte filename limit and raise
  `OSError`; two concurrent requests for the same not-yet-cached URL both start a download; a
  missing `CACHE_DIR` fails the first write outright. Hash the URL (e.g. truncated sha256) instead
  of transliterating it, add an `asyncio.Lock` per in-flight URL, and
  `os.makedirs(..., exist_ok=True)` at startup [P2/D2]
- #BUG-0015 downloaded files are always saved with a `.mp4` extension — `outtmpl`
  (`app/download.py:57,64-67`) is hardcoded to end in `.mp4` while `"format": "best"` lets yt-dlp
  choose whatever container the best available stream is in (webm, mkv, etc.), and the Docker image
  installs no `ffmpeg`, so yt-dlp can't remux/merge into a real `.mp4` when needed. Files are
  frequently mislabeled and can fail to play in strict players/browsers. Let yt-dlp choose the real
  extension (`%(ext)s`) and install `ffmpeg` if format merging is desired [P3/D2]

## Deploy / infra

- #BUG-0009 the `cron` compose service's cache cleanup runs once and then stops forever — its
  command is `find ... -delete; find ... -delete; sleep 60m` with no loop, and no service in
  `docker-compose.yml` has a `restart:` policy. The cache is cleaned exactly once, then the
  container sleeps 60 minutes and exits, so the `cache` volume grows unbounded until someone
  manually restarts it. Also note the double slash in `/tmp/url-fairy-bot-cache//`, and that
  `FILE_TTL` is commented `#days` here but treated as **seconds** by the (unused) `cleanup.sh:135`
  — the two cleanup mechanisms disagree on units. Add `restart: unless-stopped` and wrap the command
  in a loop, or switch to `cleanup.sh --serve` (see #BUG-0010) [P2/D2]
- #BUG-0010 `cleanup.sh` (repo root, 207 lines) is a complete, argument-parsing, env-validating
  cache-cleanup script — more correct than the inline `cron` service's `find` one-liner
  (#BUG-0009) — but it is never `COPY`'d into the Docker image and no compose service invokes it,
  so it has no effect at runtime. Either wire it into the `cron` service (`entrypoint: ["/cleanup.sh",
  "--serve"]`) or remove it if superseded [P3/D2]
- #BUG-0012 the unauthenticated API is an SSRF-capable open proxy — `POST /process_url/`
  (`app/api.py:11-24`) takes an arbitrary string URL with no auth or rate limit, and
  `follow_redirects()` (`app/url_processing.py:47-66`) issues a server-side `HEAD` request to it.
  It can be used to probe internal/link-local addresses (e.g. cloud metadata endpoints) and
  enumerate reachability of internal hosts. The bot path is safer since `URLMessage.url: HttpUrl`
  (`app/models.py:6`) validates the URL, but the API's `URLRequest.url: str` (`app/api.py:12`) does
  not. Validate `URLRequest.url` as `HttpUrl` too, block private/link-local/loopback ranges before
  outbound requests, and add auth/rate limiting [P2/D3]
- #BUG-0013 the public nginx autoindex exposes every downloaded file — `autoindex on`
  (`nginx/conf.d/default.conf`) is set at the web root (`root /tmp/url-fairy-bot-cache/`), the
  shared download cache. Anyone who can reach `BASE_URL` can browse a directory listing of every
  file any user has ever had the bot download, including filenames that embed the original source
  URL (#BUG-0014) — a privacy leak of what URLs users have sent the bot. Turn off `autoindex`, or
  require an unguessable per-file path/token instead of a directory listing [P2/D1]
- #BUG-0017 `.github/workflows/dependabot.yml` is inert — Dependabot config must live at
  `.github/dependabot.yml` (top-level, not under `workflows/`), and even so
  `package-ecosystem: ""` is not a valid value. No dependency update PRs are ever generated; GitHub
  silently ignores the unrecognized file under `workflows/`. Move it to `.github/dependabot.yml`
  and set `package-ecosystem: "pip"` (plus a `"github-actions"` entry) [P3/D1]

## Business logic

- #BUG-0023 YouTube's mirror-link alternative is incorrectly gated behind
  `DOWNLOAD_ALLOWED_DOMAINS` — `process_url_request`'s `transform_youtube_url(final_url)` call
  (`app/url_processing.py:193`) only runs *after* the `is_domain_allowed` branch (`:173-191`) has
  already returned. `DOWNLOAD_ALLOWED_DOMAINS` defaults to empty, so `is_domain_allowed` returns
  `False` for every domain by default, and `apply_rewrite_map` (called from the "not allowed"
  branch) has no YouTube entries at all — those patterns live only in `transform_youtube_url`,
  which this path never reaches on a default install. The test suite works around this today by
  explicitly setting `DOWNLOAD_ALLOWED_DOMAINS=youtube.com` to exercise the short-circuit
  (`tests/url_processing_test.py:307-317`) — a real deployment has no such override by default.
  Unlike Spotify/Instagram/Reddit/TikTok/Twitter, YouTube's mirror link is unreachable unless an
  operator explicitly allow-lists `youtube.com`/`music.youtube.com`/`youtu.be`, which is confusing
  given the reply text says the video "cannot be downloaded." Move the `transform_youtube_url`
  check ahead of (or independent of) the `is_domain_allowed` gate so it behaves like the other five
  platforms [P1/D2]
