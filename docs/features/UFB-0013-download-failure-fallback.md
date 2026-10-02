# UFB-0013. Download-failure fallback

**Tags:** #rewrite #download #fallback

## User Story

As a Telegram user, I want a usable reply even when a download fails, so that I'm never left without a link.

## Behavior

When a download is attempted (domain allowed per [`DOWNLOAD_ALLOWED_DOMAINS`](UFB-0009-download-allow-list.md), YouTube included) but fails for any reason, the user still gets a usable reply: the same mirror-rewrite logic used for disallowed domains is applied, offering a mirror link when one exists for that platform and it isn't excluded by [`REWRITE_ALLOWED_DOMAINS`](UFB-0023-rewrite-domain-allowlist.md). If no mirror link is available (the rewrite leaves the URL unchanged), the reply plainly states the download failed and gives only the original link, with no "parsed better" claim (or, in a group chat, nothing — see [UFB-0004](UFB-0004-group-chat-quietness.md)).

## Implementation

- Wraps [yt-dlp download](UFB-0015-yt-dlp-media-download.md); any failure (unsupported URL, network error, yt-dlp error) is treated the same way.
- Mirror found: `app.messages.download_failed_mirror()`; no mirror (modified URL equals the original): `app.messages.download_failed()` ([UFB-0037](UFB-0037-message-templates.md)), which states the failure and links only the original.

## Testing

### Unit

- Download fails, mirror available → reply with mirror + original link.
- Download fails, no mirror available, private chat → reply stating the download failed, original link only, no "parsed better" wording.
- Download fails, no mirror available, group chat → no reply.

## Status

Implemented
