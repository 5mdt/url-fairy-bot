# UFB-0028. Multi-arch CI image publishing

**Tags:** #ops #ci

## Behavior

Every push to the main branch, and every release, builds and publishes a
container image for multiple CPU architectures to the project's container
registry, tagged `latest`, with the commit SHA, and with the release tag
when one applies.

## Implementation

- A CI workflow builds `linux/amd64`, `linux/arm`, and `linux/arm64` images
  and pushes to GHCR under the repository owner's namespace.

## Testing

### Integration

- A push to main → new `latest` and `<sha>`-tagged images published.
- A tagged release → an additional matching-tag image published.

## Status

Implemented — with known gaps:

- Uses deprecated Actions patterns (`::set-output`, old `actions/checkout`/
  `docker/*` action versions) that GitHub has removed or will remove
  support for (see `TODO.md`, Tooling / CI).
