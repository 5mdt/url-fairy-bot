# UFB-0008. Query-string stripping

**Tags:** #url #privacy

## Behavior

Tracking-style query parameters (e.g. affiliate/campaign IDs) are removed
from a resolved URL before it's shown back to the user or matched against
mirror-rewrite patterns. Query parameters that identify the actual content
(e.g. a video ID) are preserved, so content-identifying links keep working.

## Implementation

- Applied to the redirect-resolved URL as part of [redirect
  resolution](UFB-0007-redirect-resolution.md).

## Testing

### Unit

- A URL with only tracking parameters → parameters stripped.
- A URL whose query string identifies the content (e.g. `?v=<id>`) →
  content-identifying parameter preserved.

## Status

Implemented — with known gaps:

- The entire query string is unconditionally dropped, not just
  tracking parameters — this breaks any content-identifying query parameter,
  most notably YouTube's `?v=` id, before it reaches the
  [YouTube rewrite](UFB-0012-youtube-mirror-rewrites.md)
  ([BUGS #1](../BUGS.md#1-redirect-resolution-strips-query-strings-breaking-youtube-rewrites-high-p1d2)).
