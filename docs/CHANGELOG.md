# Changelog

## Unreleased

- UFB-0033: `seed_static_pages` now re-renders the watch page of every
  pre-existing media file in `CACHE_DIR` on startup, not just the sample —
  so a template or embed-logic change (like the `INLINE_VIDEO_MAX_MB`
  threshold below) takes effect for already-downloaded files on the next
  bot restart instead of only whenever their URL is requested again.
- UFB-0032: fixes `#BUG-0061` — a media file over the new
  `INLINE_VIDEO_MAX_MB` setting (default `10`) now gets a plain watch page
  with no `og:video`/`twitter:player` tags or inline `<video>` element,
  since Telegram silently drops the inline player for large files anyway;
  `og:image` and the download link are unaffected.
- Fix: `Dockerfile` is now multi-stage — a `builder` stage installs `build-base`/`libffi-dev`/
  `openssl-dev`/`curl` and runs `uv sync`, then only the resulting `.venv`, `uv` binary, and app
  code are copied into a clean final stage; the compiler toolchain never reaches the runtime image
  (434MB → 415MB measured locally with the new `ffmpeg` dependency included). Copying `./app`
  before `uv sync` in the builder also closes `#BUG-0042` (`uv sync --no-editable` was installing
  the project's own package before its source existed, silently relying on `PYTHONPATH` instead).
- UFB-0035: `/watch/<file>` pages now carry a per-file `og:image` — a JPEG frame extracted with
  `ffmpeg` from the cached video — instead of the same bundled `preview.png` for every file, with
  the bundled image kept as the fallback when extraction fails. `og:video:type` now derives from
  the file's real extension. Fixes `#BUG-0015`: `outtmpl` now ends in `%(ext)s` and a remux
  postprocessor repackages a compatible non-mp4 container into a real `.mp4`, so cached files no
  longer wear a mismatched `.mp4` name; `ffmpeg` is a new runtime dependency (`Dockerfile`).
  Previews live at `CACHE_DIR/preview/<stem>.jpg` and are swept/protected alongside their media
  file's watch page.
- Tooling: every top-level function/class in `app/` now carries the `#UFB-NNNN`
  feature-id comment(s) `CLAUDE.md` requires (fixing `#BUG-0060`); a new
  `tests/frd_traceability_test.py` fails if one is missing or points at an ID not in
  `docs/FRD.md`. `docs/DOCS-DRIVEN-DEVELOPMENT.md` bumped to 1.3 to spell out the format.
- UFB-0026: replaced both cache-cleanup mechanisms (the `cron` compose service's `find -mtime`
  one-liner, which deleted actively-served files and the seeded static pages —
  fixing `#BUG-0030` — and the unused, never-shipped `cleanup.sh`, whose `FILE_TTL` unit
  disagreed with `docker-compose.yml`'s — fixing `#BUG-0010`) with a daemon thread inside the
  app (`app/cleanup.py`), started/stopped with the app lifespan and reported in `GET /health`.
  Cleanup now keys off access time, not modification time, so an actively-served file is never
  deleted while still being read (fixing `#BUG-0046`); `yt_dlp_download`'s cache-hit path
  explicitly refreshes `atime` on reuse. Deleting a cached media file also removes its
  `/watch/<file>` page; seeded filenames (landing/404 pages, preview image, sample clip and its
  watch page) are permanently exempt. `docker-compose.yml`'s `cron` service and `cleanup.sh` are
  removed; `FILE_TTL` (days, now atime-based) moved onto the `app` service and a new
  `CLEANUP_INTERVAL` (seconds between sweeps) was added; `FILE_TTL_TYPE` is gone.
- Docs: `docs/TODO.md` and `docs/BUGS.md` had drifted from
  `docs/DOCS-DRIVEN-DEVELOPMENT.md`'s spec — `TODO.md` had become a
  tech-debt list (the doc reserves it for new, not-yet-built behavior) and
  `FRD.md` was missing the `[x]`/`[ ]` status checkboxes the template
  requires. Moved every existing `TODO.md` entry into `BUGS.md` under
  `## Tech debt` or `## Chores` (new IDs `#BUG-0031`–`#BUG-0059`, continuing
  the shared ID sequence; `TODO.md` is now empty, ready for genuine new-
  feature ideas), added `[x]` to every `FRD.md` entry (all 34 features are
  `Implemented`), and documented the `[P#/D#]` priority/difficulty marker
  convention in `DOCS-DRIVEN-DEVELOPMENT.md` (bumped to v1.2), since that
  convention was already in active use but undocumented. Also logged
  `#BUG-0060`: `CLAUDE.md`'s "FRD feature id must be added to functions as
  comments" rule is barely followed in practice.
- UFB-0034: added `GET /healthz` (liveness) and `GET /health` (readiness)
  endpoints. `/health` reports whether the bot's Telegram polling loop is
  alive and whether the static pages have been seeded, returning 503 when
  either is false. The polling task is no longer fire-and-forget: `app/bot.py`
  now keeps a reference to it, logs unexpected failures via a completion
  callback, and cancels it cleanly on shutdown, fixing BUG-0007 (silent
  polling death). The `app` image's `Dockerfile` now declares a
  `HEALTHCHECK` that calls `/health` over HTTP (via busybox `wget`, since
  `curl` isn't in the runtime image) instead of `docker-compose.yml`
  testing for the seeded sample file directly — the check now travels
  with the image for anyone running it outside this compose file too.
- UFB-0030/UFB-0028: dropped the custom `url-fairy-bot-nginx` image — nginx
  now runs completely unmodified from the stock `nginx:stable-alpine-slim`
  image, with the shared cache volume mounted read-only directly at its
  default docroot (`/usr/share/nginx/html`) instead of a custom config
  pointing elsewhere. Removed `nginx/Dockerfile`, the nginx build/push
  matrix entry in CI, and the `compose.dev.yml` nginx build override (nginx
  is never built, so there's nothing to override in dev). Added an `app`
  healthcheck plus `depends_on: condition: service_healthy` on `nginx`,
  fixing a startup race this change would otherwise expose: nginx's first
  lookup of a path the app hadn't written yet could leave that path 404ing
  indefinitely on some filesystems, even after the app finished writing it
  — reproduced with `overlayfs` in testing, independent of this specific
  mount change (a latent risk since UFB-0033 moved the landing/404/sample
  pages into the shared volume).
- UFB-0033: all HTML (landing page, 404 page, per-file watch pages) is now
  generated by the app and written into the cache directory; nginx is a pure
  static file server with no SSI/autoindex. Watch page URLs now end in
  `.html` (e.g. `/watch/<file>.html`) instead of reusing the media filename,
  so nginx serves them as `text/html` rather than `video/mp4`. The Telegram
  Instant View sample page moved from the static `/theme/iv-example.html` to
  `/watch/sample.html`, rendered by the same code path as a real download —
  see [docs/telegram-instant-view-setup.md](telegram-instant-view-setup.md).
- UFB-0031: dropped the browsable `/cache/` listing entirely, closing the
  filename-privacy exposure in [BUGS #14](BUGS.md#14-cache-filenames-are-unbounded-and-non-deduplicated-medium-p2d2).
- Docs: fixed the sample template in `docs/telegram-instant-view-setup.md`
  (UFB-0032) — it never set the mandatory `body` field, assigned a
  nonexistent `video` field instead of `cover`, and scoped the rules to a
  `query { path: "/watch/*" }` block that never matches the sample page's
  own path (and used `*` as if it were a glob, not a regex) — any one of
  which makes the Instant View editor show "no instant preview available"
  for `iv-example.html`. Dropped the path restriction entirely and added the
  `~version: "2.1"` pragma the editor's footer was warning was missing.
- Fix: `uvicorn` was missing from `pyproject.toml`'s dependencies — dropped
  during the Poetry→uv migration (`f083941`) and never noticed because every
  build since had been reusing an older, still-uvicorn-containing image
  layer/venv. `entrypoint.sh` requires it directly; a genuinely fresh build
  from `main` could not start. Re-added as plain `uvicorn>=0.30.0,<1.0.0` —
  not the `[standard]` extra, which pulls in `watchfiles` for `--reload`
  (unused; `entrypoint.sh` doesn't pass it) and has no prebuilt wheel for
  armv7 musl, breaking the `linux/arm/v7` multi-arch build since rustup
  doesn't support the `arm-unknown-linux-musleabihf` target needed to build
  it from source. Regenerated `uv.lock`.
- Fix: `Lint: docker/hadolint` failing on `Dockerfile` (DL3013, unpinned
  `pip install uv`) — pinned to `uv==0.12.11`.
- Fix: `Markdown Lint` failing across several docs (missing code-fence
  languages, missing blank lines around fences/lists/headings, table
  alignment, emphasis style) — fixed and applied `markdownlint-cli2 --fix`.
- UFB-0032: download links now open a themed `/watch/<file>` page carrying
  `og:video`/`twitter:player` tags, so Telegram renders an inline-playable
  card instead of a bare file link. Setting the new `IV_RHASH` variable
  upgrades the same links to true Instant View via `t.me/iv?...&rhash=...`,
  once an operator creates a template for `BASE_URL`. The raw file URL is
  unchanged. Added `docs/telegram-instant-view-setup.md` walking through
  registering the template and getting a `rhash`.
- UFB-0031: the file server now has a landing page at `/`, instead of the
  root accidentally being a directory listing of every downloaded file
  (BUG-0013). Existing file URLs at the root are unchanged.
- UFB-0001: `/start` now actually reachable — the handler is registered at
  module import, ahead of the catch-all text handler, instead of only inside
  the unused `start_bot()`; `start_bot()` removed (BUG-0004).
- UFB-0029: Threads mirror-domain rewrites
- UFB-0030: registry-only deployment — `app` is pulled from GHCR instead of
  building/bind-mounting from the repo; `docker-compose.yml` no longer needs
  a checkout to deploy. Fixed `build-and-push.yml`'s GHCR login (missing
  `registry: ghcr.io`, the reason no image had ever published), replaced
  deprecated `::set-output` tagging with `docker/metadata-action`, and added
  `permissions: packages: write`.
  Also: `restart: unless-stopped` on `app`/`nginx`/`cron` (closes BUG-0009's
  compose half; TODO-0023), full env pass-through on `app` (TODO-0022),
  `uv.lock` copied + `uv sync --frozen` at build and `uv run --no-sync` at
  runtime for reproducible, network-free startup (TODO-0016, TODO-0018), a
  `.dockerignore` (TODO-0021), a new `.env.example`, and a `compose.dev.yml`
  override for local source builds. Closes TODO-0014, TODO-0015, TODO-0033,
  TODO-0034.

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
