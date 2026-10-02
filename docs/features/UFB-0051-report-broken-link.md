# UFB-0051. Report-broken-link button

**Tags:** #telegram #ux #ops

## User Story

As a Telegram user, I want a button on a bad reply that reports it, so that the maintainer finds out which links the bot gets wrong.

## Behavior

Replies, especially the mirror-link and failure fallbacks ([UFB-0013](UFB-0013-download-failure-fallback.md)), get an inline button. Pressing it logs the URL, the failure reason and the platform for the maintainer, and acknowledges the user.

Reports are rate-limited per user so the button can't be spammed.

## Implementation

- An inline keyboard on the reply and a callback handler.
- Reports go where they can be reviewed: the log, or the metadata store from [UFB-0041](UFB-0041-link-metadata-store.md).
- Failure reasons come from [UFB-0045](UFB-0045-usage-metrics.md). This is distinct from [UFB-0054](UFB-0054-maintainer-alerts.md), which alerts on the bot's own health without any user action.

## Quirks & Decisions

- Quirk: the button adds clutter to every reply.
  Open: show it on fallbacks only, or on all replies.
- Quirk: a report contains a URL.
  Open: how long reports are kept and who can read them.

## Testing

### Human

- Press the button on a fallback reply. The user gets an acknowledgement and the report shows up in the log. Press again quickly and the rate limit answers.

### Unit

- The per-user rate limiter, and the callback data parsing.

### Integration

- A report from a callback is stored with URL, reason and platform.

## Status

Planned
