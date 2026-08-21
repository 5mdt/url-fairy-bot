# UFB-0015. yt-dlp media download

**Tags:** #download #media

## Behavior

For an allowed, non-YouTube URL, the bot attempts to download the media at
that URL and, on success, replies with a link to watch or download the
cached file. The saved file's extension matches the actual media container
yt-dlp produced, so it plays correctly in players/browsers that check file
extensions. A platform yt-dlp has no extractor for (e.g. Spotify) fails
immediately without unnecessary work.

## Implementation

- Downloads via yt-dlp, `format: best`.
- Uses [cookies](UFB-0017-cookie-file-merging.md) when configured.
- Unsupported URLs and other yt-dlp failures both surface as a single
  "can't download this" condition, handled by
  [UFB-0013](UFB-0013-download-failure-fallback.md).

## Testing

### Unit

- Successful download → reply links to the cached file at the correct
  extension.
- Unsupported URL → falls through to the failure fallback.
- Any other yt-dlp exception → falls through to the failure fallback.

## Status

Implemented — with known gaps:

- The output file is always named with a hardcoded `.mp4` extension
  regardless of yt-dlp's actual output format, and the image has no
  `ffmpeg` to remux into a real `.mp4` when needed
  ([BUGS #15](../BUGS.md#15-downloaded-files-are-always-saved-with-a-mp4-extension-low-p3d2)).
- Runs as a blocking call directly on the event loop
  ([BUGS #6](../BUGS.md#6-blocking-networkcpu-calls-run-directly-on-the-asyncio-event-loop-medium-p2d3)).
- No concurrency lock around "is this URL already downloading" — two
  simultaneous requests for the same not-yet-cached URL both start a
  download ([BUGS #14](../BUGS.md#14-cache-filenames-are-unbounded-non-deduplicated-and-directory-unsafe-low-p2d2)).
