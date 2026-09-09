# UFB-0025. Themed download file server

**Tags:** #ops #hosting

## Behavior

Cached downloaded files are served over plain HTTP at `BASE_URL`. Each file
is retrievable at its exact path, with a themed 404 page for missing files.

## Implementation

- nginx serves the cache directory read-only as plain static files — no
  server-side templating. The landing page, 404 page, and per-file watch
  pages are pre-rendered by the app; see
  [UFB-0033](UFB-0033-static-page-generation.md).

## Testing

### Integration

- Requesting a known cached file's URL → the file served as-is.
- Requesting an unknown path → the generated 404 page.

## Status

Implemented.
