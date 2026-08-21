# TODO / Tech Debt

Cleanups, simplifications, and missing coverage found during a codebase audit (2026-08-20).
These are not (yet) broken behavior — see [`BUGS.md`](./BUGS.md) for confirmed defects — but
they add complexity, risk, or maintenance cost. Grouped by area.

## Business logic

Inconsistencies found while auditing `process_url_request`'s decision tree, to be solved once
[`BUGS.md` #23](./BUGS.md#23-youtubes-mirror-link-alternative-is-incorrectly-gated-behind-download_allowed_domains-high-p1d2)
is fixed — confirmed design intent: `DOWNLOAD_ALLOWED_DOMAINS` gates real `yt-dlp` downloads
only; mirror-link rewriting should always be available regardless of the allow-list.

- [ ] **Instagram is the only mirror platform scoped to specific paths** — `apply_rewrite_map`
      (`app/url_processing.py:87-99`) matches Spotify/Reddit/TikTok/Twitter against their whole
      domain, but Instagram only against `/p/` and `/reel/`. A plain Instagram profile or story
      link therefore gets no mirror treatment at all, unlike every other platform, which is
      inconsistent with the "mirror-links always available" principle. Either document why
      Instagram is deliberately narrower (its mirror may not support other path types) or widen
      it to match the domain-wide pattern used for the rest. [P3/D1]
- [ ] **Spotify has no yt-dlp extractor**, so if an operator ever allow-lists `spotify.com` for
      real downloads, every request pays for a full `yt-dlp` startup and failure
      (`attempt_download` → `UnsupportedUrlError`, `app/url_processing.py:102-113`) before
      falling back to the mirror link — pure overhead with no chance of succeeding. Special-case
      Spotify (and any other known non-video platform) to skip the download attempt entirely and
      go straight to the mirror rewrite. [P3/D2]
- [ ] **No `YOUTUBE_REWRITE_ENABLED` toggle** — `app/config.py:18-22` defines a
      `*_REWRITE_ENABLED` setting for Instagram/Reddit/Spotify/TikTok/Twitter, but YouTube's
      rewrite (`transform_youtube_url`) has no equivalent switch. Once
      [`BUGS.md` #2](./BUGS.md#2-_rewrite_enabled-settings-are-defined-documented-and-never-read-high-p1d2)
      is fixed and the toggles actually take effect, this asymmetry means an operator can't
      disable the YouTube mirror the same way they can disable the other five. [P3/D1]
- [ ] **Download-failure fallback overclaims an "alternative" that isn't one** —
      `process_url_request`'s private-chat reply when `modified_url == final_url`
      (`app/url_processing.py:162-166`) still says "Here is an alternative link, which Telegram
      may parse better," even though the link offered is byte-for-byte identical to the original.
      Either drop the "alternative" framing for this case or state plainly that the download
      failed. [P3/D1]

## Config (`app/config.py`)

- [ ] Stop hand-rolling env parsing with `os.getenv(...)` as the default for every
      `pydantic_settings.BaseSettings` field — this bypasses pydantic-settings' own env loading,
      type coercion, and validation, and freezes values at import time (hard to override in
      tests without `monkeypatch.setattr`). Use plain typed fields (`BOT_TOKEN: str = ""`) and
      let `BaseSettings` read the environment itself. [P3/D3]
- [ ] The hand-rolled boolean parsing (`os.getenv(...).lower() not in ("false", "0", "no")`,
      `app/config.py:17-22`) treats *any* unrecognized string (typos, `""`) as `True`. Pydantic's
      built-in `bool` coercion is stricter and would surface bad env values as a startup error
      instead of silently defaulting on. [P2/D1]
- [ ] `LOG_LEVEL` (`app/config.py:23`) isn't validated against the documented set (`DEBUG`,
      `INFO`, `WARNING`, `ERROR`) — an unrecognized value reaches `logging.basicConfig`
      (`app/main.py:21`) and raises `ValueError` there instead of failing with a clear
      configuration error at the point the setting is read. Restrict the field to a `Literal` of
      the documented levels. [P3/D1]

## Dependencies (`pyproject.toml`, `uv.lock`)

- [ ] `pyyaml` is a runtime dependency but nothing under `app/` imports `yaml` (only
      `tests/test_messages.yml` exists, and it's not loaded by any test — see Tests section).
      Drop it, or move it to the `dev` group if it's meant for future fixture loading. [P3/D1]
- [ ] `aiogram` is imported directly (`app/bot.py:5`) but is **not** a declared dependency in
      `pyproject.toml` — it only arrives transitively via `aiogram-utils`. Declare and pin it
      explicitly so a version bump of the shim can't silently change the aiogram major version. [P2/D1]
- [ ] `aiogram` 2.25 is end-of-life (aiogram 3.x has been current for a while). Plan a migration;
      aiogram 2's `Dispatcher`/`executor` API used in `app/bot.py` and `app/main.py` no longer
      receives fixes. [P2/D4]
- [ ] FastAPI's `@app.on_event("startup"/"shutdown")` (`app/main.py:25-35`) is deprecated in
      favor of the `lifespan` context-manager API. [P3/D2]

## Code structure

- [ ] `process_url_request`'s `except UnsupportedUrlError` and `except Exception` branches
      (`app/url_processing.py:155-179`) build byte-for-byte identical responses. Since
      `attempt_download()` (`:102-113`) already collapses every failure mode into
      `UnsupportedUrlError`, the distinction between the two branches is meaningless — merge them
      into one and keep the real exception only for logging detail. [P3/D1]
- [ ] `sanitize_subfolder_name` (`app/download.py:111-112`) is named as if it produces a
      subfolder but actually produces a filename; rename for clarity. [P3/D1]
- [ ] `attempt_download`'s success-path reconstruction of the filename
      (`os.path.join(*video_os_path.split(os.path.sep)[-1:])`, `app/url_processing.py:106`) is a
      convoluted way to write `os.path.basename(video_os_path)`. [P3/D1]
- [ ] `is_domain_allowed` and `follow_redirects` re-derive `urlparse(...)` multiple times on the
      same string; minor, but worth consolidating once the allow-list logic is fixed (see Bug 5). [P3/D1]

## Tooling / CI

- [ ] Three overlapping/inconsistent linters are configured: `.flake8` (not run in CI — no
      flake8 job exists, only referenced from `.pre-commit-config.yaml`), a black CI job, a ruff
      CI job with no `ruff` configuration anywhere in `pyproject.toml`, and pre-commit running
      black + isort + flake8 + pytest. Consolidate onto one tool (e.g. `ruff format` + `ruff
      check`, which subsumes flake8/isort/black) and delete the rest. [P2/D3]
- [ ] No GitHub Actions workflow runs `pytest` — it only runs via the local `pre-commit` hook
      (`.pre-commit-config.yaml`, `run-pytest`), which is opt-in per contributor. Add a CI
      workflow (e.g. `.github/workflows/test-python.yml`) so the suite actually gates merges. [P1/D2]
- [ ] `.pre-commit-config.yaml`'s `name-tests-test` hook expects `test_*.py` naming, but every
      test file in the repo uses the `*_test.py` suffix (`api_test.py`, `bot_test.py`,
      `url_processing_test.py`) — this hook must be failing (or was never actually run) since
      the tests were added. [P3/D1]
- [ ] `build-and-push.yml` uses deprecated GitHub Actions patterns: `::set-output` (removed by
      GitHub, replaced by `$GITHUB_OUTPUT`), `actions/checkout@v2`,
      `docker/setup-qemu-action@v1`/`setup-buildx-action@v1`, `docker/build-push-action@v2`.
      Bump to current major versions. [P2/D2]
- [ ] The `PUSH_DOCKER_IMAGE` step in `build-and-push.yml` (`Set default value for
      env.PUSH_DOCKER_IMAGE if not defined`) exports a variable into a subshell that exits
      immediately after — it has no effect, and `build-push-action`'s `push: true` is
      unconditional anyway. Remove the dead step or wire it up for real. [P3/D1]

## Docker / Deploy

- [ ] `Dockerfile` never copies `uv.lock`, so `uv sync` re-resolves dependencies at build time
      instead of using the locked versions — builds are not reproducible across time. [P2/D1]
- [ ] `uv sync --no-dev --no-editable` runs *before* `COPY ./app /app/app`
      (`Dockerfile`), so the project's own package is installed empty/stale; the app only works
      at all because `ENV PYTHONPATH="/app"` makes the later-copied `app/` importable directly,
      bypassing the installed (empty) distribution. Reorder the `COPY`s or accept that the
      `uv sync` step is only installing third-party deps (fine, but worth a comment). [P3/D1]
- [ ] `entrypoint.sh` runs `uv run uvicorn ...`, which can trigger `uv` to re-sync/re-resolve at
      container start. Use `uv run --frozen` (or `--no-sync`) to guarantee the image's locked
      dependency set is used verbatim at runtime. [P2/D1]
- [ ] The container runs as root (no `USER` directive in `Dockerfile`). Add a non-root user. [P2/D2]
- [ ] No `HEALTHCHECK` in `Dockerfile` and no `/health` endpoint in `app/main.py` — combined with
      Bug 7 (silent polling death), there's no way for an orchestrator to detect a stuck bot. [P2/D2]
- [ ] No `.dockerignore` — `docker build` context includes `.venv/`, `__pycache__/`,
      `.ruff_cache/`, `.env`, `.git/`, etc. (all present in the repo tree today), inflating the
      build context needlessly (and `.env` in the build context next to `COPY ./pyproject.toml
      ./README.md /app/` is worth double-checking is never accidentally added). [P2/D1]
- [ ] `docker-compose.yml`'s `app` service does not pass through most of the settings
      documented in `README.md`: `CACHE_DIR`, `COOKIES_DIR`, `COOKIE_JAR_ENABLED`,
      `FOLLOW_REDIRECT_TIMEOUT`, and all five `*_REWRITE_ENABLED` flags are absent from its
      `environment:` block, so they can only ever take their code defaults in the shipped
      compose file. [P2/D2]
- [ ] No service in `docker-compose.yml` has a `restart:` policy — beyond the `cron` service
      (see `BUGS.md` #9), `app` and `nginx` will also stay down after a crash until manually
      restarted. [P2/D1]

## Cookie handling (`app/download.py`)

- [ ] Once `COOKIE_JAR_PATH` (`cookie_jar.txt`) exists, it is never refreshed from
      `cookies*.txt` again (`_resolve_cookie_path`, `app/download.py:36-44`) — rotating/updating
      cookies requires an operator to manually delete the jar file. Document this clearly (or
      add a periodic refresh/merge). [P3/D2]
- [ ] The comment-stripping filter in `_write_merged_cookies`
      (`not line.startswith("# ") and line.strip() != "#"`, `app/download.py:30`) is subtle
      (it keeps lines starting with a single `#` but no space, which is how Netscape cookie
      files often mark the `HttpOnly` prefix `#HttpOnly_domain...`) — worth a comment explaining
      the exact intent, plus a unit test. [P3/D1]

## Tests

Full audit of the current suite: see `BUGS.md` #18–#22 for defects that make specific tests
wrong or non-functional. The items below are coverage gaps and testing-infrastructure debt.

- [ ] **No `conftest.py`** — nothing isolates tests from the developer's `.env`, provides a
      dummy `BOT_TOKEN`, or blocks outbound network. A single `conftest.py` with an autouse
      fixture that (a) sets a syntactically-valid dummy `BOT_TOKEN` before any `app.*` module is
      imported and (b) pins every `*_MIRROR_DOMAIN`/`*_REWRITE_ENABLED` setting to a known value
      would fix `BUGS.md` #18 and #20 at once. [P1/D2]
- [ ] **Import-time side effects make the app hard to test** — `Bot(...)`/`Dispatcher(bot)` run
      at import time in `app/bot.py:14-15`, and `settings = Settings()` runs at import time in
      `app/config.py:39`. A factory function (e.g. `create_bot()` called from `main.py`) or lazy
      initialization would let test modules import `app.bot`/`app.main` without a real token —
      directly fixes `BUGS.md` #18. [P1/D3]
- [ ] **The core business logic has no direct test** — `process_url_request()`
      (`app/url_processing.py:116-179`, diagrammed in `docs/flows/url-processing-flow.md`) is the
      product's actual behavior and is currently only exercised indirectly (and, per `BUGS.md`
      #19, not even that) through `tests/bot_test.py`. With `follow_redirects`/`yt_dlp_download`
      mocked, each branch is a cheap, fast unit test:
  - [ ] disallowed domain, rewrite available, private chat
  - [ ] disallowed domain, rewrite available, group chat
  - [ ] disallowed domain, no rewrite available, private chat (message shown)
  - [ ] disallowed domain, no rewrite available, group chat (silent — `BUGS.md` #19 caught this
        case being asserted on incorrectly)
  - [ ] allowed domain, YouTube pattern match (short-circuits before download)
  - [ ] allowed domain, download succeeds
  - [ ] allowed domain, download raises `UnsupportedUrlError`, rewrite available/unavailable
  - [ ] allowed domain, download raises an unexpected `Exception` (generic-failure path) [P1/D3]
- [ ] **Other untested units**: `is_domain_allowed` (exact match, subdomain match, the fail-open
      trailing-comma/whitespace cases from `BUGS.md` #5), `follow_redirects` (query-stripping
      from `BUGS.md` #1, the missing non-timeout exception handling from `BUGS.md` #11),
      `app/download.py` (cookie-jar vs. temp-merged-file selection, the comment-line filter,
      `UnsupportedUrlError`/`RuntimeError` mapping for each yt-dlp exception type),
      `app/config.py` (boolean env-var parsing edge cases, e.g. `""`/typos defaulting to `True`),
      `app/api.py`'s 400-on-exception path, and the bot's reply-to-bot easter egg, multi-URL
      message, and private-chat-no-URL branches. [P2/D3]
- [ ] **No mocking strategy anywhere in the suite** — no `unittest.mock`, `pytest-mock`,
      `respx`, or `responses` in use or in `pyproject.toml`'s dev group. Every test that touches
      more than a pure string-transform function is therefore forced to hit the real network or
      real `yt-dlp`/aiogram, which is what causes `BUGS.md` #18, #19, and #21. [P2/D2]
- [ ] **No coverage measurement** — no `pytest-cov` (or equivalent) in the dev dependency group,
      no coverage threshold, no report published from CI, so gaps like the ones above are
      invisible to contributors until manually audited (as here). [P3/D2]
- [ ] `tests/url_processing_test.py`'s parametrized-table + `monkeypatch.setattr(settings, ...)`
      pattern (its "overridden settings" tests) is the right model for this codebase — the fix
      for `api_test.py` and `bot_test.py` should be to rewrite them to follow the same pattern
      (mock the collaborators, parametrize inputs/outputs) rather than patch them in place. [P2/D2]
- [ ] `pytest.ini`'s `addopts = --ignore=lib/python3.11/site-packages` refers to a
      pre-`uv` venv layout (`lib/`) that no longer exists now that the project uses `.venv/` —
      dead option, safe to remove. [P3/D1]
- [ ] `tests/bot_test.py`'s inline comments ("Set this to `private` to test private chat
      behavior", "Set to a message object if you want to test reply behavior") describe test
      cases a human is expected to enable by hand-editing the file before running it. These
      should be `@pytest.mark.parametrize` rows exercised automatically, not manual toggles. [P3/D2]
- [ ] `httpx<0.28` and `pytest-asyncio<0.25` (`pyproject.toml`) are pinned specifically to keep
      the deprecated `AsyncClient(app=app, ...)` constructor working
      (`tests/api_test.py:9-10`); modern `httpx` requires `ASGITransport`. Migrating unblocks
      dependency updates. [P3/D2]
- [ ] `pytest.ini` does not set `asyncio_mode` (relies on `pytest.mark.asyncio` per-test, which
      is fine, but worth being explicit given `pytest-asyncio`'s strict/auto mode footguns). [P3/D1]
- [ ] `tests/test_messages.yml` is a stale manual fixture file: it references
      `ddinstagram.com` (current mirror default is `kkinstagram.com`,
      `app/config.py:28`) and reply text (`"I failed to download the file by myself"`) that no
      longer matches any string in `app/url_processing.py`. Nothing in the test suite loads this
      file (it's not referenced by any `*_test.py`). Either wire it into a real
      parametrized test or delete it. [P3/D1]
- [ ] The local dev `.venv` currently can't even build its own dependencies
      (`aiohttp` 3.8.6 fails to compile against Python 3.14, missing `Python.h`), so
      `uv run pytest` fails before collection on at least one maintainer machine — another
      reason a CI test job (see Tooling/CI above) is needed to keep the suite's actual status
      visible, rather than relying on whoever's laptop happens to already have a working
      environment. [P2/D2]

## Docs

- [ ] `README.md`'s License section links `[LICENSE](LICENSE)`, but the file in the repo is
      named `LICENCE` (British spelling) — the link is broken on GitHub (case/path-sensitive). [P3/D1]
- [ ] `README.md` step 4 says `docker-compose up -d` (the standalone v1 binary/hyphenated
      command); the rest of the project (and the user's own tooling conventions) uses
      `docker compose` (v2 plugin syntax). [P3/D1]
- [ ] `README.md`'s environment variable table documents `INSTAGRAM_REWRITE_ENABLED`,
      `REDDIT_REWRITE_ENABLED`, `SPOTIFY_REWRITE_ENABLED`, `TIKTOK_REWRITE_ENABLED`,
      `TWITTER_REWRITE_ENABLED` as working toggles — see `BUGS.md` #2, they currently have no
      effect. Either fix the code or remove these rows until it does. [P2/D1]
- [ ] `README.md` does not document `FILE_TTL`, `FILE_TTL_TYPE`, `PUBLIC_PORT`, or
      `GLOBAL_DATA_FOLDER`, all of which are used in `docker-compose.yml` and needed for a
      working deployment. Also doesn't mention `cleanup.sh` at all (see `BUGS.md` #10). [P3/D1]
- [ ] The README's "Example Response" for the REST API
      (`{"status": "success", "data": "https://example.com/processed-url"}`) doesn't match the
      actual response shape produced by `process_url_request` (a Markdown string with emoji and
      `[text](url)` links, per `tests/test_messages.yml`'s captured examples) — misleading for
      anyone integrating against the API from the docs alone. [P3/D1]
- [ ] An `ADMIN_CHAT_ID` environment variable is set in the maintainer's local `.env` but is
      never read anywhere in `app/`, never mentioned in `README.md`, and never passed through
      `docker-compose.yml`. Either it's a leftover from a removed/never-finished feature (e.g.
      error reporting to an admin chat) and should be dropped from `.env`, or it's an
      undocumented planned feature that should be implemented and documented. [P3/D1]
