# Bugs

Confirmed defects found during a codebase audit (2026-08-20), ordered roughly by severity.
Each entry cites the exact location so it can be re-verified.

## 1. Redirect resolution strips query strings, breaking YouTube rewrites (High) [P1/D2]

**Status: Fixed (2026-08-21)** — `follow_redirects` now rebuilds the query string
against an allow-list of content-identifying parameter names (`v`, `list`, `t`,
`index`, `id`) instead of dropping it entirely.

- **Location**: `app/url_processing.py:38-45` (`follow_redirects`)
- **What happens**: `follow_redirects()` unconditionally drops the query component of every
  resolved URL (`urlunparse(urlparse(response.url)._replace(query=""))`).
- **Impact**: `https://www.youtube.com/watch?v=ID` becomes `https://www.youtube.com/watch`
  before it reaches `transform_youtube_url()` (`app/url_processing.py:51-75`), whose regexes
  all require `?v=...`. Regular (non-`youtu.be`) YouTube links can never match, so the YouTube
  rewrite feature is effectively dead for its main case. Any other platform that encodes the
  content id in the query string breaks the same way.
- **Suggested fix**: only strip tracking-style query params (or none at all), and match
  `transform_youtube_url` against the pre-redirect URL as well.

## 2. `*_REWRITE_ENABLED` settings are defined, documented, and never read (High) [P1/D2]

**Status: Fixed (2026-08-21)** — `apply_rewrite_map`'s `rewrite_map` entries are now
gated on their corresponding `*_REWRITE_ENABLED` setting.

- **Location**: `app/config.py:18-22`, documented in `README.md:111-115`
- **What happens**: `INSTAGRAM_REWRITE_ENABLED`, `REDDIT_REWRITE_ENABLED`,
  `SPOTIFY_REWRITE_ENABLED`, `TIKTOK_REWRITE_ENABLED`, `TWITTER_REWRITE_ENABLED` are parsed
  from the environment but not referenced anywhere else in `app/`.
- **Impact**: `apply_rewrite_map()` (`app/url_processing.py:78-99`) rewrites every matching URL
  unconditionally. Operators who set e.g. `TIKTOK_REWRITE_ENABLED=false` (as documented) get no
  effect at all — a documented, configurable feature silently does nothing.
- **Suggested fix**: gate each `rewrite_map` entry on its corresponding setting, or remove the
  settings and the README rows if the feature was intentionally dropped.

## 3. `COOKIES_DIR` reads the wrong environment variable (High) [P1/D1]

- **Location**: `app/config.py:14`
- **What happens**: `COOKIES_DIR: str = os.getenv("COOKIES_FILE", "/config/")` — the field is
  named `COOKIES_DIR` but reads env var `COOKIES_FILE`.
- **Impact**: Setting `COOKIES_DIR` (as documented in `README.md`, "Cookie Support" section and
  the environment variable table) has no effect; the directory always defaults to `/config/`
  unless the differently-named `COOKIES_FILE` is set instead.
- **Suggested fix**: `os.getenv("COOKIES_DIR", "/config/")`.

## 4. `/start` command handler is unreachable (Medium) [P2/D1]

- **Location**: `app/bot.py:19-20, 64-66`; real entrypoint `app/main.py:25-28`
- **What happens**: `dp.register_message_handler(start, commands="start")` only happens inside
  `start_bot()`, a function nothing calls. The process actually starts polling via
  `asyncio.create_task(dp.start_polling())` in `app/main.py`'s FastAPI startup hook, which never
  registers the `/start` command handler.
- **Impact**: Sending `/start` to the bot falls through to `handle_message` (a plain text
  handler matches `/start` as message text, extracts no URL) and the bot replies "Please send a
  valid URL to process!" instead of the intended greeting. `start_bot()` and `start()` are dead
  code in production.
- **Suggested fix**: register the `/start` handler in `app/main.py`'s startup, or call
  `dp.register_message_handler(start, commands="start")` at module import time in `bot.py`.

## 5. Domain allow-list can be bypassed or trivially disabled (Medium) [P1/D2]

**Status: Fixed (2026-08-21)** — allow-list entries are now trimmed, lower-cased,
and empties dropped; matching requires an exact or label-boundary
(`.`-prefixed subdomain) match instead of a raw `endswith`.

