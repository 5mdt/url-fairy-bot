# UFB-0023. Rewrite domain allow-list

**Tags:** #config #rewrite #allowlist

## Behavior

`REWRITE_ALLOWED_DOMAINS` restricts which domains get a mirror-domain
rewrite — nothing else. An empty value (the default) means no restriction:
every platform's rewrite applies. A non-empty, comma-separated list
restricts rewriting to only those domains, using the same matching rules as
[`DOWNLOAD_ALLOWED_DOMAINS`](UFB-0009-download-allow-list.md) (exact or
subdomain match, trimmed, lower-cased, `www.`-agnostic). This governs every
[platform](UFB-0011-platform-mirror-rewrites.md) and
[YouTube](UFB-0012-youtube-mirror-rewrites.md) rewrite rule alike, and is
entirely independent of `DOWNLOAD_ALLOWED_DOMAINS` — an operator can
restrict rewriting without affecting downloads, or vice versa.

## Implementation

- `REWRITE_ALLOWED_DOMAINS`: comma-separated domain list; empty means
  unrestricted. Same normalization/matching as `DOWNLOAD_ALLOWED_DOMAINS`.
- Checked once, at the top of `apply_rewrite_map`, before any pattern is
  tried.

## Testing

### Unit

- Empty list → every platform rewritten (default).
- Non-empty list excluding a platform's domain → that platform's URLs pass
  through unchanged; other listed platforms unaffected.
- Same domain-matching edge cases as `DOWNLOAD_ALLOWED_DOMAINS` (subdomain
  match, lookalike domain, whitespace/trailing comma).

## Status

Implemented — replaces the five per-platform `*_REWRITE_ENABLED` booleans
(`INSTAGRAM_REWRITE_ENABLED`, `REDDIT_REWRITE_ENABLED`,
`SPOTIFY_REWRITE_ENABLED`, `TIKTOK_REWRITE_ENABLED`,
`TWITTER_REWRITE_ENABLED`), which are removed entirely, with a single
domain-list setting consistent with `DOWNLOAD_ALLOWED_DOMAINS`. This also
closes the gap where YouTube had no equivalent toggle (`TODO.md` TODO-0003)
— YouTube is now governed by the same setting as every other platform
(2026-08-22).
