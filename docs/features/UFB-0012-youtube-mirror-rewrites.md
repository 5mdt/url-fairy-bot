# UFB-0012. YouTube mirror rewrites

**Tags:** #rewrite #youtube

## Behavior

Any recognized YouTube video link (standard watch pages, Shorts,
`music.youtube.com`, `youtu.be`, `m.youtube.com`, with or without `www.`) can
be rewritten to a mirror-domain alternative that renders a richer embed,
alongside the original link. YouTube is just another entry in the shared
[platform rewrite map](UFB-0011-platform-mirror-rewrites.md): it is no
longer specially exempted from real downloads, and the mirror is only
offered when a download isn't attempted or fails — see
[UFB-0009](UFB-0009-download-allow-list.md) (download gate) and
[UFB-0010](UFB-0010-mirror-link-disallowed-domains.md) /
[UFB-0013](UFB-0013-download-failure-fallback.md) (when the mirror is
offered). With the default (empty) `DOWNLOAD_ALLOWED_DOMAINS`, a YouTube URL
is downloaded via yt-dlp like any other supported domain rather than
mirrored, unless the operator restricts `DOWNLOAD_ALLOWED_DOMAINS` to
exclude it. Whether the mirror itself is offered is governed by
[`REWRITE_ALLOWED_DOMAINS`](UFB-0023-rewrite-domain-allowlist.md), same as
every other platform.

## Implementation

- URL-pattern matching in the shared `rewrite_map` (`apply_rewrite_map`,
  `app/url_processing.py`), rewriting the host to `YOUTUBE_MIRROR_DOMAIN`
  (long-form URLs) or `YOUTUBE_SHORT_MIRROR_DOMAIN` (`youtu.be` short
  links).
- No longer has its own early-return special case — it runs through the
  same allow-list-gated fallback path as every other platform.

## Testing

### Unit

- `youtube.com/watch?v=ID`, `www.youtube.com/watch?v=ID`,
  `music.youtube.com/watch?v=ID`, `m.youtube.com/watch?v=ID`,
  `youtube.com/shorts/ID`, `youtu.be/ID` → each rewritten to the
  matching mirror domain when a download isn't attempted/fails and
  `REWRITE_ALLOWED_DOMAINS` permits it.
- `REWRITE_ALLOWED_DOMAINS` excluding YouTube's domains → no rewrite offered
  (download proceeds normally if `DOWNLOAD_ALLOWED_DOMAINS` permits it).

## Status

Implemented

Changed:

- YouTube is no longer hard-blocked from real downloads or special-cased
  ahead of the allow-list gate. It is now folded into the shared
  `rewrite_map` and governed by `REWRITE_ALLOWED_DOMAINS`/
  `DOWNLOAD_ALLOWED_DOMAINS` like every other platform (2026-08-22).

Fixed:

- Matching now accepts an optional `www.`/`m.` host prefix, bare
  `youtube.com`, and a `/shorts/<id>` path form, in addition to the existing
  `www.`/`music.` + `?v=` forms
  ([BUGS #26](../BUGS.md#26-youtube-rewrite-misses-shorts-m-and-bare-domain-forms-medium-p2d2),
  fixed 2026-08-21).
- Query-string stripping upstream no longer removes `?v=` before matching
  runs ([BUGS #1](../BUGS.md#1-redirect-resolution-strips-query-strings-breaking-youtube-rewrites-high-p1d2),
  fixed 2026-08-21).