- **Location**: `app/url_processing.py:17-35` (`is_domain_allowed`)
- **What happens**: The allow-list check is `domain.endswith(allowed_domain.lower())` with no
  boundary check and no `.strip()` on the comma-split entries.
  - `endswith` matches on substrings, not domain suffixes: an allow-list of `tiktok.com` also
    matches `evil-tiktok.com` (ends with `tiktok.com` as a raw string).
  - A stray space after a comma (`"tiktok.com, x.com"`) yields an entry `" x.com"` that will
    never match anything (since `domain` is lowercased but not stripped of the leading space
    accordingly), silently locking that domain out.
  - A trailing comma in `DOWNLOAD_ALLOWED_DOMAINS` (`"tiktok.com,"`) produces an empty entry;
    `domain.endswith("")` is always `True`, so **every** domain becomes allowed.
- **Impact**: The allow-list can silently become a no-op (fail open) or admit lookalike domains,
  defeating the purpose of `DOWNLOAD_ALLOWED_DOMAINS`.
- **Suggested fix**: split with `.split(",")` then `.strip()` each entry and drop empties;
  compare with `domain == allowed_domain or domain.endswith("." + allowed_domain)`.

## 6. Blocking network/CPU calls run directly on the asyncio event loop (Medium) [P2/D3]

- **Location**: `app/url_processing.py:39-40` (`requests.head`), `app/download.py:73-83`
  (`ydl.download` inside `async def yt_dlp_download`)
- **What happens**: Both the redirect-following HTTP call and the yt-dlp download are
  synchronous, blocking calls invoked directly from `async def` functions with no
  `run_in_executor`/thread offload.
- **Impact**: A single slow redirect or large video download blocks the entire process — the
  FastAPI event loop and the Telegram polling loop share one thread, so one user's request stalls
  every other in-flight request and the bot's `/process_url/` and message handling.
- **Suggested fix**: run both via `loop.run_in_executor(None, ...)` or switch to async-native
  clients (`httpx.AsyncClient` for redirects).

## 7. Bot polling failures are silent (Medium) [P2/D2]

