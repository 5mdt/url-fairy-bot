# UFB-0032. Telegram Instant View embeds

**Tags:** #telegram #ux #hosting

**Priority:** P1 (high)

## Behavior

A link the bot sends for a downloaded video opens as a Telegram Instant View
page instead of a plain file link, with the video embedded and playable
without leaving Telegram. Telegram support ships first; other IV-capable
clients may follow later.

## Implementation

Open question, to resolve before implementation:

- Full Telegram Instant View (instantview.telegram.org) requires an approved
  IV template bound to `BASE_URL`'s domain and markup the template can parse.
- A lighter alternative — `og:video`/`twitter:player` meta tags on the
  per-file page served by nginx — gets Telegram's native link-preview video
  player without an approved IV template, at the cost of not being "Instant
  View" in Telegram's specific sense.

Whichever route is chosen, it hangs off the per-file pages nginx serves (see
[UFB-0025](UFB-0025-themed-download-file-server.md),
[UFB-0031](UFB-0031-landing-page-and-cache-index.md)).

## Status

Planned.
