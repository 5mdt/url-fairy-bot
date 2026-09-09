# UFB-0032. Telegram Instant View embeds

**Tags:** #telegram #ux #hosting

**Priority:** P1 (high)

## Behavior

A link the bot sends for a downloaded video opens with the video playable
without leaving Telegram, instead of a plain file link.

By default this is Telegram's native link-preview video player, driven by
`og:video`/`twitter:player` tags on a themed per-file page — no Telegram
approval needed. An operator who creates an Instant View template for their
`BASE_URL` domain (at instantview.telegram.org) and sets `IV_RHASH` to its
`rhash` upgrades the same links to true Instant View, which Telegram opens
even before the template is publicly approved.

A file larger than `INLINE_VIDEO_MAX_MB` gets a plain watch page instead —
no `og:video`/`twitter:player` tags, no inline `<video>` element, just the
per-file image and a download link — since Telegram silently drops the
inline player for large files anyway ([BUGS #61](../BUGS.md)) and a
non-functional `og:video` tag is worse than none.

## Implementation

- The watch page (`app/templates/watch.html`, rendered per
  [UFB-0033](UFB-0033-static-page-generation.md)) carries `og:video`,
  `og:video:secure_url`, `og:image`, and `twitter:player` tags pointing at
  the file's existing root-level URL (see
  [UFB-0025](UFB-0025-themed-download-file-server.md)), plus an inline
  `<video>` element and a download link for browsers. The `<video>` element
  is not wrapped in a `<p>` — Telegram's Instant View content model rejects
  `<video>` nested inside `<p>` ("Element `<video>` is not supported in
  `<p>`"). `og:video:type` matches the file's real extension; `og:image` is
  a per-file preview frame when one exists
  ([UFB-0035](UFB-0035-per-file-preview-images.md)), otherwise the bundled
  `preview.png`.
- `render_watch_page` (`app/pages.py`) stats the media file on disk; when
  its size exceeds `INLINE_VIDEO_MAX_MB` (default `10`), the template omits
  every `og:video`/`twitter:player` tag and the inline `<video>` element —
  only `og:image` and a download link render. A file that can't be stat'd
  (already swept, permission error) is treated as small, so a missing file
  never blocks the page from rendering.
- The bot's download reply links to `https://BASE_URL/watch/<stem>.html`
  instead of the raw file. The raw file stays reachable at its existing
  `.../<stem>.mp4` path unchanged.
- If `IV_RHASH` is set, the link is wrapped as
  `https://t.me/iv?url=<page_url>&rhash=<IV_RHASH>` instead. See
  [docs/telegram-instant-view-setup.md](../telegram-instant-view-setup.md)
  for how to obtain a `rhash`.
- The stable `https://BASE_URL/watch/sample.html` page (seeded per
  [UFB-0033](UFB-0033-static-page-generation.md)) is the sample URL to use
  when registering an Instant View template, so the template's preview can
  never drift from a real watch page.

## Testing

### Unit

- Successful download, `IV_RHASH` unset → reply links to
  `https://BASE_URL/watch/<stem>.html`.
- Successful download, `IV_RHASH` set → reply links to
  `https://t.me/iv?url=<percent-encoded page url>&rhash=<IV_RHASH>`.
- A filename needing percent-encoding stays correctly encoded in both forms.
- A media file at or under `INLINE_VIDEO_MAX_MB` → page keeps `og:video`/
  `twitter:player` tags and the `<video>` element.
- A media file over `INLINE_VIDEO_MAX_MB` → page has no `og:video`/
  `twitter:player` tags and no `<video>` element, but keeps `og:image` and
  the download link.
- A missing media file → treated as small (tags kept), doesn't raise.

### Integration / Human

- `GET /watch/<known file>.html` → the rendered page with the meta tags
  present.
- `GET /watch/<unknown file>.html` → the generated 404.
- Sending a real URL to the bot renders an inline-playable card in Telegram;
  with `IV_RHASH` set, the link opens in Instant View.
- `GET /watch/sample.html` → 200, same tag shape as a real watch page, video
  points at `/sample.mp4` (also reachable, `video/mp4`).

## Status

Implemented.
