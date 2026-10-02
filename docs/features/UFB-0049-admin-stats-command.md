# UFB-0049. `/stats` admin command

**Tags:** #telegram #commands #ops

## User Story

As a bot operator, I want a `/stats` command in chat, so that I can see the bot's numbers without opening a dashboard.

## Behavior

`/stats` replies with the bot's own numbers: requests handled, download success, failure and mirror-fallback rates, a per-platform breakdown and cache size. The numbers come from the counters in [UFB-0045](UFB-0045-usage-metrics.md), so that feature comes first.

It only answers configured admin chat IDs, and the output never contains chat IDs or URLs. Anyone else gets no reply.

## Implementation

- The admin check reuses `ADMIN_CHAT_ID`, a comma-separated list of chat IDs, which [UFB-0054](UFB-0054-maintainer-alerts.md) introduces to the config, README and compose file. Any listed chat may run `/stats`.

## Quirks & Decisions

- Quirk: an unauthorized `/stats` could either be ignored or answered with a refusal.
  Proposed: ignore it, so the command isn't discoverable.
- Quirk: more than one admin may be wanted.
  Decided: a comma-separated list in `ADMIN_CHAT_ID`.

## Testing

### Human

- Send `/stats` from the admin chat. Numbers appear. Send it from another chat. Nothing happens.

### Unit

- The admin check, and the formatter, which contains no chat IDs or URLs.

### Integration

- After a few processed links the reported counts match `/metrics`.

## Status

Planned
