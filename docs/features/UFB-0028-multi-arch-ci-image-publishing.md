# UFB-0028. Multi-arch CI image publishing

**Tags:** #ops #ci

## Behavior

Every push to the main branch, and every git tag, builds and publishes a container image for multiple CPU architectures to the project's container registry, tagged `latest` and with the short commit SHA on main, or with the git tag on a tag. Pull requests build the image without pushing it.

## Implementation

- A Woodpecker pipeline (`.woodpecker.yml`) builds `linux/amd64`, `linux/arm`, and `linux/arm64` images from `Dockerfile` (the app) with `plugin-docker-buildx` and pushes to Docker Hub as `5mdt/url-fairy-bot`, using the global `5mdt_docker_io_{url,user,pat}` Woodpecker secrets. There is no separate nginx image to build; see [UFB-0030](UFB-0030-registry-only-deployment.md) for the image it runs instead.
- Tags are derived by an `image-tags` step into a `.tags` file: main → `latest` + 7-char SHA; git tag → the tag; any other branch → its name with `/` replaced by `-`. Pull requests run a `dry_run` build only.
- Previously this ran as a GitHub Actions workflow pushing to GHCR.

## Testing

### Integration

- A push to main → new `latest` and `<sha>`-tagged `url-fairy-bot` images published.
- A git tag → an additional matching-tag image published.

## Status

Implemented.
