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

## Implementation

- The watch page (`app/templates/watch.html`, rendered per
  [UFB-0033](UFB-0033-static-page-generation.md)) carries `og:video`,
  `og:video:secure_url`, `og:image`, and `twitter:player` tags pointing at
  the file's existing root-level URL (see
  [UFB-0025](UFB-0025-themed-download-file-server.md)), plus an inline
  `<video>` element and a download link for browsers.
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

### Integration / Human

- `GET /watch/<known file>.html` → the rendered page with the meta tags
  present.
- `GET /watch/<unknown file>.html` → the generated 404.
- Sending a real URL to the bot renders an inline-playable card in Telegram;
  with `IV_RHASH` set, the link opens in Instant View.
- `GET /watch/sample.html` → 200, same tag shape as a real watch page, video
  points at `/sample.mp4` (also reachable, `video/mp4`).

## Status

Implemented — with a known gap:

- `og:video:type` is stated as `video/mp4`, but cached files are always
  named `.mp4` regardless of their actual container
  ([BUGS #15](../BUGS.md#15-downloaded-files-are-always-saved-with-a-mp4-extension-low-p3d2)).
  A cached webm/mkv wearing an `.mp4` name will not play in the Telegram
  card.
