# UFB-0039. TikTok photo-post galleries

**Tags:** #download #media #telegram #ux

## User Story

As a Telegram user, I want a TikTok photo post sent as a photo album with its audio, so that I can see the post without leaving Telegram.

## Behavior

A TikTok photo post (`https://www.tiktok.com/@user/photo/<id>`) is not supported by yt-dlp, so it used to fall back to a mirror link. The bot now replies with the post's images as a Telegram photo album (chunks of 10), the first photo carrying the usual Download/Source caption, followed by the post's audio track as an audio reply. If the images cannot be sent, the reply degrades to the plain text with links. A post with no images is treated as unsupported (mirror-link fallback, see [UFB-0013](UFB-0013-download-failure-fallback.md)).

## Implementation

- `app.download.is_tiktok_photo_url` detects photo URLs; `tiktok_gallery_download` reads the post data through yt-dlp's TikTok extractor (the `/photo/` URL rewritten to `/video/`) and saves images to `CACHE_DIR/gallery/<stem>/NN.jpg` and the audio to `CACHE_DIR/<stem>.mp3`. Cached galleries are reused ([UFB-0016](UFB-0016-download-caching.md)) and swept by TTL ([UFB-0026](UFB-0026-cached-file-ttl-cleanup.md)).
- `attempt_download` routes photo URLs there; `DownloadResult` carries `image_paths`. The first image doubles as the audio's preview image.
- `bot._reply_with_gallery` sends the album, then the audio.

## Quirks & Decisions

- Quirk: relies on yt-dlp's private `TikTokIE._extract_web_data_and_status` (isolated in `app.download._tiktok_item`); a yt-dlp refactor may break it. Tracked as #BUG-0080.

## Testing

### Unit

- Photo-URL detection.
- Gallery download writes images and audio; cache hit skips the network; no images raises `UnsupportedUrlError`; missing audio yields `None`.
- Bot sends albums (10 per group) with the caption on the first photo, then the audio; failure falls back to text.

## Status

Implemented
