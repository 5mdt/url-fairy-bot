# UFB-0035. Per-file preview images

**Tags:** #hosting #telegram #media

## User Story

As a Telegram user who receives a watch link from the bot, I want the link
preview card to show a frame from the actual clip, so that I can tell what
was shared before opening it.

## Behavior

A `/watch/<file>` page's `og:image` is a JPEG frame extracted from that
file's own video, instead of the same bundled artwork every page used to
share. If a frame could not be extracted (missing `ffmpeg`, a corrupt file,
or a timeout), the page falls back to the bundled `app/assets/preview.png`
unchanged — a link never breaks or 404s over this.

## Implementation

- `app/preview.py` mirrors `app/pages.py`'s `watch_page_path`/`watch_page_url`
  shape: `preview_path(media_filename)` → `<CACHE_DIR>/preview/<stem>.jpg`,
  `preview_url(media_filename)` → `https://BASE_URL/preview/<stem>.jpg`.
  Kept in its own top-level directory (not beside the media file) so
  [UFB-0026](UFB-0026-cached-file-ttl-cleanup.md)'s stem-matching sweep never
  confuses a preview image for the media it previews.
- `generate_preview(media_os_path)` shells out to `ffmpeg` to grab one frame,
  writing it atomically. Any failure (binary missing, non-zero exit, timeout)
  is caught, logged, and returns `None` — download and reply flow are
  unaffected either way.
- `attempt_download` ([UFB-0015](UFB-0015-yt-dlp-media-download.md)) calls
  `generate_preview` right after a download resolves, before
  `write_watch_page`, covering both a fresh download and a cache hit.
- `render_watch_page` ([UFB-0033](UFB-0033-static-page-generation.md)) uses
  the per-file preview's URL as `og:image` when the file exists on disk,
  else the bundled `preview.png`. `og:video:type` is derived from the
  media's real extension instead of being hardcoded, fixing the mismatch
  half of [BUG-0015](../BUGS.md).
- `seed_static_pages` best-effort generates a preview for the bundled
  `sample.mp4` too, so `/watch/sample.html` (the Instant View sample) has
  the same tag shape as a real watch page.
- `app/cleanup.py` sweeps a preview alongside its media file exactly like it
  already does for a watch page, and protects the sample's preview
  permanently.
- `ffmpeg` is now a runtime OS dependency (`Dockerfile`).

## Quirks & Decisions

- Quirk: extracting at a fixed timestamp can land on a black frame or a
  fade-in for some clips.
  Open: is a smarter frame-picking heuristic worth the complexity, or is
  "good enough most of the time" acceptable? Logged as
  [BUG-0062](../BUGS.md).
- Quirk: `generate_preview` runs synchronously inside `attempt_download`,
  adding to the reply latency of every successful download.
  Open: move it off the request path (background task, lazy-on-first-view)
  if the added latency turns out to matter in practice. Logged as
  [BUG-0063](../BUGS.md).

## Testing

### Unit

- `preview_path`/`preview_url` map a media filename to the right path/URL,
  including percent-encoding.
- `generate_preview` invokes `ffmpeg` with the expected arguments and
  destination; a non-zero exit, a missing binary, and a timeout all return
  `None` without raising.
- `render_watch_page`: preview file present → `og:image` is the per-file
  URL; absent → falls back to `/preview.png`; `og:video:type` matches the
  media's real extension.
- A preview whose media goes stale is swept with it; an orphaned preview
  with no media is swept; the sample's preview is protected.

### Integration / Human

- `GET /watch/<known file>.html` → `og:image` points at
  `/preview/<stem>.jpg`, which itself returns `200 image/jpeg`.
- Sending a real URL to the bot shows the clip's own frame in Telegram's
  link preview card.
- `GET /watch/sample.html` → still 200, same tag shape.

## Status

Implemented.
