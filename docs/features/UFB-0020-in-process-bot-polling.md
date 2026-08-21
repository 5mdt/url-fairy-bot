# UFB-0020. In-process bot polling

**Tags:** #runtime

## Behavior

The Telegram bot and the REST API run as a single process: on startup, the
bot begins polling Telegram for updates in the background while the HTTP
server also serves API requests. If polling stops unexpectedly (network
issue, transient Telegram error), that failure is observable — logged and
reflected in the process's health status — rather than silently leaving the
bot unresponsive while the API keeps reporting healthy. On shutdown, polling
stops cleanly.

## Implementation

- Bot polling starts as a background task alongside the HTTP server's
  startup.
- The task's completion/failure is observed (not fire-and-forget); shutdown
  cancels it explicitly and closes its storage.

## Testing

### Integration

- Process starts → both bot polling and the HTTP API are live.
- Polling raises → the failure is logged and surfaced (not silently
  swallowed).
- Process shuts down → polling task is cancelled, storage closed.

## Status

Implemented — with known gaps:

- The polling task's return value is discarded with no completion callback,
  and shutdown never cancels it or calls `stop_polling()` — a polling
  failure is silent and undetectable from outside the process
  ([BUGS #7](../BUGS.md#7-bot-polling-failures-are-silent-medium-p2d2)).
- No `/health` endpoint or container healthcheck exists to expose this at
  all (see `TODO.md`, Docker / Deploy).
- `/start` isn't registered on this startup path either
  ([BUGS #4](../BUGS.md#4-start-command-handler-is-unreachable-medium-p2d1)).
