# UFB-0028. Multi-arch CI image publishing

**Tags:** #ops #ci

## User Story

As a maintainer, I want multi-architecture container images built and published by CI, so that every push and release is deployable on any host.

## Behavior

Every push to any branch, every git tag, a weekly Sunday run on main, and any manual run builds and publishes a container image for multiple CPU architectures to the project's container registry. Main is tagged `stable` and with the short commit SHA, a git tag with the tag, and any other branch with its name. Pull requests build the image without pushing it.

## Implementation

- A Woodpecker pipeline (`.woodpecker.yml`) builds `linux/amd64` and `linux/arm64` images from `Dockerfile` (the app) with `plugin-docker-buildx` and pushes to Docker Hub as `5mdt/url-fairy-bot`, using the global `5mdt_docker_io_{url,user,pat}` Woodpecker secrets. There is no separate nginx image to build; see [UFB-0030](UFB-0030-registry-only-deployment.md) for the image it runs instead.
- Tags are derived by an `image-tags` step into a `.tags` file: main → `stable` + 7-char SHA; git tag → the tag; any other branch → its name with `/` replaced by `-`. Pull requests run a `dry_run` build only.
- The weekly run is a Woodpecker cron job (repo settings → Cron) on branch `main`, schedule `0 0 0 * * 0` (Sundays 00:00, seconds-first syntax); the pipeline just accepts the `cron` event. Manual runs use the branch picked in the UI.
- Previously this ran as a GitHub Actions workflow pushing to GHCR.

## Testing

### Integration

- A push to main → new `stable` and `<sha>`-tagged `url-fairy-bot` images published.
- A push to a development branch → an image tagged with its (slash-replaced) name.
- The Sunday cron job and a manual run on main → a refreshed `stable` image.
- A git tag → an additional matching-tag image published.

## Status

Implemented
