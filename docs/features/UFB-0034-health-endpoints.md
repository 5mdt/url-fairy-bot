# UFB-0034. Health endpoints

**Tags:** #api #ops #runtime

## User Story

As an operator, I want the app to expose HTTP health endpoints, so that a
container orchestrator can tell whether the process is up and whether the
bot is actually working.

## Behavior

- `GET /healthz` is a pure liveness probe: always `200 {"status": "ok"}` as
  long as the HTTP server is answering requests.
- `GET /health` is a readiness probe that reflects whether the bot's
  Telegram polling loop is alive and whether the static pages (landing,
  404, sample watch page) have been seeded into the cache directory. It
  returns `200 {"status": "ok", "polling": true, "pages_seeded": true}`
  when both are true, otherwise `503 {"status": "degraded", ...}` with the
  failing flag(s) set to `false`.

## Implementation

- `app/bot.py` now owns the polling task as a module-level
  `polling_task: asyncio.Task | None`, created by `start_polling()` and
  cancelled/awaited by `stop_polling()`. A `add_done_callback` logs an
  unexpected failure at `ERROR` (with traceback) or a clean cancellation at
  `INFO`, so a dead polling loop is no longer silent.
  `is_polling_alive()` reports `polling_task is not None and not
  polling_task.done()`.
- `app/pages.py` sets a module-level `pages_seeded = True` at the end of
  `seed_static_pages()`.
- `app/api.py` adds `GET /healthz` and `GET /health` on the existing
  `api_router`, reading `is_polling_alive()` and `pages.pages_seeded` live.
- `app/main.py`'s `lifespan()` calls `bot.start_polling()` /
  `await bot.stop_polling()` instead of managing the task inline.
- `Dockerfile` declares a `HEALTHCHECK` that runs
  `wget -q -O /dev/null http://127.0.0.1:8000/health` instead of
  `docker-compose.yml` testing for the seeded sample file directly —
  `pages_seeded` in `/health` reflects the same signal, so `nginx`'s
  `depends_on: condition: service_healthy` gate is preserved, and the
  check now travels with the image rather than living only in this
  compose file.

## Quirks & Decisions

- `/healthz` deliberately checks nothing beyond "the ASGI app is
  responding" — it exists for a plain liveness probe that should never
  flap because of a transient bot-side issue. `/health` is the one that
  encodes readiness.
- `curl` is not present in the runtime image (removed with the build
  dependencies), so the `Dockerfile`'s `HEALTHCHECK` uses busybox `wget`,
  which ships with the `python:3.11-alpine` base image.
- Closes [BUGS #7](../BUGS.md) (silent polling death) and
  [TODO-0020](../TODO.md), and resolves the known gaps listed in
  [UFB-0020](UFB-0020-in-process-bot-polling.md).

## Testing

### Human

- Start the app locally (`make run`), `curl localhost:8000/healthz` and
  `curl localhost:8000/health` — both return 200 once startup finishes.
- Point `BOT_TOKEN` at an invalid token (or otherwise break polling) and
  confirm `/health` returns 503 with `"polling": false` while `/healthz`
  still returns 200.

### Unit

- `tests/health_test.py` — `/healthz` always 200; `/health` 200 when both
  flags true; 503 when the polling task is `None`, done, or pages aren't
  seeded yet.

### Integration

- `sudo docker compose -f docker-compose.yml -f compose.dev.yml up --build`
  — `app` reaches `healthy` via the new HTTP check and `nginx` starts.

## Status

Implemented
