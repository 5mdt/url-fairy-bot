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

- Downloads via yt-dlp, `format: best`, output template ending in
  `%(ext)s` so the saved file keeps its real container extension.
- A remux postprocessor (`merge_output_format: mp4`) losslessly repackages
  a compatible non-mp4 container into a real `.mp4`, using the `ffmpeg`
  binary the image now installs (see [UFB-0035](UFB-0035-per-file-preview-images.md)).
  Codecs `ffmpeg` cannot remux into mp4 are left in their original
  container/extension.
- The cache-hit check and the returned path resolve the file by globbing
  `<stem>.*` rather than assuming `.mp4`.
- Uses [cookies](UFB-0017-cookie-file-merging.md) when configured.
- Unsupported URLs and other yt-dlp failures both surface as a single
  "can't download this" condition, handled by
  [UFB-0013](UFB-0013-download-failure-fallback.md).

## Testing

### Unit

- Successful download → reply links to the cached file at the correct
  extension.
- A cache hit resolves whatever extension the file actually has on disk
  (e.g. `<stem>.webm`), not a hardcoded `.mp4`.
- Unsupported URL → falls through to the failure fallback.
- Any other yt-dlp exception → falls through to the failure fallback.

## Status

Implemented — with known gaps:

- Runs as a blocking call directly on the event loop
  ([BUGS #6](../BUGS.md#6-blocking-networkcpu-calls-run-directly-on-the-asyncio-event-loop-medium-p2d3)).
- No concurrency lock around "is this URL already downloading" — two
  simultaneous requests for the same not-yet-cached URL both start a
  download ([BUGS #14](../BUGS.md#14-cache-filenames-are-unbounded-non-deduplicated-and-directory-unsafe-low-p2d2)).