- **Location**: `app/main.py:25-35`
- **What happens**: `asyncio.create_task(dp.start_polling())` discards its return value (task can
  be garbage-collected per asyncio's usual footgun) and no callback/`add_done_callback` observes
  exceptions. `on_shutdown` closes `dp.storage` but never calls `dp.stop_polling()` or cancels the
  task.
- **Impact**: If polling raises (e.g. network blip, invalid token, aiogram exception), the
  exception is logged nowhere and the task disappears — the FastAPI app (and its `/health`-less
  liveness) keeps reporting healthy while the Telegram bot has silently stopped responding.
- **Suggested fix**: keep a reference to the task, add `add_done_callback` that logs/raises, and
  cancel it explicitly on shutdown.

## 8. CI lint is currently red on `main` (Medium) [P1/D1]

**Status: Fixed (2026-08-21)** — `black ./app` and `isort ./app` have been run and
committed; `black --check ./app` is clean.

- **Location**: `.github/workflows/lint-python-black.yml`; verified locally with
  `black --check ./app`
- **What happens**: Running `black --check ./app` against the current `main` reports
  `app/config.py` and `app/url_processing.py` (3 files total) would be reformatted.
- **Impact**: The `lint-python-black` GitHub Actions job must be failing on every push/PR to
  `main`, undermining the value of the check (and likely trained reviewers to ignore it).
- **Suggested fix**: run `black ./app` once and commit, then keep pre-commit's black hook
  actually enforced before merging.

## 9. Cache cleanup (`cron` compose service) runs once and then stops forever (Medium) [P2/D2]

- **Location**: `docker-compose.yml` (`cron` service)
- **What happens**: The command is
  `find ... -delete; find ... -delete; sleep 60m` with no loop, and the service has no
  `restart:` policy (no service in the file does).
- **Impact**: The cache is cleaned exactly once, after which the container sleeps for 60 minutes
  and exits — cleanup never runs again unless someone manually restarts the container. The
  `cache` volume grows unbounded in normal operation. Also note the double slash in
  `/tmp/url-fairy-bot-cache//` and that `FILE_TTL` is commented `#days` here but is treated as
  **seconds** by the (unused) `cleanup.sh:135` — the two cleanup mechanisms disagree on units.
- **Suggested fix**: add `restart: unless-stopped` and wrap the command in a `while true; do ...;
  done` loop, or replace with the (more careful) `cleanup.sh --serve` — see Bug 10.

## 10. `cleanup.sh` is never shipped or run (Low) [P3/D2]

- **Location**: `cleanup.sh` (repo root); not referenced by `Dockerfile` or `docker-compose.yml`
- **What happens**: `cleanup.sh` is a complete, argument-parsing, env-validating cache-cleanup
  script, but it is not `COPY`'d into the Docker image and no compose service invokes it.
- **Impact**: Dead code that looks production-ready (and is more correct than the inline `cron`
  service's `find` one-liner — see Bug 9) but has no effect at runtime.
- **Suggested fix**: either wire it into the `cron` service (`entrypoint: ["/cleanup.sh",
  "--serve"]`) or remove it if superseded.

## 11. `follow_redirects` only handles the timeout case (Low) [P3/D2]

**Status: Fixed (2026-08-21)** — `follow_redirects` now also catches
`requests.RequestException` broadly and returns the original URL unchanged.
The bot/API-side catch-alls described in the suggested fix are still open.

- **Location**: `app/url_processing.py:38-48`
- **What happens**: The `try` only catches `requests.Timeout`. `ConnectionError`,
  `TooManyRedirects`, `InvalidURL`, `SSLError`, etc. all propagate uncaught.
- **Impact**: In the bot path (`app/bot.py:48-61`), there is no surrounding `except Exception`
  around `process_url_request`, so an unreachable/unresolvable host raises inside the message
  handler with no user-facing reply and only aiogram's generic error logging. In the API path
  (`app/api.py:20-24`), the raw exception message is returned to the caller as a 400 detail,
  leaking internal error text (e.g. DNS resolution errors, local library paths).
- **Suggested fix**: broaden the `except` to `requests.RequestException`, and wrap
  `process_url_request` calls in both `bot.py` and `api.py` with a catch-all that replies/returns
  a safe generic message.

## 12. Unauthenticated API is an SSRF-capable open proxy (Low/contextual) [P2/D3]

- **Location**: `app/api.py:11-24`, `app/url_processing.py:38-48`
- **What happens**: `POST /process_url/` takes an arbitrary string URL (no auth, no rate limit),
  and `follow_redirects()` issues a `HEAD` request to it server-side.
- **Impact**: The API can be used to probe internal/link-local addresses (e.g. cloud metadata
  endpoints) and enumerate reachability of internal hosts from wherever the container runs. The
  bot path is safer since `URLMessage.url: HttpUrl` (`app/models.py`) validates the URL, but the
  API's `URLRequest.url: str` (`app/api.py:11-12`) does no such validation.
- **Suggested fix**: validate `URLRequest.url` as `HttpUrl` too, and consider blocking
  private/link-local/loopback address ranges before making outbound requests, plus basic auth or
  rate limiting on the endpoint.

## 13. Public autoindex exposes every downloaded file (Low/contextual) [P2/D1]

- **Location**: `nginx/conf.d/default.conf`
- **What happens**: `autoindex on` is set at the web root (`root
  /tmp/url-fairy-bot-cache/`), which is the shared download cache.
- **Impact**: Anyone who can reach `BASE_URL` can browse a directory listing of every file any
  user has ever had the bot download, including filenames that embed the original source URL
  (see `sanitize_subfolder_name`, Bug 14) — a privacy leak of what URLs users have sent the bot.
- **Suggested fix**: turn off `autoindex`, or require an unguessable per-file path/token instead
  of a directory listing.

## 14. Cache filenames are unbounded, non-deduplicated, and directory-unsafe (Low) [P2/D2]

- **Location**: `app/download.py:56, 111-112` (`sanitize_subfolder_name`,
  `yt_dlp_download`)
- **What happens**: The output filename is the *entire* input URL with non-alphanumeric
  characters replaced by `_`, with no length cap. There is also no lock/mutex around
  "does this file already exist" (`app/download.py:58-60`), and `settings.CACHE_DIR` is never
  created (`os.makedirs`) before use.
- **Impact**: A sufficiently long URL (common with tracking query strings, before Bug 1's
  stripping applies — e.g. via the API which does not call `follow_redirects` before hashing)
  can exceed the filesystem's max filename length (~255 bytes on most Linux filesystems) and
  raise `OSError`. Two concurrent requests for the same not-yet-cached URL both start a
  download. If `CACHE_DIR` doesn't exist, the first write fails outright.
- **Suggested fix**: hash the URL (e.g. `sha256` truncated) instead of transliterating it,
  add an `asyncio.Lock` per in-flight URL, and `os.makedirs(settings.CACHE_DIR, exist_ok=True)`
  at startup.

## 15. Downloaded files are always saved with a `.mp4` extension (Low) [P3/D2]

- **Location**: `app/download.py:56, 63-66`
- **What happens**: `outtmpl` is hardcoded to end in `.mp4` while `"format": "best"` lets
  yt-dlp choose whatever container the best available stream is in (webm, mkv, etc.), and the
  Docker image installs no `ffmpeg` (`Dockerfile` has no such package), so yt-dlp cannot remux/
  merge into a real `.mp4` when needed.
- **Impact**: Files are frequently mislabeled (a `.webm` stream saved with a `.mp4` extension),
  which can fail to play in strict players/browsers, and formats that require post-processing
  merges fail outright without `ffmpeg`.
- **Suggested fix**: let yt-dlp choose the real extension (`outtmpl` without a fixed suffix, or
  `%(ext)s`) and install `ffmpeg` in the image if format merging/remuxing is desired.

## 16. Markdown replies can break Telegram's parser (Low) [P2/D2]

- **Location**: `app/bot.py:32-35` (group-reply easter egg), and every
  `f"...[…]({final_url})"` link built in `app/url_processing.py`
- **What happens**: `"\_ (ツ)_/"` sent with `parse_mode=MARKDOWN` has an odd number of `_`
  characters (legacy Telegram Markdown treats `_..._` as italics), and any `final_url`/
  `modified_url` containing `)` or `_` (both legal and common in the wild, e.g. TikTok/Instagram
  share links with query params) breaks the surrounding `[text](url)` markdown link syntax.
- **Impact**: Telegram either mangles the rendered message or rejects the `sendMessage` call
  outright (`can't parse entities`), causing the bot to silently fail to reply for otherwise-
  successful URL processing.
- **Suggested fix**: escape user-derived URL text for Markdown, or switch to
  `parse_mode=MarkdownV2`/HTML with proper escaping, or stop putting raw URLs inside `()`.

## 17. `dependabot.yml` workflow is inert (Low) [P3/D1]

- **Location**: `.github/workflows/dependabot.yml`
- **What happens**: Dependabot configuration must live at `.github/dependabot.yml` (top-level,
  not under `workflows/`), and even so `package-ecosystem: ""` is not a valid ecosystem value.
- **Impact**: No dependency update PRs are ever generated by this file; it silently does
  nothing (GitHub ignores unrecognized files under `workflows/`).
- **Suggested fix**: move it to `.github/dependabot.yml` and set
  `package-ecosystem: "pip"` (and add a `"github-actions"` entry for the workflow files).

## Test suite

Findings from auditing `tests/` itself (2026-08-20 follow-up). Numbering continues from the
findings above; do not renumber #1–#17, other docs link to them by anchor.

### 18. The suite cannot even be collected without a real `BOT_TOKEN` (High) [P1/D2]

- **Location**: `app/bot.py:14` (`Bot(token=settings.BOT_TOKEN)`, runs at import time);
  `tests/api_test.py:6` and `tests/bot_test.py:5` both import through `app.main`/`app.bot`
- **What happens**: aiogram validates the token at `Bot.__init__` time
  (`aiogram/bot/base.py:76` → `aiogram/bot/api.py:57`, `check_token()`), raising
  `aiogram.utils.exceptions.ValidationError` for an empty or malformed token. Nothing in the test
  suite stubs or bypasses this — the suite only "works" today because the maintainer's untracked
  `.env` (loaded via `app/config.py:7`'s `load_dotenv()`) happens to contain a real `BOT_TOKEN`.
- **Impact**: A fresh `git clone` + `pytest`, or any CI runner without that specific `.env`, fails
  at **collection**, before a single test body runs — `pytest` reports every test in
  `api_test.py`/`bot_test.py` as an error, not a failure. This is very likely why no GitHub
  Actions workflow runs `pytest` at all (see `TODO.md`).
- **Suggested fix**: stop constructing a real `Bot`/`Dispatcher` at import time (factory function
  instead — see `TODO.md`), or provide a `conftest.py` that sets a syntactically-valid dummy
  `BOT_TOKEN` (e.g. `"123456:TEST"`) and disables token validation
  (`Bot(token=..., validate_token=False)`) before any app module is imported.

### 19. `bot_test.py`'s only assertion lives on an unreachable code path (High) [P2/D2]

- **Location**: `tests/bot_test.py:8-25`
- **What happens**: The test sends `https://example.com` in a `"group"` chat. Walking
  `process_url_request` (`app/url_processing.py`): `example.com` is not on
  `DOWNLOAD_ALLOWED_DOMAINS` (empty by default) → not allowed branch; `apply_rewrite_map` doesn't
  match `example.com` so `modified_url == final_url`; chat is a group ⇒ the function returns
  `None` (`:128-131`). Back in `handle_message` (`app/bot.py:56`), `if result is not None:` is
  `False`, so `message.reply()` — the only place the test's `assert` lives — is **never called**.
- **Impact**: The test passes unconditionally without exercising its own assertion; it gives false
  confidence that "URL handling in group chats" is covered. It is also self-contradictory: the
  expected substrings (`"Unsupported URL https://example.com/"`, `"success"`) don't match any
  string ever produced by `app/url_processing.py`, so if the reply path *were* reached (e.g. after
  the group-silence behavior changes), this test would immediately start failing on unrelated
  strings.
- **Suggested fix**: parametrize over chat type and expected outcome (e.g. private chat + a
  mocked `process_url_request` return value → assert `reply` was actually called with that value;
  group chat + `None` → assert `reply` was **not** called).

### 20. `apply_rewrite_map`/`transform_youtube_url` "defaults" tests depend on ambient env vars (Medium) [P2/D2]

- **Location**: `tests/url_processing_test.py:11-38` (`test_apply_rewrite_map_defaults`),
  `:63-80` (`test_transform_youtube_url_defaults`)
- **What happens**: These tests assert against literal mirror domains
  (`fxspotify.com`, `kkinstagram.com`, `yfxtube.com`, …) but read them via the live, imported
  `settings` object, which is populated from whatever `*_MIRROR_DOMAIN` environment variables are
  set at import time — they never pin `settings` the way the "overridden" tests a few lines below
  correctly do (`monkeypatch.setattr(settings, ...)`, `:44-49`, `:87-95`).
- **Impact**: `docker-compose.yml` sets all seven `*_MIRROR_DOMAIN` variables explicitly (even
  though they're set to the same values as the code defaults today). If anyone changes a mirror
  domain in `docker-compose.yml` without changing the code default (or vice versa), these
  "defaults" tests silently start failing inside the container/CI while continuing to pass on a
  developer machine with no such env vars set — the opposite of what a "defaults" test should do.
- **Suggested fix**: `monkeypatch.delenv`/`monkeypatch.setattr` every `*_MIRROR_DOMAIN` setting to
  its known default at the top of the defaults tests, so they're isolated from the environment.

### 21. `api_test.py` performs live outbound network I/O and asserts almost nothing (Medium) [P2/D2]

- **Location**: `tests/api_test.py:8-14`
- **What happens**: Posting `https://example.com` reaches `process_url_request` →
  `follow_redirects()` → a real `requests.head("https://example.com", ...)` over the network
  (`app/url_processing.py:38-48`). The only assertions are `response.status_code == 200` and
  `response.json()["status"] == "success"` — but `app/api.py:18-24` returns `"success"` for
  *any* call to `process_url_request` that doesn't raise, regardless of what `data` actually
  contains, so the test cannot detect a regression in the URL-processing logic itself.
- **Impact**: The test is slow, flaky, and fails outright in offline/sandboxed CI (or blocks for
  up to `FOLLOW_REDIRECT_TIMEOUT` seconds, default 10s, per run). It also implicitly depends on
  whatever `DOWNLOAD_ALLOWED_DOMAINS` happens to be set to in the environment — if `example.com`
  (or a domain it redirects to) were ever allow-listed, this "API smoke test" would start
  triggering a real `yt-dlp` download as a side effect of running the test suite.
- **Suggested fix**: mock `follow_redirects`/`is_domain_allowed`/`yt_dlp_download` (e.g. via
  `unittest.mock.patch`) so the test exercises FastAPI request/response wiring only, and assert on
  the actual `data` payload instead of just `status`.

### 22. Unescaped `.` in the Spotify rewrite pattern (Low) [P2/D1]

**Status: Fixed (2026-08-21)** — the Spotify pattern now escapes the dot in
`spotify\.com`.

- **Location**: `app/url_processing.py:88`
- **What happens**: `r"^https://(open\.)?spotify.com"` escapes the first dot but not the one in
  `spotify.com`; in regex, an unescaped `.` matches *any* character, not just a literal dot.
- **Impact**: A URL like `https://spotifyXcom.evil.tld/...` (or any single-character substitution
  for the dot) is matched and rewritten as if it were a genuine Spotify link — a spoofable
  redirect target. None of the existing tests (`tests/url_processing_test.py`) cover this edge
  case; every *other* pattern in the same `rewrite_map` correctly escapes its dots.
- **Suggested fix**: `r"^https://(open\.)?spotify\.com"`, plus a regression test asserting the
  literal-dot requirement.

## Business logic

Findings from auditing `process_url_request`'s decision tree itself (2026-08-20 follow-up),
confirmed against stated design intent: `DOWNLOAD_ALLOWED_DOMAINS` is meant to gate only whether
a real `yt-dlp` download is attempted — mirror-link rewriting should always be available
regardless of the allow-list, the same way it already works for Spotify/Instagram/Reddit/
TikTok/Twitter.

### 23. YouTube's mirror-link alternative is incorrectly gated behind `DOWNLOAD_ALLOWED_DOMAINS` (High) [P1/D2]

- **Location**: `app/url_processing.py:116-149` (`process_url_request`) — the
  `transform_youtube_url(final_url)` call at `:143` only runs *after* the
  `if not is_domain_allowed(final_url):` branch (`:123-141`) has already returned.
- **What happens**: `DOWNLOAD_ALLOWED_DOMAINS` defaults to empty, and `is_domain_allowed`
  returns `False` for every domain when the list is empty (`app/url_processing.py:17-22`). So on
  a default install, YouTube URLs hit the "not allowed" branch first — and `apply_rewrite_map`
  (called from that branch) has **no YouTube entries at all** (those patterns live only in
  `transform_youtube_url`, which this code path never reaches). The user gets a bare "This domain
  is not allowed for downloading" message with no alternative link, even though the entire
  purpose of `transform_youtube_url` is to hand YouTube users a nicer mirror link. The five other
  mirror platforms don't have this problem, because their rewrite patterns live in
  `apply_rewrite_map`, which *is* reached by the "not allowed" branch.
- **Impact**: Unlike Spotify/Instagram/Reddit/TikTok/Twitter (which get a working mirror link out
  of the box), YouTube's mirror-link feature is unreachable unless an operator explicitly
  allow-lists `youtube.com`/`music.youtube.com`/`youtu.be` — which is a confusing thing to ask an
  operator to do, since the reply text itself says the video "cannot be downloaded." Even in that
  misconfigured-looking state, the feature is further broken by the query-string stripping in
  [#1](#1-redirect-resolution-strips-query-strings-breaking-youtube-rewrites-high-p1d2). No existing
  test would have caught this: `transform_youtube_url` is only ever tested in isolation
  (`tests/url_processing_test.py`), never through `process_url_request` end-to-end.
- **Suggested fix**: move the `transform_youtube_url` check ahead of (or independent of) the
  `is_domain_allowed` gate, so it behaves like the other five platforms and fires unconditionally.

## Message handling

Findings from auditing the feature set against `docs/features/*.md` (2026-08-21 follow-up).
Numbering continues from the findings above.

### 24. URL extraction captures trailing punctuation and Markdown syntax (Low) [P3/D1]

**Status: Fixed (2026-08-21)** — each match now has trailing
`.,;:!?)]}'"` characters trimmed before processing.

- **Location**: `app/bot.py:38` (`url_pattern = r"(https?://\S+)"`)
- **What happens**: `\S+` is greedy and has no allowance for sentence punctuation or enclosing
  brackets/quotes, so `Look at https://x.com/a).` extracts `https://x.com/a).` as the URL.
- **Impact**: The trailing `).` is carried through redirect resolution and rewrite matching, and
  ends up embedded inside the reply's `[…](url)` markdown link, compounding
  [#16](#16-markdown-replies-can-break-telegrams-parser-low-p2d2).
- **Suggested fix**: trim trailing `.,;:!?)]}'"` characters from each match before processing.

### 25. The reply-to-bot shrug is malformed (Low) [P3/D1]

**Status: Fixed (2026-08-21)** — the text now sends `"¯\_(ツ)_/¯"`.

- **Location**: `app/bot.py:33`
- **What happens**: The easter-egg reply text is `"\_ (ツ)_/"` — both `¯` macrons are missing and
  there's a stray space, unlike the intended `¯\_(ツ)_/¯` shrug emoticon (as described in
  `docs/flows/message-handling-flow.md:14`).
- **Impact**: Users replying to the bot in a group see a garbled emoticon instead of the intended
  shrug.
- **Suggested fix**: send `"¯\\_(ツ)_/¯"`.

### 26. YouTube rewrite misses Shorts, `m.`, and bare-domain forms (Medium) [P2/D2]

**Status: Fixed (2026-08-21)** — patterns now accept an optional `www.`/`m.`
host prefix, bare `youtube.com`, and a `/shorts/<id>` path form.

- **Location**: `app/url_processing.py:58-71` (`transform_youtube_url`)
- **What happens**: The three patterns require a literal `https://www.youtube.com/watch?v=`,
  `https://music.youtube.com/watch?v=`, or `https://youtu.be/` prefix. `youtube.com/shorts/ID`
  (Shorts), `m.youtube.com/watch?v=ID` (mobile), and `youtube.com/watch?v=ID` (no `www.`) all
  fail to match any pattern.
- **Impact**: A large share of real-world shared YouTube links — particularly Shorts and links
  copied from the mobile app/site — never get a mirror-link alternative, even once
  [#23](#23-youtubes-mirror-link-alternative-is-incorrectly-gated-behind-download_allowed_domains-high-p1d2)
  is fixed.
- **Suggested fix**: broaden the patterns to accept an optional `www.`/`m.` host prefix and a
  `/shorts/<id>` path form.

### 27. Raw pydantic `ValidationError` text is replied to the user (Low) [P3/D1]

**Status: Fixed (2026-08-21)** — `e` is still logged at `warning` level, but the
user now gets a fixed short message instead of the raw exception text.

- **Location**: `app/bot.py:61` (`await message.reply(f"Invalid URL provided: {e}")`)
- **What happens**: `e` is the full `pydantic.ValidationError`, whose `str()` includes a
  multi-line error summary and a `https://errors.pydantic.dev/...` documentation link.
- **Impact**: Users see an internal library error dump instead of a short, friendly rejection
  message.
- **Suggested fix**: log `e` at `warning` level (already done) and reply with a fixed short
  message, e.g. `"That doesn't look like a valid URL."`

## Test suite audit (2026-08-21 follow-up)

Two further defects surfaced while making `tests/` genuinely green (i.e. removing the
`xfail`/`skip` markers added by the 2026-08-20/21 audits). Numbering continues from the findings
above; do not renumber #1–#27.

### 28. `yt_dlp.PostProcessingError` is not a real attribute (Low) [P2/D1]

**Status: Fixed (2026-08-21)** — changed to `yt_dlp.utils.PostProcessingError`.

- **Location**: `app/download.py:98` (`except yt_dlp.PostProcessingError as e:`)
- **What happens**: `PostProcessingError` is not a top-level attribute of the `yt_dlp` package —
  only `yt_dlp.utils.PostProcessingError` exists. Evaluating the `except` clause itself raises
  `AttributeError` instead of catching the real error.
- **Impact**: A post-processing failure (e.g. a merge/remux error) never gets mapped to the
  intended `RuntimeError`; it crashes with an unrelated `AttributeError` instead.
- **Suggested fix**: `except yt_dlp.utils.PostProcessingError as e:` (done).

### 29. Unreachable generic `except Exception` in `process_url_request` (Low) [P3/D2]

**Status: Fixed (2026-08-21)** — the dead branch was removed.

- **Location**: `app/url_processing.py:167-179` (removed)
- **What happens**: `attempt_download()` was the only call inside the `try` block in
  `process_url_request`, and it already converts every exception into `UnsupportedUrlError`
  (`app/url_processing.py:108-112`), so the `except UnsupportedUrlError` branch above always won —
  the generic `except Exception` branch could never execute.
- **Impact**: Dead code that also pushed `process_url_request` over flake8's `C901` complexity
  threshold.
- **Suggested fix**: remove the unreachable branch (done).
