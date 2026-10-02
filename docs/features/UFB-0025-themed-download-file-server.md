# UFB-0025. Themed download file server

**Tags:** #ops #hosting

## User Story

As a Telegram user, I want downloaded files served over plain HTTP with a themed 404, so that I can open or save them from a link.

## Behavior

Cached downloaded files are served over plain HTTP at `BASE_URL`. Each file is retrievable at its exact path, with a themed 404 page for missing files.

## Implementation

- nginx serves the cache directory read-only as plain static files — no server-side templating. Its only configuration is a tiny server block shipped inline in `docker-compose.yml` (a Compose `configs:` entry mounted at `/etc/nginx/conf.d/default.conf`): the stock static server on port 80 plus `error_page 404 /404.html;` and `location = /404.html { internal; }`, so a missing path returns the generated `404.html` with status 404 ([BUG-0067](../BUGS.md)). `/`, `/watch/<stem>.html` and `/<file>` remain plain files in the docroot.
- Cached files are world-readable (default umask), because nginx and the optional `telegram-bot-api` container read the shared volume as other users. The landing page, 404 page, and per-file watch pages are pre-rendered by the app; see [UFB-0033](UFB-0033-static-page-generation.md).

## Testing

### Integration

- Requesting a known cached file's URL → the file served as-is.
- Requesting an unknown path → the generated 404 page.

## Status

Implemented
