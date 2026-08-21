# UFB-0016. Download caching

**Tags:** #download #cache

## Behavior

A URL that has already been downloaded is served from a local cache instead
of being downloaded again, identified by the source URL. Cache filenames
stay within filesystem name-length limits regardless of how long the source
URL is, and the cache directory always exists before it's needed.

## Implementation

- The URL is deterministically mapped to a cache filename and checked for
  existence before invoking yt-dlp.
- Cached files live under `CACHE_DIR` and are served over HTTP (see
  [UFB-0025](UFB-0025-themed-download-file-server.md)).

## Testing

### Unit

- Same URL requested twice → second request skips download, returns the
  cached path.
- A very long source URL → cache filename stays within filesystem limits.

## Status

Implemented — with known gaps:

- The filename is the entire URL with non-alphanumeric characters replaced
  by `_`, with no length cap — long URLs can exceed the filesystem's max
  filename length. `CACHE_DIR` is also never created ahead of use
  ([BUGS #14](../BUGS.md#14-cache-filenames-are-unbounded-non-deduplicated-and-directory-unsafe-low-p2d2)).
