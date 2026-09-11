# UFB-0036. Native Telegram video replies via a local Bot API server

**Tags:** #telegram #ux #hosting #media

**Priority:** P1 (high)

## Behavior

When a downloaded file is small enough to send, the bot replies with a
native Telegram video (`sendVideo`) instead of only a watch-page link.
Telegram's own player then handles playback — no Instant View, no template,
no `og:video` size limits (see [UFB-0032](UFB-0032-telegram-instant-view-embeds.md),
which those limits still bind). Every reply — a native video's caption or a
plain text fallback alike — always carries the same two links:

```text
⏬ Download

📎 Source
```

("Download" points at the watch page — or the `t.me/iv?...` link when
`IV_RHASH` is set; "Source" at the original URL the user sent.) So no
outcome ever leaves the user without a way to get the file.

Three size tiers decide whether a native send is even attempted:

| File size                                                              | Behavior                                                                                                                                              |
|------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------|
| ≤ `CLOUD_SEND_VIDEO_MAX_MB` (default 10)                               | Always attempted natively.                                                                                                                            |
| `CLOUD_SEND_VIDEO_MAX_MB` – `LOCAL_SEND_VIDEO_MAX_MB` (default 10–500) | Attempted natively only if a local Bot API server (`TELEGRAM_API_URL`) is configured **and** currently reachable.                                     |
| > `LOCAL_SEND_VIDEO_MAX_MB` (default 500)                              | Never attempted — the bot replies with "I cannot upload attachment this big now, use link below to watch or download" plus the Download/Source links. |

A native send that's attempted but fails (probe error, upload error,
anything) falls back to the plain text reply, same as a declined attempt —
sending is always a pure addition on top of the text reply, never a new way
to fail outright. On the local backend specifically, a failed path-based
attempt is retried once as a real upload before falling back to text — see
"Local-path send failures" below.

**Constraint that shapes the tiering:** a Telegram bot token is logged into
exactly one Bot API backend at a time — cloud *or* a self-hosted local one,
never both. (Confirmed directly: with the local server active, the cloud API
returns `Unauthorized` until the bot calls `logOut` there, and vice versa —
see [docs/telegram-bot-api-setup.md](../telegram-bot-api-setup.md).) So this
feature never picks "cloud vs. local" per message; it only decides whether
the one backend currently active should be trusted with a file of this size.
Below `CLOUD_SEND_VIDEO_MAX_MB` that's always true (small enough for either
backend). Above it, only a *reachable* local server justifies the attempt —
a bare cloud session was never going to carry that size anyway (its real
ceiling is 50 MB, but this tier's whole point is a deliberately lower,
operator-chosen cutoff for what an unassisted cloud API should be asked to
carry).

### If the local server dies

