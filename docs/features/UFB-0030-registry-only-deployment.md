# UFB-0030. Registry-only deployment

**Tags:** #ops #deploy

## Behavior

The stack deploys from published container images with no repository
checkout on the host — a `docker-compose.yml` and a filled-in `.env` are
sufficient to bring up `app`, `nginx`, and `cron`.

## Implementation

- `app` and `nginx` both pull `image:` references from GHCR
  (`ghcr.io/5mdt/url-fairy-bot` and `ghcr.io/5mdt/url-fairy-bot-nginx`)
  instead of building from the working tree.
- `nginx/conf.d/` and `nginx/theme/` are baked into the `url-fairy-bot-nginx`
  image (`nginx/Dockerfile`) instead of bind-mounted from the repo — see
  [UFB-0028](UFB-0028-multi-arch-ci-image-publishing.md).
- Local development keeps building from source via a `compose.dev.yml`
  override (`docker compose -f docker-compose.yml -f compose.dev.yml`).

## Testing

### Human

- From a directory with only `docker-compose.yml` and a filled-in `.env`
  (no repo checkout): `docker compose pull && docker compose up -d` brings
  up all three services.
- A cached file requested through `nginx` still gets the themed
  header/footer, and an unknown path still gets the themed 404 — proof the
  baked-in image serves the same config/theme the bind mounts used to.

## Status

Implemented.
