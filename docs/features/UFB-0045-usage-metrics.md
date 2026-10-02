# UFB-0045. Usage metrics

**Tags:** #ops #api

## User Story

As a bot operator, I want counters and timings for what the bot does, so that I can see how it is used and where it fails.

## Behavior

The bot measures, without any user-identifying data (no chat IDs or URLs in labels):

| Metric                     | Breakdown                                                                           |
|----------------------------|-------------------------------------------------------------------------------------|
| Requests handled           | per platform                                                                        |
| Download outcome           | success, failure, fallback to mirror, per platform                                  |
| Which downloader succeeded | yt-dlp, or the cobalt fallback ([UFB-0052](UFB-0052-cobalt-fallback-downloader.md)) |
| Latency                    | download and reply                                                                  |
| Cache                      | size and hit rate                                                                   |
| Reply kind                 | native video versus text link                                                       |

## Implementation

- In-memory counters and histograms served as a Prometheus `/metrics` endpoint next to `/health` ([UFB-0034](UFB-0034-health-endpoints.md)), using the `prometheus-client` library. Counters reset on restart, which Prometheus handles; there is no persistence layer.
- It is the data source for [UFB-0049](UFB-0049-admin-stats-command.md) and [UFB-0054](UFB-0054-maintainer-alerts.md), and for failure reasons in [UFB-0051](UFB-0051-report-broken-link.md).

## Quirks & Decisions

- Quirk: nothing is measured today.
  Decided: Prometheus `/metrics` with in-memory counters. `/stats` ([UFB-0049](UFB-0049-admin-stats-command.md)) reads the same counters, so its numbers also start from zero after a restart.
- Quirk: platform labels could leak data if derived from raw URLs.
  Proposed: a fixed set of platform names, and `other` for the rest.

## Testing

### Human

- Send a few links, then open `/metrics`. Counts and latencies moved accordingly.

### Unit

- A counter increments once per outcome and labels never contain a URL or chat ID.

### Integration

- A failed download followed by a mirror fallback shows up as one failure and one fallback.

## Status

Planned
