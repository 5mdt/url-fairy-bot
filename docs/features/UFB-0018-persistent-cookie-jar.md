# UFB-0018. Persistent cookie jar

**Tags:** #download #cookies #config

## Behavior

An operator can opt into a persistent cookie jar so that session cookies yt-dlp updates during a download (e.g. refreshed tokens) are kept across requests, instead of re-merging the source cookie files from scratch every time. When disabled (the default), a freshly merged temporary cookie file is used per download and discarded afterward.

## Implementation

- `COOKIE_JAR_ENABLED` (default `false`): when enabled, initializes `cookie_jar.txt` once by merging all `cookies*.txt` files, then reuses and lets yt-dlp update that same file on every subsequent download.

## Testing

### Unit

- Jar disabled → a fresh merged temp file is used and deleted after each download.
- Jar enabled, first run → jar file initialized from source cookie files.
- Jar enabled, subsequent runs → existing jar file reused as-is.

## Status

Implemented. The jar is kept fresh by [UFB-0038](UFB-0038-cookie-keepalive.md), which periodically checks the sessions and re-merges the jar when `cookies*.txt` files change.
