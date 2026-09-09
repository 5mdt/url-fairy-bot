# UFB-0031. Landing page and cache index

**Tags:** #ops #hosting

## Behavior

`BASE_URL`'s root serves a static landing page introducing the bot, instead of
a directory listing. The download cache is browsable at `/cache/` — a themed
listing of every cached file, linked from the landing page. `/cache` without
the trailing slash redirects to `/cache/`.

Cached files stay retrievable at their existing root-level path
(`https://BASE_URL/<file>`, see [UFB-0025](UFB-0025-themed-download-file-server.md))
and are also reachable the same way under `/cache/<file>`.

Filenames in the `/cache/` listing currently embed the original source URL
they were downloaded from, so browsing the index reveals what URLs users have
sent the bot — see [BUGS #14](../BUGS.md), tracked separately.

## Implementation

- A static `index.html` (`nginx/theme/index.html`) is served at `= /`.
- `location /cache/` aliases the cache directory with `autoindex on`, wrapped
  in the same themed header/footer as single-file responses.
- `location = /cache` redirects (301) to `/cache/`.

## Testing

### Integration

- Requesting `/` → the landing page, not a listing.
- Requesting `/cache/` → a themed listing containing known cached files.
- Requesting `/cache` → 301 to `/cache/`.
- Requesting a cached file at the root and under `/cache/` → same content
  both ways.
- Requesting an unknown path → the themed 404 page.

## Status

Implemented.
