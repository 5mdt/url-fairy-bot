# UFB-0023. Per-platform rewrite toggles

**Tags:** #config #rewrite

## Behavior

An operator can disable mirror-domain rewriting for an individual platform
without affecting the others. A disabled platform's URLs pass through
unmodified everywhere a rewrite would otherwise apply (disallowed-domain
replies, download-failure fallback).

## Implementation

- `INSTAGRAM_REWRITE_ENABLED`, `REDDIT_REWRITE_ENABLED`,
  `SPOTIFY_REWRITE_ENABLED`, `TIKTOK_REWRITE_ENABLED`,
  `TWITTER_REWRITE_ENABLED` — each defaults to `true`.

## Testing

### Unit

- Each toggle set to `false` → that platform's URLs are never rewritten;
  other platforms unaffected.

## Status

Implemented — with a known gap:

- YouTube has no equivalent toggle, unlike the other five platforms (see
  `TODO.md` addition below).

Fixed:

- These settings used to be parsed but never consulted by the rewrite
  logic — setting any of them to `false` had no effect; each is now checked
  before its corresponding `apply_rewrite_map` pattern is applied
  ([BUGS #2](../BUGS.md#2-_rewrite_enabled-settings-are-defined-documented-and-never-read-high-p1d2),
  fixed 2026-08-21).
