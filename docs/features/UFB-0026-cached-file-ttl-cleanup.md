# UFB-0026. Cached-file TTL cleanup

**Tags:** #ops #cache

## Behavior

A cached download that has gone untouched (not read) for longer than a configured age is
automatically and continuously removed, along with its `/watch/<file>` page, its
[per-file preview image](UFB-0035-per-file-preview-images.md), and any directory left empty by
that removal, so the cache does not grow without bound. Seeded static pages (landing page, 404
page, bundled preview image, sample clip and its watch page and preview) are never removed.
Cleanup keeps running for the lifetime of the process, not just once at startup.

## Implementation

- A daemon thread inside the app process (`app/cleanup.py`) sweeps `CACHE_DIR` on a repeating
  interval (`CLEANUP_INTERVAL` seconds), deleting files whose access time (`atime`) is older than
  `FILE_TTL` days, their orphaned `/watch/` page and `/preview/` image counterparts, and any
  directory left empty.
- The thread is started/stopped alongside the app lifespan (`app/main.py`) and its liveness is
  reported by `GET /health` next to bot-polling and page-seeding status.
- On a cache hit, `yt_dlp_download` (`app/download.py`) refreshes the file's `atime` explicitly,
  so serving a cached file counts as a touch independent of the filesystem's `relatime` behavior.

## Testing

### Unit / Integration

- A file untouched longer than `FILE_TTL` → removed on the next sweep.
- A file recently read but with an old modification time → kept (access time, not mtime, is the
  criterion).
- A removed media file's `/watch/<stem>.html` and `/preview/<stem>.jpg` → removed with it; an
  orphaned watch page or preview with no matching media file → removed too.
- Seeded filenames → always kept, regardless of age.
- A directory left empty by deletion → pruned; `CACHE_DIR` itself is never removed.
- Cleanup continues to run after the first pass (not a one-shot); `start_cleanup`/`stop_cleanup`
  toggle `is_cleanup_alive()` and the thread stops cleanly on shutdown.

## Status

Implemented.
