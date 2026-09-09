# UFB-0025. Themed download file server

**Tags:** #ops #hosting

## Behavior

Cached downloaded files are served over plain HTTP at `BASE_URL`, wrapped in
a themed header/footer, with a custom 404 page for missing files. Each file
is retrievable at its exact path. A browsable index of the cache lives at
`/cache/`, see [UFB-0031](UFB-0031-landing-page-and-cache-index.md).

## Implementation

- A reverse-proxying web server serves the cache directory read-only, with
  header/footer/404 templates injected around file responses.

## Testing

### Integration

- Requesting a known cached file's URL → file served with the themed
  wrapper.
- Requesting an unknown path → themed 404 page.
- Requesting `/` → the landing page, not a listing of cached files.

## Status

Implemented.
