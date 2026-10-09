# UFB-0038. Cookie keepalive

**Tags:** #cookies #ops #runtime

## User Story

As an operator running authenticated downloads, I want the bot to periodically check that my cookie sessions are still logged in and refresh them, so that cookies don't silently expire during quiet periods and I find out when they do.

## Behavior

- Active only when `COOKIE_JAR_ENABLED=true` and `COOKIE_KEEPALIVE_INTERVAL > 0` (default `3600` seconds; `0` disables). Without the jar there is nowhere to persist refreshed cookies, so no thread starts and `/health` reports `"cookies": null`.
- Every interval a background thread:
  1. **Source change** — if any `cookies*.txt` is newer than the last merge (recorded in the `cookie_jar.sources` sidecar next to the jar), rebuilds the whole jar from the source files (resolves [UFB-0018](UFB-0018-persistent-cookie-jar.md)'s "never refreshed" gap). With no sidecar yet, the jar's own mtime is the baseline.
  2. **Check** — for each known site that has cookies in the jar, requests a logged-in-only page with those cookies (no redirects followed, 5 s timeout). Result per site: alive, logged out, or unknown (network error, 5xx, unexpected response — unknown never triggers a re-seed). The jar is saved afterwards so refreshed `Set-Cookie` values persist.
  3. **Re-seed on failure** — for a logged-out site, replaces only that site's cookies in the jar with those from `cookies*.txt`, saves, and re-checks once.
- Overall state: `false` if any site is logged out, `true` if at least one was checked and all are alive, otherwise `null`.
- Known sites: Instagram (`/accounts/edit/`), YouTube (`/account`), TikTok (`/passport/web/account/info/`), Reddit (`/api/me.json`: a JSON object with a `data.name` is logged in, an object without `data` is logged out).
- Reddit's API client ([UFB-0057](UFB-0057-reddit-links.md)) reads its cookies from the jar when the jar is enabled, so refreshed values reach it; it never takes the jar lock, and falls back to the `cookies*.txt` files if the jar is missing or unreadable.
- `GET /health` ([UFB-0034](UFB-0034-health-endpoints.md)) always includes `"cookies": true|false|null`. It only returns `503` for `cookies: false` when `COOKIE_HEALTHCHECK=true` (default `false`). `cookies` is also `false` if keepalive is enabled but its thread has died.

## Implementation

- `app/cookie_keepalive.py` — thread lifecycle modelled on `app/cleanup.py` (`start_keepalive`, `stop_keepalive`, `is_keepalive_alive`), plus `check_once()` (one tick) and `cookies_alive()` (last result for `/health`). Jar I/O uses `yt_dlp.cookies.YoutubeDLCookieJar` so the file format matches what yt-dlp writes.
- `app/download.py` — `COOKIE_JAR_LOCK` is held around jar-mode downloads so yt-dlp and the keepalive never write `cookie_jar.txt` concurrently.
- `app/config.py` — `COOKIE_KEEPALIVE_INTERVAL`, `COOKIE_HEALTHCHECK`.
- `app/main.py` — starts/stops the thread in `lifespan`.
- `app/api.py` — adds the `cookies` field and the opt-in degrade to `/health`.

## Quirks & Decisions

- Quirk: the jar lock is held across the network checks, so a download that starts mid-tick waits up to a few seconds. Open: acceptable for hourly checks; revisit if checks grow slower.
- Quirk: site check URLs are best-effort and may break when a platform changes its login flow; an unrecognized response reads as unknown, never as dead. Open: add sites by extending `SITES` in `app/cookie_keepalive.py`.
- A source-file change rebuilds the whole jar, discarding refreshed tokens — the operator's newly supplied cookies win.

## Testing

### Human

- Set `COOKIE_JAR_ENABLED=true`, `COOKIE_KEEPALIVE_INTERVAL=60`, run `make run` with a real `cookies.txt`: logs show a per-site result and `curl localhost:8000/health` shows `"cookies": true`.
- Corrupt the Instagram `sessionid` in the jar: the next tick logs the site as logged out and re-seeds it from `cookies.txt`.
- Corrupt the source file too with `COOKIE_HEALTHCHECK=true`: `/health` returns `503`.

### Unit

- Each site's response classifier: alive, logged-out redirect, 5xx/exception → unknown; Reddit: `data.name` → alive, `{}` → logged out, 403/non-JSON → unknown.
- Newer source files rebuild the jar; unchanged sources leave it alone.
- A logged-out site is re-seeded alone, other sites' cookies are kept, and it is re-checked once.
- Refreshed `Set-Cookie` values are persisted to the jar.
- No known site in the jar → `null`; disabled config → thread not started and `cookies_alive()` is `None`.
- `/health`: `cookies: false` is `200` by default and `503` with `COOKIE_HEALTHCHECK=true`.

## Status

Implemented
