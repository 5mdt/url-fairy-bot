# UFB-0028. Multi-arch CI image publishing

**Tags:** #ops #ci

## Behavior

Every push to the main branch, and every release, builds and publishes a
container image for multiple CPU architectures to the project's container
registry, tagged `latest`, with the commit SHA, and with the release tag
when one applies.

## Implementation

- A CI workflow builds `linux/amd64`, `linux/arm`, and `linux/arm64` images
  for two targets — `Dockerfile` (the app) and `nginx/Dockerfile` (config +
  theme baked in, see [UFB-0030](UFB-0030-registry-only-deployment.md)) —
  and pushes both to GHCR under the repository owner's namespace as
  `url-fairy-bot` and `url-fairy-bot-nginx`.
- Tags are derived with `docker/metadata-action`.

## Testing

### Integration

- A push to main → new `latest` and `<sha>`-tagged images published for
  both `url-fairy-bot` and `url-fairy-bot-nginx`.
- A tagged release → an additional matching-tag image published.

## Status

Implemented.
