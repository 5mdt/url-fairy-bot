# UFB-0011. Platform mirror-domain rewrites

**Tags:** #rewrite

## Behavior

Links to Spotify, Instagram, Reddit, TikTok, Twitter/X, and YouTube are
rewritten to an equivalent link on a configured "mirror" domain that renders
richer link previews/embeds than the original site. Rewriting a domain is
only skipped when it's excluded by the
[rewrite allow-list](UFB-0023-rewrite-domain-allowlist.md)
(`REWRITE_ALLOWED_DOMAINS`, empty by default — no exclusions). Every URL
path on a matched domain is eligible for rewriting, not just specific
sub-paths (YouTube's patterns are the exception — see
[UFB-0012](UFB-0012-youtube-mirror-rewrites.md)).

## Implementation

- Domain-matching patterns per platform, each pointing at a configurable
  mirror domain (see [UFB-0022](UFB-0022-configurable-mirror-domains.md)).
- Matching requires an exact literal domain (no wildcard characters).
- All patterns live in a single `rewrite_map` in `apply_rewrite_map`
  (`app/url_processing.py`), gated once by
  [`is_rewrite_allowed`](UFB-0023-rewrite-domain-allowlist.md).

## Testing

### Unit

- One representative URL per platform → rewritten to the platform's
  configured mirror domain.
- A domain that merely contains a platform's name as a substring (e.g.
  `spotifyXcom.example`) → not rewritten.
- A platform's domain excluded via `REWRITE_ALLOWED_DOMAINS` → URL passed
  through unchanged.

## Status

Implemented — with a known gap:

- Instagram is matched only under `/p/` and `/reel/`, unlike every other
  platform's whole-domain match — a profile or story link gets no rewrite
  (see `TODO.md`, Business logic).

Fixed:

- The `INSTAGRAM_REWRITE_ENABLED` / `REDDIT_REWRITE_ENABLED` /
  `SPOTIFY_REWRITE_ENABLED` / `TIKTOK_REWRITE_ENABLED` /
  `TWITTER_REWRITE_ENABLED` toggles used to be read but never consulted;
  each `rewrite_map` entry was gated on its corresponding setting
  ([BUGS #2](../BUGS.md#2-_rewrite_enabled-settings-are-defined-documented-and-never-read-high-p1d2),
  fixed 2026-08-21), then replaced entirely by the single
  [`REWRITE_ALLOWED_DOMAINS`](UFB-0023-rewrite-domain-allowlist.md)
  allow-list, which also brings YouTube under the same control (2026-08-22).
- The Spotify pattern had an unescaped `.` in `spotify.com`, so it also
  matched any single-character substitute for that dot (e.g.
  `spotifyXcom.evil.tld`); the dot is now escaped
  ([BUGS #22](../BUGS.md#22-unescaped--in-the-spotify-rewrite-pattern-low-p2d1),
  fixed 2026-08-21).
