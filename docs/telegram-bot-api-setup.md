# Setting up a local Telegram Bot API server

Operator runbook for
[UFB-0036](features/UFB-0036-native-video-replies.md).
Leave `TELEGRAM_API_URL` unset and native video replies still work — up to
Telegram's cloud API ceiling of 50 MB per file. Follow this guide only if you
want to send larger files.

## Overview

Telegram's cloud Bot API caps any file a bot sends at 50 MB. Running your own
[Bot API server](https://github.com/tdlib/telegram-bot-api) in **local mode**
lifts that to 2000 MB. `app` also hands it a **path on disk** instead of
uploading the bytes itself when a local server is active — which is why
`docker-compose.yml`'s `telegram-bot-api` service shares the same `cache`
volume as `app`, mounted at the identical path: a bare path only means
anything to the local server if it resolves to the same file there.

A bot can only be registered with one Bot API server at a time. Telegram
requires you to explicitly log the bot out of the cloud API before a local
server will accept it, and the reverse to move back — both are one `curl`
call, covered below.

## Steps

1. Get **API credentials** for your own Telegram account at
   <https://my.telegram.org> → **API development tools** → create an app.
   This gives you `api_id`/`api_hash` — these are account credentials, not a
   bot token; the local server needs them to talk to Telegram's data centers
   on your bot's behalf.
2. Copy them into `.env`, alongside the compose profile's other settings:

   ```dotenv
   TELEGRAM_API_ID=1234567
   TELEGRAM_API_HASH=abcdef0123456789abcdef0123456789
   TELEGRAM_API_URL=http://telegram-bot-api:8081
   LOCAL_SEND_VIDEO_MAX_MB=500
   ```

   `LOCAL_SEND_VIDEO_MAX_MB` only takes effect once the local server is
   actually reachable — files at or under `CLOUD_SEND_VIDEO_MAX_MB` (default
   10 MB) are already sent natively regardless, local server or not.

   `TELEGRAM_API_URL` must be reachable from the `app` container — the
   service name on the shared compose network, not `localhost`.
3. Log the bot **out of the cloud API** — required once, before its first
   local-mode start; the cloud API refuses to serve a bot session the local
   server is also trying to hold, and vice versa:

   ```sh
   curl -sS "https://api.telegram.org/bot<BOT_TOKEN>/logOut"
   ```

   A successful call returns `{"ok":true,"result":true}`. Do this from
   wherever you have network access to `api.telegram.org` — it doesn't need
   to run on the host.
4. Start the `telegram-bot-api` service — it's gated behind the
   `local-bot-api` compose profile, so a plain `docker compose up -d` never
   starts it. `app` depends on `telegram-bot-api` reaching `healthy`
   (`required: false`, so this has no effect when the profile is inactive),
   so this one command also holds `app`'s (re)start until the local server
   is actually up:

   ```sh
   sudo docker compose --profile local-bot-api up -d
   ```
5. Check the logs for a clean start and the bot's first local-mode request:

   ```sh
   sudo docker compose logs -f telegram-bot-api
   ```

   A `Bad Request: Unauthorized` at this point almost always means step 3
   didn't happen yet — the cloud API still holds the session. A
   `PHONE_NUMBER_INVALID`/`API_ID_INVALID` error means `TELEGRAM_API_ID`/
   `TELEGRAM_API_HASH` are wrong or weren't picked up (recheck `.env` and
   that the container was recreated, not just restarted).

   The service also carries a Docker healthcheck (a bare TCP connect to its
   port — every real HTTP route 404s/401s without a valid bot token, so an
   HTTP-status check would always read "down"):

   ```sh
   sudo docker compose ps telegram-bot-api
   ```

   should show `healthy` within a few seconds of a clean start.
6. `app` should already have picked up `TELEGRAM_API_URL` and reconnected
   through the local server as part of step 4's `up -d`. If it didn't (e.g.
   `TELEGRAM_API_URL` was added to `.env` after `app` was already running),
   recreate it explicitly:

   ```sh
   sudo docker compose up -d app
   ```
7. Send the bot a URL for a file over 50 MB and confirm it still arrives as a
   native, playable video — this is the only way to confirm path-based
   sending is actually working, since a file under 50 MB would have sent
   fine over the cloud API too and wouldn't prove anything.

## Reverting to the cloud API

1. Log the bot out of the **local** server instead of the cloud one:

   ```sh
   curl -sS "http://telegram-bot-api:8081/bot<BOT_TOKEN>/logOut"
   ```

   (Run this from inside the compose network, e.g.
   `sudo docker compose exec app curl -sS http://telegram-bot-api:8081/bot<BOT_TOKEN>/logOut`
   — the local server usually isn't published on a host port.)
2. Clear `TELEGRAM_API_URL` in `.env`, then `sudo docker compose up -d app`
   — with no local server configured, only `CLOUD_SEND_VIDEO_MAX_MB` (10 MB)
   applies again; `LOCAL_SEND_VIDEO_MAX_MB` is simply unused until you
   reconnect a local server.
3. Stop the now-unused service:

   ```sh
   sudo docker compose --profile local-bot-api down telegram-bot-api
   ```

## Notes

- The local server's own data directory is the `botapi` named volume — safe
  to leave in place across restarts (it holds the bot's session state), but
  removing it is equivalent to logging out.
- `telegram-bot-api` and `app` must mount the `cache` volume at the **same
  path** in both containers. aiogram's default file-path handling passes a
  local send's path straight through to the local server unchanged; a
  mismatched mount point means the server looks for the file somewhere it
  doesn't exist.
- If the local server dies while `TELEGRAM_API_URL` is set, `app` keeps
  polling through it — aiogram's own `getUpdates` loop retries with backoff
  against the same endpoint and resumes automatically once it's reachable
  again, no restart needed. What's unavailable for the duration is native
  sends above `CLOUD_SEND_VIDEO_MAX_MB` (they fall back to the text/link
  reply, same as if `TELEGRAM_API_URL` had never been set) — that also
  self-heals the moment the local server answers again. `app` does **not**
  swap onto the cloud API while the local server is down: Telegram requires
  an explicit `logOut` against the local server first (see "Reverting to
  the cloud API" above), which a dead server can't answer, so an automatic
  swap can't work and isn't attempted. `GET /health`'s `telegram_api` field
  reflects whether the local server is currently reachable — see
  [UFB-0034](features/UFB-0034-health-endpoints.md) and
  [UFB-0036](features/UFB-0036-native-video-replies.md#if-the-local-server-dies).
- No `TELEGRAM_API_ID`/`TELEGRAM_API_HASH`/`TELEGRAM_API_URL` set → the bot
  uses Telegram's cloud API exactly as before this feature existed, capped
  at 50 MB per send.
