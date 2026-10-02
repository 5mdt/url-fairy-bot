# UFB-0016. Download caching

**Tags:** #download #cache

## User Story

As a Telegram user, I want repeat links served from a local cache, so that replies are fast and sources aren't hit again.

## Behavior

A URL that has already been downloaded is served from a local cache instead of being downloaded again, identified by the source URL. Cache filenames stay within filesystem name-length limits regardless of how long the source URL is, and the cache directory always exists before it's needed. Concurrent requests for the same not-yet-cached URL download it once.

## Implementation

- The URL is deterministically mapped to a cache filename and checked for existence before invoking yt-dlp.
- The stem is the URL with non-alphanumeric characters replaced by `_`. When that exceeds 200 UTF-8 bytes it is truncated and ends in `_` plus the first 16 hex digits of the URL's sha256, so distinct long URLs never collide and the stem plus any extension or temp suffix (`.mp4`, `.f137.mp4.part`, `.jpg.tmp`) stays under 255 bytes. Short URLs keep the plain stem, so existing caches stay valid.
- A per-stem `asyncio.Lock` wraps the cache check and the download in `yt_dlp_download` and `tiktok_gallery_download`; the second concurrent request waits, then sees the cached file. The lock is dropped from the registry once nobody holds or awaits it.
- Cached files live under `CACHE_DIR` and are served over HTTP (see [UFB-0025](UFB-0025-themed-download-file-server.md)).

## Quirks & Decisions

Known gaps: none (BUG-0014 fixed).

## Testing

### Unit

- Same URL requested twice → second request skips download, returns the cached path.
- A very long source URL → cache filename stays within filesystem limits.
- Two long URLs differing only at the end → different stems.
- Short URL → stem unchanged (plain transliteration).
- Two concurrent requests for the same uncached URL → one download.

## Status

Implemented
