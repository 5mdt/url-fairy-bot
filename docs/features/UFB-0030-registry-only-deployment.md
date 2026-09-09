# UFB-0030. Registry-only deployment

**Tags:** #ops #deploy

## Behavior

The stack deploys from published container images with no repository
checkout on the host — a `docker-compose.yml` and a filled-in `.env` are
sufficient to bring up `app`, `nginx`, and `cron`.

## Implementation

- `app` pulls its `image:` reference from GHCR (`ghcr.io/5mdt/url-fairy-bot`)
  instead of building from the working tree; see
  [UFB-0028](UFB-0028-multi-arch-ci-image-publishing.md).
- `nginx` uses the stock `nginx:stable-alpine-slim` image.
- `app` declares a `healthcheck` (checks that
  `<CACHE_DIR>/watch/sample.html` exists) and `nginx` has
  `depends_on: app: condition: service_healthy`, so nginx never starts
  before the app has finished seeding the shared volume. Without this,
  nginx's very first lookup of a not-yet-written path can leave that path
  404ing indefinitely on some filesystems, even after the app writes the
  file — observed with `overlayfs` in testing.
- Local development keeps building the app from source via a
  `compose.dev.yml` override (`docker compose -f docker-compose.yml -f
  compose.dev.yml`); nginx needs no dev override since it isn't built at
  all.

## Testing

### Human

- From a directory with only `docker-compose.yml` and a filled-in `.env`
  (no repo checkout): `docker compose pull && docker compose up -d` brings
  up all three services.
- A cached file requested through `nginx` is served unchanged, and an
  unknown path still gets the app-generated 404.
- A cold `docker compose up -d` (empty volume) → `/`, `/watch/sample.html`,
  and every seeded static asset return 200 immediately, with no manual
  intervention, across repeated fresh starts — the regression case for the
  startup race above.

## Status

Implemented.
