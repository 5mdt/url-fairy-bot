# TODO / Tech Debt

Cleanups, simplifications, and missing coverage. Behavior actually misbehaving today goes in
`docs/BUGS.md` instead. Entries are deleted when done (the fix gets a `docs/CHANGELOG.md` bullet);
IDs are never reused or renumbered, so deletions leave gaps. Next free ID: **TODO-0038**.

Each entry ends with a `[P#/D#]` marker:

```
Priority:   P1 = high     P2 = medium   P3 = low
Difficulty: D1 = trivial  D2 = small    D3 = medium   D4 = large
```

## Business logic

Design intent, confirmed against `process_url_request`'s decision tree: `DOWNLOAD_ALLOWED_DOMAINS`
gates real `yt-dlp` downloads only — empty means every domain is allowed, the default. Mirror-link
rewriting is a separate, independent gate, `REWRITE_ALLOWED_DOMAINS` (see
[UFB-0023](features/UFB-0023-rewrite-domain-allowlist.md)) — empty there also means every platform
is rewritten. Neither list affects the other, and YouTube is no longer special-cased: it is subject
to both gates exactly like every other platform (2026-08-22).

- #TODO-0001 Instagram is the only mirror platform scoped to specific paths — `apply_rewrite_map`
  (`app/url_processing.py`) matches Spotify/Reddit/TikTok/Twitter/YouTube against their whole
  domain, but Instagram only against `/p/` and `/reel/`. A plain Instagram profile or story link
  therefore gets no mirror treatment at all, unlike every other platform. Either document why
  Instagram is deliberately narrower or widen it to the domain-wide pattern used for the rest
  [P3/D1]
- #TODO-0002 Spotify has no yt-dlp extractor, so if an operator ever allow-lists `spotify.com` for
  real downloads, every request pays for a full `yt-dlp` startup and failure
  (`attempt_download` → `UnsupportedUrlError`, `app/url_processing.py`) before falling back
  to the mirror link — pure overhead with no chance of succeeding. Special-case Spotify (and any
  other known non-video platform) to skip the download attempt and go straight to the mirror
  rewrite [P3/D2]
- #TODO-0004 the download-failure fallback overclaims an "alternative" that isn't one —
  `process_url_request`'s reply when `modified_url == final_url` after a download failure
  (`app/url_processing.py:212-216`) still says "Here is an alternative link, which Telegram may
  parse better," even though the link offered is byte-for-byte identical to the original. Either
  drop the "alternative" framing for this case or state plainly that the download failed [P3/D1]
- #TODO-0037 the platform/YouTube rewrite rules in `apply_rewrite_map` (`app/url_processing.py`)
  are a hardcoded list of `(regex, replacement)` tuples, one per platform — adding a new mirror
  site means editing code. Consider making rewrite rules dynamically configurable, e.g. an
  operator-supplied list of `{match_regex, mirror_domain}` rules (via env var or config file)
  instead of one Python tuple per platform [P3/D3]

## Config (`app/config.py`)

- #TODO-0005 every field hand-rolls its own `os.getenv(...)` default instead of letting
  `pydantic_settings.BaseSettings` read the environment itself. This mostly works in practice —
  `tests/config_test.py` confirms that when an env var *is* set, pydantic-settings' own env source
  still overrides the hand-rolled default and applies pydantic's stricter coercion/validation (a
  bad `COOKIE_JAR_ENABLED` value raises `pydantic.ValidationError` at startup, it does not silently
  default to `True` as an earlier version of this doc assumed) — but the pattern is still redundant
  with what `BaseSettings` already does, and the class-level `os.getenv(...)` default is frozen at
  import time regardless. Use plain typed fields (`BOT_TOKEN: str = ""`) [P3/D2]
- #TODO-0006 `LOG_LEVEL` (`app/config.py:37`) isn't validated against the documented set (`DEBUG`,
  `INFO`, `WARNING`, `ERROR`) — an unrecognized value reaches `logging.basicConfig`
  (`app/main.py:16`) and raises `ValueError` there instead of failing with a clear configuration
  error at the point the setting is read. Restrict the field to a `Literal` of the documented
  levels [P3/D1]

## Dependencies (`pyproject.toml`)

- #TODO-0007 `pyyaml` is a runtime dependency (`pyproject.toml:18`) but nothing under `app/`
  imports `yaml` (only `tests/test_messages.yml` exists, and it's not loaded by any test — see
  Tests section). Drop it, or move it to the `dev` group if it's meant for future fixture loading
  [P3/D1]

## Code structure

- #TODO-0008 `sanitize_subfolder_name` (`app/download.py:112-113`) is named as if it produces a
  subfolder but actually produces a filename; rename for clarity [P3/D1]
