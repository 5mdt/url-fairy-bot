# UFB-0013. Download-failure fallback

**Tags:** #rewrite #download #fallback

## Behavior

When a download is attempted (domain allowed, not a YouTube link) but fails
for any reason, the user still gets a usable reply: the same mirror-rewrite
logic used for disallowed domains is applied, offering a mirror link when
one exists for that platform. If no mirror link is available, the reply
explains the download failed and gives only the original link (or, in a
group chat, nothing — see [UFB-0004](UFB-0004-group-chat-quietness.md)).
The reply never claims to offer an "alternative" link that is identical to
the original.

## Implementation

- Wraps [yt-dlp download](UFB-0015-yt-dlp-media-download.md); any failure
  (unsupported URL, network error, yt-dlp error) is treated the same way.

## Testing

### Unit

- Download fails, mirror available → reply with mirror + original link.
- Download fails, no mirror available, private chat → reply stating the
  download failed, original link only.
- Download fails, no mirror available, group chat → no reply.

## Status

Implemented — with known gaps:

- The private-chat "no mirror available" reply text still says "here is an
  alternative link" even though the link offered is identical to the
  original (see `TODO.md`, Business logic).
