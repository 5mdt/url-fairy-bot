# UFB-0027. Docker Compose stack with Traefik routing

**Tags:** #ops #deploy

## User Story

As an operator, I want the whole stack to deploy as one Docker Compose project behind Traefik, so that I bring it up with a single command.

## Behavior

The whole stack (app, file server, cache cleanup) deploys as one Docker Compose project. The public-facing service is routed through an existing Traefik reverse proxy with automatic TLS, addressed by `BASE_URL`. Every setting documented as configurable is actually passed through to the container that reads it, and services recover automatically from a crash.

## Implementation

- `app`, `nginx`, and `cron` (cleanup) services share a `cache` volume.
- `nginx` carries the Traefik routing/TLS labels; `app` is reached only through it.
- Compose environment blocks forward every operator-facing setting to the service that consumes it.
- The `app` container starts as root only long enough for `entrypoint.sh` to `chown` `CACHE_DIR` and `COOKIES_DIR` to the fixed-UID `app` user (uid 1000), then drops privileges with `su-exec` and runs `uvicorn` as that user ([BUG-0043](../BUGS.md)). The ownership fix for volumes created by earlier root-running versions is automatic; no manual `chown` is needed.
- `app` and `nginx` run `restart: unless-stopped`; see [UFB-0030](UFB-0030-registry-only-deployment.md) for images sourced from a registry instead of a local build, and for why `nginx` waits on `app`'s healthcheck before starting.

## Testing

### Human

- `docker compose up -d` brings up all services; `BASE_URL` resolves through Traefik with TLS.
- Killing a service container → it comes back up on its own.

## Status

Implemented
