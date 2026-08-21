# UFB-0012. YouTube mirror rewrites

**Tags:** #rewrite #youtube

## Behavior

YouTube is never downloaded via yt-dlp — any recognized YouTube video link
(standard watch pages, Shorts, `music.youtube.com`, `youtu.be`, `m.youtube.com`,
with or without `www.`) is immediately answered with a mirror-domain
alternative that renders a richer embed, alongside the original link. This
always applies, independent of the download allow-list.

## Implementation

- URL-pattern matching against the resolved URL, rewriting the host to
  `YOUTUBE_MIRROR_DOMAIN` (long-form URLs) or `YOUTUBE_SHORT_MIRROR_DOMAIN`
  (`youtu.be` short links).
- Runs before any download is attempted, taking priority over the
  [allow-list gate](UFB-0009-download-allow-list.md).

## Testing

### Unit

- `youtube.com/watch?v=ID`, `www.youtube.com/watch?v=ID`,
  `music.youtube.com/watch?v=ID`, `m.youtube.com/watch?v=ID`,
  `youtube.com/shorts/ID`, `youtu.be/ID` → each rewritten to the
  matching mirror domain.
- Runs unconditionally, regardless of `DOWNLOAD_ALLOWED_DOMAINS`.

## Status

Implemented — with known gaps:

- Only reachable when `youtube.com`/`youtu.be` happens to be on the download
  allow-list, because the rewrite lives on a code path gated behind it —
  the opposite of "always applies"
  ([BUGS #23](../BUGS.md#23-youtubes-mirror-link-alternative-is-incorrectly-gated-behind-download_allowed_domains-high-p1d2)).
- Even when reached, matching requires the literal `www.`/`music.` prefix
  and a `?v=` query, so `youtube.com/watch?v=ID` (no `www.`), `m.youtube.com`,
  and Shorts links never match
  ([BUGS #26](../BUGS.md#26-youtube-rewrite-misses-shorts-m-and-bare-domain-forms-medium-p2d2)).
- Query-string stripping upstream removes `?v=` before matching even runs
  ([BUGS #1](../BUGS.md#1-redirect-resolution-strips-query-strings-breaking-youtube-rewrites-high-p1d2)).
