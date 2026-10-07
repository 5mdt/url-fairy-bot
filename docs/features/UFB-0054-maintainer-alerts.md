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

- `ADMIN_CHAT_ID` (`app/config.py`, the README, `docker-compose.yml`) is a comma-separated list of chat IDs, and every alert goes to each of them. [UFB-0049](UFB-0049-admin-stats-command.md) reuses it.
- `app/alerts.py` holds the logic with an injectable send function. A checker thread started in the `app/main.py` lifespan runs every `ALERT_CHECK_INTERVAL` seconds (default 60) and sends through the bot's event loop.
- Per-condition checks:

| Kind (setting)                          | Faulty when                                                                                     |
|-----------------------------------------|-------------------------------------------------------------------------------------------------|
| `cookies` (`ALERT_COOKIES`)             | the last keepalive result is logged out (`False`); unknown (`None`) changes nothing             |
| `failure_spike` (`ALERT_FAILURE_SPIKE`) | one platform, per the windowed rule below                                                       |
| `bot_api` (`ALERT_BOT_API`)             | `bot.is_telegram_api_reachable()` is `False` (`None` = not configured, never faulty)            |
| `ytdlp` (`ALERT_YTDLP`)                 | the installed yt-dlp release is older than `ALERT_YTDLP_MAX_AGE_DAYS` (default 60) days         |
| `cache` (`ALERT_CACHE`)                 | the volume holding `CACHE_DIR` is at least `ALERT_CACHE_FULL_PERCENT` (default 90) percent used |

- The failure-spike alert fires when one platform has at least `ALERT_FAILURE_SPIKE_MIN_ATTEMPTS` (default 5) attempts within `ALERT_FAILURE_SPIKE_WINDOW_MINUTES` (default 10) and more than `ALERT_FAILURE_SPIKE_RATIO` (default 0.5) of them failed.
- The failure counters are cumulative, so the checker keeps a snapshot per tick and compares the newest with the oldest one inside the window. Attempts are `success` + `failure` outcomes; failures are `failure` outcomes (`fallback_mirror` is not added, it already follows a `failure`).
- One setting per alert kind (table above), a boolean; unset means on when `ADMIN_CHAT_ID` is set and off otherwise. An explicit `true` still sends nothing without an admin chat.
- De-duplication state is kept per kind (and per platform for `failure_spike`): the first faulty check sends one alert, further faulty checks send nothing, the first healthy check after an alert sends one recovery notice. After a recovery, a new alert for the same key waits until `ALERT_MIN_INTERVAL` seconds (default 3600) have passed since the previous alert, so a flapping fault cannot spam; the fault is re-evaluated each tick and the alert goes out once the interval elapses.
- A send that fails is logged and counts as not sent, so it is retried on the next tick.

## Quirks & Decisions

- Quirk: alerts need thresholds. Decided: a fixed default of 5 attempts in 10 minutes with over 50% failing, tunable through the three `ALERT_FAILURE_SPIKE_*` settings above.
- Quirk: with `ADMIN_CHAT_ID` empty there is nowhere to send. Decided: alerts are off and nothing is logged beyond today's logging; the checker thread is not even started.
- Quirk: "yt-dlp out of date" needs a version check that does not depend on the network. Decided: compare the release date encoded in the installed version (`YYYY.MM.DD`) with today; older than `ALERT_YTDLP_MAX_AGE_DAYS` is out of date. No PyPI request is made.
- Quirk: "cache nearly full" could mean the cache's own size or the volume. Decided: the volume's used percentage (`shutil.disk_usage` of `CACHE_DIR`), since the volume filling is what breaks downloads.

## Testing

### Human

- Expire a cookie jar. One alert arrives. Fix it and a recovery notice arrives. No repeat messages in between.

### Unit

- De-duplication and rate-limit state per alert kind, and the per-kind switches.
- The windowed failure-spike rule, the yt-dlp age rule and the cache-percent rule.
- Every alert goes to each admin chat; a failed send is retried; empty `ADMIN_CHAT_ID` sends nothing.

### Integration

- A simulated unreachable Bot API server produces exactly one alert across repeated ticks, then one recovery notice.

## Status

Implemented