- #TODO-0009 `attempt_download`'s success-path reconstruction of the filename
  (`os.path.join(*video_os_path.split(os.path.sep)[-1:])`, `app/url_processing.py:156`) is a
  convoluted way to write `os.path.basename(video_os_path)` [P3/D1]
- #TODO-0010 `is_domain_allowed`, `is_rewrite_allowed`, and `follow_redirects`
  (`app/url_processing.py`) each re-derive `urlparse(...)` multiple times on the same string;
  minor, but worth consolidating now that the allow-list matching itself is correct [P3/D1]

## Tooling / CI

- #TODO-0011 three overlapping/inconsistent linters are configured: `.flake8` (not run in CI — no
  flake8 job exists, only referenced from `.pre-commit-config.yaml`), a black CI job
  (`lint-python-black.yml`), a ruff CI job (`lint-python-ruff.yml`) with no `ruff` configuration
  anywhere in `pyproject.toml`, and pre-commit running black + isort + flake8 + pytest. Consolidate
  onto one tool (e.g. `ruff format` + `ruff check`, which subsumes flake8/isort/black) and delete
  the rest [P2/D3]
- #TODO-0012 no GitHub Actions workflow runs `pytest` — it only runs via the local `pre-commit`
  hook (`.pre-commit-config.yaml`'s `run-pytest`), which is opt-in per contributor. Add a CI
  workflow (e.g. `.github/workflows/test-python.yml`) so the suite actually gates merges [P1/D2]
- #TODO-0013 `.pre-commit-config.yaml`'s `name-tests-test` hook expects `test_*.py` naming, but
  every test file in the repo uses the `*_test.py` suffix (`api_test.py`, `bot_test.py`,
  `config_test.py`, `download_test.py`, `url_processing_test.py`) — this hook must be failing (or
  was never actually run) since the tests were added [P3/D1]
- #TODO-0014 `build-and-push.yml` uses deprecated GitHub Actions patterns: `::set-output` (removed
  by GitHub, replaced by `$GITHUB_OUTPUT`), `actions/checkout@v2`,
  `docker/setup-qemu-action@v1`/`setup-buildx-action@v1`, `docker/build-push-action@v2`. Bump to
  current major versions [P2/D2]
- #TODO-0015 the `PUSH_DOCKER_IMAGE` step in `build-and-push.yml` ("Set default value for
  env.PUSH_DOCKER_IMAGE if not defined") exports a variable into a subshell that exits immediately
  after — it has no effect, and `build-push-action`'s `push: true` is unconditional anyway. Remove
  the dead step or wire it up for real [P3/D1]

## Docker / Deploy

- #TODO-0016 `Dockerfile` never copies `uv.lock`, so `uv sync` re-resolves dependencies at build
  time instead of using the locked versions — builds are not reproducible across time [P2/D1]
- #TODO-0017 `uv sync --no-dev --no-editable` (`Dockerfile:16`) runs *before* `COPY ./app /app/app`
  (`:19`), so the project's own package is installed empty/stale; the app only works at all because
  `ENV PYTHONPATH="/app"` makes the later-copied `app/` importable directly, bypassing the
  installed (empty) distribution. Reorder the `COPY`s or accept that `uv sync` is only installing
  third-party deps (fine, but worth a comment) [P3/D1]
- #TODO-0018 `entrypoint.sh` runs `uv run uvicorn ...`, which can trigger `uv` to re-sync/re-resolve
  at container start. Use `uv run --frozen` (or `--no-sync`) to guarantee the image's locked
  dependency set is used verbatim at runtime [P2/D1]
- #TODO-0019 the container runs as root (no `USER` directive in `Dockerfile`). Add a non-root user
  [P2/D2]
- #TODO-0020 no `HEALTHCHECK` in `Dockerfile` and no `/health` endpoint in `app/main.py` —
  combined with `docs/BUGS.md` BUG-0007 (silent polling death), there's no way for an orchestrator
  to detect a stuck bot [P2/D2]
- #TODO-0021 no `.dockerignore` — `docker build` context includes `.venv/`, `__pycache__/`,
  `.ruff_cache/`, `.env`, `.git/`, etc., inflating the build context needlessly (and `.env` in the
  build context next to `COPY ./pyproject.toml ./README.md /app/` is worth double-checking is
  never accidentally added) [P2/D1]
- #TODO-0022 `docker-compose.yml`'s `app` service does not pass through most of the settings
  documented in `README.md`: `CACHE_DIR`, `COOKIES_DIR`, `COOKIE_JAR_ENABLED`,
  `FOLLOW_REDIRECT_TIMEOUT`, and `REWRITE_ALLOWED_DOMAINS` are absent from its `environment:`
  block, so they can only ever take their code defaults in the shipped compose file [P2/D2]
- #TODO-0023 no service in `docker-compose.yml` has a `restart:` policy — beyond the `cron`
  service (see `docs/BUGS.md` BUG-0009), `app` and `nginx` will also stay down after a crash until
  manually restarted [P2/D1]