Polling itself needs no help here: aiogram's `Dispatcher._listen_updates`
already retries `getUpdates` forever with backoff and resets automatically
once the same endpoint answers again ("you may not worry that the polling
will stop working" — its own docstring). So a `TELEGRAM_API_URL`-configured
bot whose local server drops **and comes back** keeps polling — and once it
comes back, resumes both receiving messages and native sends up to
`LOCAL_SEND_VIDEO_MAX_MB` — with no code on our side involved.

What genuinely doesn't recover on its own is native sends *while* the local
server is down: `_fits_native_send`'s mid tier checks
`is_telegram_api_reachable()` live on every message, so it correctly falls
back to the text reply for the duration — no operator action needed, this
self-heals the moment the server is reachable again.

An earlier version of this feature also tried to swap the bot onto the
cloud API automatically while the local server was down, to get sends up to
`CLOUD_SEND_VIDEO_MAX_MB` working too. That doesn't work: moving a bot
*onto* the cloud API — even temporarily — requires an explicit `logOut`
call against the **local** server first (see
[docs/telegram-bot-api-setup.md](../telegram-bot-api-setup.md#reverting-to-the-cloud-api))
— exactly the call a dead local server can't answer. Removed; don't
re-attempt an automatic backend swap without solving that first.
`GET /health`'s `telegram_api` field reflects reachability directly
(`false` means the configured local server is currently down — see
[UFB-0034](UFB-0034-health-endpoints.md)), which is enough to alert an
operator if the outage is prolonged.

### Local-path send failures

Observed live: a path-based send to a reachable, healthy local server can
still fail with `Bad Request: invalid file HTTP URL specified: URL host is empty` for a file that is genuinely present and readable at the expected
path (see [BUGS #76](../BUGS.md)). Root cause undiagnosed — direct
reproduction against the same file with the real request shape succeeded,
but inconclusively: the local server validates `chat_id` before it resolves
the `video` field, so every reproduction attempt (necessarily against a
fake chat, since re-sending to a real one wasn't an option for debugging)
short-circuited before ever reaching file resolution.

`_reply_with_video` treats this the same as any other local-path failure:
one retry as a real upload (`FSInputFile`) before giving up to the text
reply. This masks the symptom rather than fixing the cause — if it turns
out to correlate with something identifiable (file size, a particular
platform's filename shape, load on the local server), narrow the fix
instead of leaning on the retry indefinitely.

## Implementation

- `app/config.py`: `TELEGRAM_API_URL` (empty = cloud API, the default),
  `CLOUD_SEND_VIDEO_MAX_MB` (default `10`), `LOCAL_SEND_VIDEO_MAX_MB`
  (default `500`).
- `app/bot.py`:
  - `_build_session()` returns `None` (aiogram's default cloud session)
    when `TELEGRAM_API_URL` is unset, otherwise an `AiohttpSession` pointed
    at it via `TelegramAPIServer.from_base(url, is_local=True)`.
  - `_make_bot(use_local)` builds a fresh `Bot` on the requested backend.
    The module-level `bot` is reassigned (never mutated in place) whenever
    the active backend changes — there is no way to redirect a live
    session, per the constraint above.
  - `start_polling()` decides the *starting* backend from a live
    reachability check (`is_telegram_api_reachable()`), not just whether
    `TELEGRAM_API_URL` is set — so a local server that's already dead at
    boot doesn't get tried first. There is no in-process recovery after
    that; see "If the local server dies" above.
  - `_fits_native_send(size_mb)` implements the three-tier send decision
    above; the mid tier calls `is_telegram_api_reachable()` (off the event
    loop, `asyncio.to_thread`) to require a live local server, not just a
    configured one.
  - `_reply_with_video()` does the send mechanics: probe, thumbnail, and
    `reply_video`, tried against up to two `video` values in order. When
    the active session is local (`_using_local_api`), the first attempt
    passes the media path as a plain `str` rather than wrapping it in
    `FSInputFile` — aiogram hands a bare string straight to the Bot API
    server's `sendVideo` as a local file path instead of reading and
    uploading the bytes itself, which is what actually makes a local-mode
    send skip the upload (see the `docker-compose.yml` bullet below for
    why this requires the shared `cache` mount). If that attempt fails —
    always on the cloud backend, or when the local-path attempt errors for
    any reason (see "Local-path send failures" above) — it's retried once
    as a real upload (`FSInputFile`); only if that also fails does
    `_reply_with_video` give up. `thumbnail` always stays an `FSInputFile`,
    on both backends and both attempts: aiogram's `SendVideo.thumbnail` is
    typed strictly as `InputFile`, unlike `video` (`str | InputFile`) — a
    bare path there fails pydantic validation (`is_instance_of`)
    regardless of backend (hit live in production; an earlier version of
    this fix sent the thumbnail path too). The thumbnail is small
    (≤200 KB) anyway, so always uploading it costs nothing. No size logic
    here; `_reply_with_video` always attempts and reports success/failure.
  - `_deliver_result()` ties it together per `handle_message` result: stats
    the file, replies with the "too large" notice above
    `LOCAL_SEND_VIDEO_MAX_MB`, otherwise attempts a native send when
    `_fits_native_send` allows it, and falls back to the plain text reply
    (`result.text`) on any decline or failure. A file that can't be stat'd
    (`os.path.getsize` raising) is treated the same as "don't attempt" —
    text-only fallback, never a crash.
- `attempt_download`/`process_url_request` (`app/url_processing.py`) return
  a `DownloadResult(text, media_path)` — `text` is the Download/Source block
  above, rendered via `app.messages.download_result()`
  ([UFB-0037](UFB-0037-message-templates.md)), `media_path` the on-disk file.
  `app/api.py`'s HTTP response shape is unchanged (it only ever used `.text`).
- `app/media.py`: `probe()` wraps `ffprobe` for width/height/duration, with
  the same defensive shape as `preview.generate_preview` — never raises,
  returns `None` on a missing binary/timeout/non-zero exit, so a failed
  probe just sends without those hints rather than failing the reply.
- `docker-compose.yml`: a `telegram-bot-api` service
  (`aiogram/telegram-bot-api`, `TELEGRAM_LOCAL=1`), internal-only (no
  Traefik labels), sharing the `cache` volume with `app` at the identical
  mount path — required for the path-based (non-upload) send above:
  `_reply_with_video`'s bare-string path is only meaningful to the local
  server if it resolves to the same file there. Gated behind the
  `local-bot-api` compose profile, so a plain `docker compose up -d`
  never starts it; enabling it is `docker compose --profile local-bot-api up -d` after the migration below.
- Health: the `telegram-bot-api` service carries its own Docker
  `healthcheck` (`nc -z 127.0.0.1 8081` — a bare TCP connect, since every
  real HTTP route 404s/401s without a valid bot token and would make an
  HTTP-status check always read "down"). `app` depends on it at the compose
  level too: `depends_on: telegram-bot-api: condition: service_healthy, required: false`. Plain `condition: service_healthy` (no `required: false`)
  was tried first and rejected — Compose refuses to even build the project
  when a profile-less service depends on one gated behind an inactive
  profile (verified directly — `docker compose config` errors with "depends
  on undefined service"), which would break the default no-profile
  `docker compose up -d`. `required: false` fixes exactly that: verified
  directly (`docker compose config`, both with and without `--profile local-bot-api`) that it makes the dependency a no-op when
  `telegram-bot-api` isn't part of the run, while still gating `app`'s
  start on `telegram-bot-api` reaching `healthy` when the profile *is*
  active (confirmed with a throwaway two-service stack: `app` didn't start
  until the dependency's healthcheck passed). This only holds `app`'s
  *first* start until the server is reachable — see
  [UFB-0034](UFB-0034-health-endpoints.md)'s continuous `GET /health` check
  for detecting it going down again afterward.

## Operator migration (one-time)

Full step-by-step runbook:
[docs/telegram-bot-api-setup.md](../telegram-bot-api-setup.md). Summary:
Telegram requires a bot to log out of the cloud API before a local server
will accept it:

```sh
curl -sS "https://api.telegram.org/bot<TOKEN>/logOut"
```

Get `TELEGRAM_API_ID`/`TELEGRAM_API_HASH` from https://my.telegram.org
(account API credentials, not the bot token), set them plus
`TELEGRAM_API_URL=http://telegram-bot-api:8081` in `.env`, and start the
stack. Reversible: call `logOut` against the **local** server's address to
move back to the cloud API.

## Testing

### Unit

- `_fits_native_send`: `True` at/under `CLOUD_SEND_VIDEO_MAX_MB`; `False`
  above `LOCAL_SEND_VIDEO_MAX_MB`; in between, `True`/`False` following
  `is_telegram_api_reachable()`'s `True`/`False`/`None`
  (`None` — `TELEGRAM_API_URL` unset — also resolves to `False`, nothing
  to send this tier through).
- A file at/under `CLOUD_SEND_VIDEO_MAX_MB` → `_reply_with_video` is
  attempted (`reply_video` awaited with `supports_streaming=True` and a
  thumbnail).
- A file over `LOCAL_SEND_VIDEO_MAX_MB` → no send attempted; the reply is
  "I cannot upload attachment this big now..." followed by the same
  Download/Source links, in one message.
- A file that can't be stat'd → falls back to the plain text reply, doesn't
  raise.
- `reply_video` raising on every attempt → falls back to the text `reply`,
  no exception escapes `handle_message`.
- On the local backend, `reply_video` raising on the first (path-based)
  attempt and succeeding on the retry (`FSInputFile`) → counted as sent;
  `reply_video` was awaited twice, first with the plain path then with an
  `FSInputFile`.
- `_build_session()` with `TELEGRAM_API_URL` set → returns an
  `AiohttpSession` whose API base is the local server, `is_local=True`;
  unset → returns `None` (default cloud session).
- `TELEGRAM_API_URL`/`CLOUD_SEND_VIDEO_MAX_MB`/`LOCAL_SEND_VIDEO_MAX_MB`
  defaults (`""` / `10` / `500`).
- `process_url_request` returns the Download/Source text plus the media
  path; `api.py`'s JSON response is unchanged.
- `is_telegram_api_reachable()` → `None` when `TELEGRAM_API_URL` is unset;
  `True` against a real listening socket; `False` against a closed one.
- `GET /health` → `telegram_api` is `null` and status stays `200` when
  unset; `503`/`"telegram_api": false` when configured but unreachable.
- `_make_bot(use_local=True/False)` → session's `api.is_local` matches.
- `_reply_with_video()` sends `media_path` as plain `str` (first attempt)
  when `_using_local_api` is `True`, and as `FSInputFile` when `False`; the
  thumbnail is `FSInputFile` in both cases and on both attempts.
- `start_polling()` picks the starting backend from a live reachability
  check, not just whether `TELEGRAM_API_URL` is set.

### Integration / Human

- With `TELEGRAM_API_URL` unset: a file at/under `CLOUD_SEND_VIDEO_MAX_MB`
  arrives as a native playable video; anything larger falls back to the
  text link (or the "cannot upload" notice above `LOCAL_SEND_VIDEO_MAX_MB`).
- With the local Bot API server configured and reachable: files up to
  `LOCAL_SEND_VIDEO_MAX_MB` arrive as native playable video too, and the
  `telegram-bot-api` logs show a path-based send (no multipart upload) —
  this is the only way to confirm path-based sending actually happened,
  since a file under 50 MB would send fine over the cloud API too.
- Every reply — native video caption, text fallback, or "cannot upload"
  notice — carries the Download/Source links.
- Verified live (2026-09-10): `sudo docker compose --profile local-bot-api up -d telegram-bot-api` reaches `healthy` in `docker inspect`; against a
  real closed TCP port, `GET /health` returns `503` with
  `"telegram_api": false` end-to-end through the real ASGI app (not
  mocked).
- With `TELEGRAM_API_URL` set and the local server running, stop it
  (`docker compose stop telegram-bot-api`): `/health` degrades to
  `503`/`"telegram_api": false`, but the bot keeps polling (aiogram's own
  retry/backoff against the same endpoint) and still replies with text for
  anything above `CLOUD_SEND_VIDEO_MAX_MB`. Restart the local server and
  confirm both `/health` returns to `200` and native sends up to
  `LOCAL_SEND_VIDEO_MAX_MB` resume — with no restart of `app` needed.

## Status

Implemented.
