# UFB-0054. Maintainer alerts

**Tags:** #ops #telegram #config

## User Story

As a bot operator, I want the bot to message an admin chat when it is unhealthy, so that failures aren't silent.

## Behavior

The bot sends proactive alerts to a configured admin chat for:

| Condition                                   | Source                                                      |
|---------------------------------------------|-------------------------------------------------------------|
| A cookie jar expired or logged out          | [UFB-0038](UFB-0038-cookie-keepalive.md)                    |
| A spike in download failures for a platform | failure counters from [UFB-0045](UFB-0045-usage-metrics.md) |
| The local Bot API server is unreachable     | [UFB-0034](UFB-0034-health-endpoints.md)                    |
| yt-dlp is out of date                       | version check                                               |
| The cache volume is nearly full             | cache size                                                  |

Alerts are de-duplicated and rate-limited, so a persistent fault sends one message and later a recovery notice, not one per request. Each kind can be switched off individually. This is distinct from [UFB-0051](UFB-0051-report-broken-link.md), a user-initiated report button.

## Implementation

- Introduces `ADMIN_CHAT_ID` to `app/config.py`, the README and `docker-compose.yml`: a comma-separated list of chat IDs, and every alert goes to each of them. It was previously set in a local `.env` and read nowhere. [UFB-0049](UFB-0049-admin-stats-command.md) reuses it.
- The failure-spike alert fires when one platform has at least `ALERT_FAILURE_SPIKE_MIN_ATTEMPTS` (default 5) attempts within `ALERT_FAILURE_SPIKE_WINDOW_MINUTES` (default 10) and more than `ALERT_FAILURE_SPIKE_RATIO` (default 0.5) of them failed.
- One setting per alert kind, on by default only if `ADMIN_CHAT_ID` is set.

## Quirks & Decisions

- Quirk: alerts need thresholds.
  Decided: a fixed default of 5 attempts in 10 minutes with over 50% failing, tunable through the three `ALERT_FAILURE_SPIKE_*` settings above.
- Quirk: with `ADMIN_CHAT_ID` empty there is nowhere to send.
  Proposed: alerts are off and nothing is logged beyond today's logging.

## Testing

### Human

- Expire a cookie jar. One alert arrives. Fix it and a recovery notice arrives. No repeat messages in between.

### Unit

- De-duplication and rate-limit state per alert kind, and the per-kind switches.

### Integration

- A simulated unreachable Bot API server produces exactly one alert.

## Status

Planned
