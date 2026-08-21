# UFB-0017. Cookie file merging

**Tags:** #download #cookies

## Behavior

For platforms requiring a logged-in session, the operator can drop one or
more Netscape-format cookie files into a configured directory. Every
`cookies*.txt` file found there is merged into a single cookie file and
passed to yt-dlp, so authenticated downloads work without picking one file
manually. Comment lines in the source files are excluded from the merged
output; lines that merely start with `#` as part of cookie data (e.g. the
Netscape `HttpOnly_` prefix) are preserved.

## Implementation

- `COOKIES_DIR`: directory scanned for `cookies*.txt` files (glob).
- Merged into one file per download, prefixed with the standard Netscape
  cookie-file header.

## Testing

### Unit

- Multiple cookie files present → all merged into one.
- A comment line vs. an `HttpOnly_`-prefixed data line → comment dropped,
  data line kept.
- No cookie files present → download proceeds without a cookie file.

## Status

Implemented — with known gaps:

- The comment-line filter's exact intent (why a line starting with a
  single `#` and no following space is kept) isn't documented in code and
  has no dedicated test (see `TODO.md`, Cookie handling).
