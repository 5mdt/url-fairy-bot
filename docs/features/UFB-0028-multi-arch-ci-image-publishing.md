# UFB-0028. Multi-arch CI image publishing

**Tags:** #ops #ci

## Behavior

Every push to the main branch, and every release, builds and publishes a
container image for multiple CPU architectures to the project's container
registry, tagged `latest`, with the commit SHA, and with the release tag
when one applies.

## Implementation

- A CI workflow builds `linux/amd64`, `linux/arm`, and `linux/arm64` images
  from `Dockerfile` (the app) and pushes to GHCR under the repository
  owner's namespace as `url-fairy-bot`. There is no separate nginx image to
  build; see [UFB-0030](UFB-0030-registry-only-deployment.md) for the image
  it runs instead.
- Tags are derived with `docker/metadata-action`.

## Testing

### Integration

- A push to main → new `latest` and `<sha>`-tagged `url-fairy-bot` images
  published.
- A tagged release → an additional matching-tag image published.

## Status

Implemented.
