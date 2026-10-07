# UFB-0041. Link metadata in replies

**Tags:** #download #hosting #ux

## User Story

As a Telegram user, I want a reply to carry the link's description, uploader and subtitles, so that I can tell what a video is without opening the original post.

## Behavior

A successful download stores a trimmed metadata record next to its media, and the reply and watch page use it.

| Where                                                             | What it shows                                                                                                 |
|-------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------|
| Reply caption                                                     | Short form: title, uploader, a clipped description. Stays well under Telegram's 1024-character caption limit. |
| Watch page ([UFB-0032](UFB-0032-telegram-instant-view-embeds.md)) | Full form: long description, uploader and avatar, subtitle files.                                             |

The source is yt-dlp's info dict, plus the TikTok photo-post item data ([UFB-0039](UFB-0039-tiktok-photo-galleries.md)). A download without metadata (for example a future fallback downloader) still replies exactly as today.

## Implementation

- A trimmed JSON (title, uploader, description, avatar URL, subtitle file names) is written to `CACHE_DIR/meta/<stem>.json`, not yt-dlp's full `.info.json`.
- `seed_static_pages` re-renders watch pages from it on restart ([UFB-0033](UFB-0033-static-page-generation.md)).
- The cleanup sweep removes it together with its media file ([UFB-0026](UFB-0026-cached-file-ttl-cleanup.md)).
- It is the shared store for [UFB-0048](UFB-0048-song-identification.md), [UFB-0050](UFB-0050-duplicate-link-detection.md) and [UFB-0047](UFB-0047-profile-cards.md).

## Quirks & Decisions

- Quirk: nothing besides the media, preview, watch page and gallery files is saved to the cache today, so there is nothing to render metadata from after a restart. Proposed: the trimmed JSON store above.
- Quirk: which fields go in the caption is undecided. Open: title and uploader only, or also a description excerpt.
- Quirk: subtitles may be long or absent. Open: link them from the watch page only, or inline an excerpt.

## Testing

### Human

- Send a YouTube or TikTok link. The reply caption shows the short metadata and the watch page shows the full text.
- Restart the container and open the same watch page. It still renders its metadata.

### Unit

- The trimming function keeps only the agreed fields and tolerates missing keys.
- The caption builder never exceeds 1024 characters.

### Integration

- A cleanup sweep removes the `meta/<stem>.json` file together with its media.

## Status

Planned
