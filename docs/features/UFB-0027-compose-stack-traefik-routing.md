# UFB-0027. Docker Compose stack with Traefik routing

**Tags:** #ops #deploy

## Behavior

The whole stack (app, file server, cache cleanup) deploys as one Docker
Compose project. The public-facing service is routed through an existing
Traefik reverse proxy with automatic TLS, addressed by `BASE_URL`. Every
setting documented as configurable is actually passed through to the
container that reads it, and services recover automatically from a crash.

## Implementation

- `app`, `nginx`, and `cron` (cleanup) services share a `cache` volume.
- `nginx` carries the Traefik routing/TLS labels; `app` is reached only
  through it.
- Compose environment blocks forward every operator-facing setting to the
  service that consumes it.

## Testing

### Human

- `docker compose up -d` brings up all services; `BASE_URL` resolves
  through Traefik with TLS.
- Killing a service container → it comes back up on its own.

## Status

Implemented — with known gaps:

- `CACHE_DIR`, `COOKIES_DIR`, `COOKIE_JAR_ENABLED`,
  `FOLLOW_REDIRECT_TIMEOUT`, and the `*_REWRITE_ENABLED` toggles aren't
  passed through in the shipped `docker-compose.yml`, so they can only ever
  take their code defaults (see `TODO.md`, Docker / Deploy).
- No service defines a `restart:` policy, so `app`/`nginx` also stay down
  after a crash (see `TODO.md`, Docker / Deploy, and
  [BUGS #9](../BUGS.md#9-cache-cleanup-cron-compose-service-runs-once-and-then-stops-forever-medium-p2d2)).