## Cookie handling (`app/download.py`)

- #TODO-0024 once `COOKIE_JAR_PATH` (`cookie_jar.txt`) exists, it is never refreshed from
  `cookies*.txt` again (`_resolve_cookie_path`, `app/download.py:37-45`) — rotating/updating
  cookies requires an operator to manually delete the jar file. Document this clearly (or add a
  periodic refresh/merge) [P3/D2]
- #TODO-0025 the comment-stripping filter in `_write_merged_cookies`
  (`not line.startswith("# ") and line.strip() != "#"`, `app/download.py:31`) is subtle — it keeps
  lines starting with a single `#` but no space, which is how Netscape cookie files often mark the
  `HttpOnly` prefix (`#HttpOnly_domain...`). `tests/download_test.py` now covers this behavior, but
  the code itself still has no comment explaining the intent — worth adding one [P3/D1]

## Tests

- #TODO-0026 import-time side effects still make parts of the app hard to test cleanly — `Bot(...)`
  /`Dispatcher()` run at import time in `app/bot.py:16-17`, and `settings = Settings()` runs at
  import time in `app/config.py:53`. `tests/conftest.py` now works around the resulting collection
  failure with `os.environ.setdefault("BOT_TOKEN", ...)` before any `app.*` import, which is
  sufficient for the test suite, but a factory function (e.g. `create_bot()` called from
  `main.py`) or lazy initialization would remove the need for that workaround entirely [P2/D3]
- #TODO-0027 no coverage measurement — no `pytest-cov` (or equivalent) in the dev dependency
  group, no coverage threshold, no report published from CI, so any remaining gaps are invisible to
  contributors until manually audited [P3/D2]
- #TODO-0028 `pytest.ini`'s `addopts = --ignore=lib/python3.11/site-packages` refers to a
  pre-`uv` venv layout (`lib/`) that no longer exists now that the project uses `.venv/` — dead
  option, safe to remove [P3/D1]
- #TODO-0029 `httpx<0.28` and `pytest-asyncio<0.25` (`pyproject.toml`) are still pinned as if
  `tests/api_test.py` used the deprecated `AsyncClient(app=app, ...)` constructor, but it already
  uses the modern `ASGITransport` — `AsyncClient(transport=ASGITransport(app=app), ...)`. The pins
  look like leftovers from before that migration; verify current `httpx`/`pytest-asyncio` majors
  work and drop the upper bounds [P3/D1]
- #TODO-0030 `pytest.ini` does not set `asyncio_mode` (relies on `pytest.mark.asyncio` per-test,
  which is fine, but worth being explicit given `pytest-asyncio`'s strict/auto mode footguns)
  [P3/D1]
- #TODO-0031 `tests/test_messages.yml` is a stale manual fixture file: it references
  `ddinstagram.com` (current mirror default is `kkinstagram.com`, `app/config.py:42`) and reply
  text ("I failed to download the file by myself") that no longer matches any string in
  `app/url_processing.py`. Nothing in the test suite loads this file. Either wire it into a real
  parametrized test or delete it [P3/D1]

## Docs

- #TODO-0032 `README.md`'s License section links `[LICENSE](LICENSE)`, but the file in the repo is
  named `LICENCE` (British spelling) — the link is broken on GitHub (case/path-sensitive) [P3/D1]
- #TODO-0033 `README.md` step 4 says `docker-compose up -d` (the standalone v1 binary/hyphenated
  command); the rest of the project (and the user's own tooling conventions) uses `docker compose`
  (v2 plugin syntax) [P3/D1]
- #TODO-0034 `README.md` does not document `FILE_TTL`, `FILE_TTL_TYPE`, `PUBLIC_PORT`, or
  `GLOBAL_DATA_FOLDER`, all of which are used in `docker-compose.yml` and needed for a working
  deployment. Also doesn't mention `cleanup.sh` at all (see `docs/BUGS.md` BUG-0010) [P3/D1]
- #TODO-0035 the README's "Example Response" for the REST API
  (`{"status": "success", "data": "https://example.com/processed-url"}`) doesn't match the actual
  response shape produced by `process_url_request` (a Markdown string with emoji and
  `[text](url)` links, per `tests/test_messages.yml`'s captured examples) — misleading for anyone
  integrating against the API from the docs alone [P3/D1]
- #TODO-0036 an `ADMIN_CHAT_ID` environment variable is set in the maintainer's local `.env` but is
  never read anywhere in `app/`, never mentioned in `README.md`, and never passed through
  `docker-compose.yml`. Either it's a leftover from a removed/never-finished feature (e.g. error
  reporting to an admin chat) and should be dropped from `.env`, or it's an undocumented planned
  feature that should be implemented and documented [P3/D1]
