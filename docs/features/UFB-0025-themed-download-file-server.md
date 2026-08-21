# UFB-0025. Themed download file server

**Tags:** #ops #hosting

## Behavior

Cached downloaded files are served over plain HTTP at `BASE_URL`, wrapped in
a themed header/footer, with a custom 404 page for missing files. Only
someone who already knows (or is given) a file's exact path can retrieve it
— the cache is not browsable, since directory listings would expose every
URL any user has ever had the bot process.

## Implementation

- A reverse-proxying web server serves the cache directory read-only, with
  header/footer/404 templates injected around file responses.

## Testing

### Integration

- Requesting a known cached file's URL → file served with the themed
  wrapper.
- Requesting an unknown path → themed 404 page.
- Requesting the cache root or a directory path → not a listing of cached
  files.

## Status

Implemented — with known gaps:

- Directory autoindexing is enabled at the cache root, so anyone who can
  reach `BASE_URL` can browse every cached file's name — including
  filenames that embed the source URL
  ([BUGS #13](../BUGS.md#13-public-autoindex-exposes-every-downloaded-file-lowcontextual-p2d1)).
