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

Implemented — the polling task is now owned by `app/bot.py`
(`start_polling()` / `stop_polling()` / `is_polling_alive()`), observed via
a completion callback that logs unexpected failures, and cancelled
cleanly on shutdown. See [UFB-0034](UFB-0034-health-endpoints.md) for the
`/health` endpoint that exposes this state externally.
