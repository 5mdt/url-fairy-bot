#!/usr/bin/env sh
# #UFB-0028 - publish the image for this pipeline run, reusing an existing one.
#
# Tags: main -> stable; git tag -> the tag; other branch -> its name ('/' -> '-');
# plus any git tag on the commit and the short sha. If <repo>:<short sha> is
# already in the registry, the manifest is re-tagged server-side (no pull,
# multi-arch kept); otherwise the image is built and pushed. Cron always builds
# to refresh base images. Ends by listing every image of the run.
#
# Env: REGISTRY, REPO, PLATFORMS, DOCKER_USERNAME, DOCKER_PASSWORD and the CI_*
# variables Woodpecker sets. Needs git, jq and a docker CLI.
set -eu

host=$(printf %s "$REGISTRY" | sed -e 's#^[a-z]*://##' -e 's#/*$##')
case "$host" in "" | index.docker.io | registry-1.docker.io) host=docker.io ;; esac
image="$host/$REPO"
sha=$(printf %s "$CI_COMMIT_SHA" | cut -c1-7)

if [ -n "${CI_COMMIT_TAG:-}" ]; then
  base="$CI_COMMIT_TAG"
elif [ "${CI_COMMIT_BRANCH:-}" = main ]; then
  base=stable
else
  base=$(printf %s "$CI_COMMIT_BRANCH" | tr / -)
fi
git config --global --add safe.directory "$CI_WORKSPACE"
tags=$({ echo "$base"; git tag --points-at "$CI_COMMIT_SHA"; echo "$sha"; } | awk 'NF && !seen[$0]++')
echo "image tags: $(echo $tags)"

set --
for tag in $tags; do set -- "$@" -t "$image:$tag"; done

reuse() {
  echo "reuse: $image:$sha exists, re-tagging instead of building"
  docker buildx imagetools create "$@" "$image:$sha"
}

build() {
  echo "build: no $image:$sha (or cron run), building"
  mkdir -p build
  export DOCKER_TLS_CERTDIR=
  dockerd-entrypoint.sh >build/dockerd.log 2>&1 &
  i=0
  until docker info >/dev/null 2>&1; do
    i=$((i + 1))
    [ "$i" -le 60 ] || { cat build/dockerd.log; echo "dockerd did not start" >&2; exit 1; }
    sleep 1
  done
  docker buildx create --name ci --driver docker-container --use >/dev/null
  docker buildx build --builder ci --platform "$PLATFORMS" --file Dockerfile \
    --label "org.opencontainers.image.revision=$CI_COMMIT_SHA" \
    --label "org.opencontainers.image.source=$CI_REPO_URL" \
    "$@" --push .
}

summary() {
  # every tag of the run points at the same manifest
  digest=$(docker buildx imagetools inspect "$image:$sha" --format '{{.Manifest.Digest}}')
  labels=$(docker buildx imagetools inspect "$image:$sha" --format '{{json .Image}}' |
    jq -c '[.. | objects | .Labels? | select(.)] | first // {}')
  echo
  echo "== images for this pipeline run =="
  for tag in $tags; do echo "$image:$tag"; done
  echo "digest: $digest"
  echo "labels: $labels"
}

printf %s "$DOCKER_PASSWORD" | docker login "$host" -u "$DOCKER_USERNAME" --password-stdin

if [ "${CI_PIPELINE_EVENT:-}" != cron ] &&
  docker buildx imagetools inspect "$image:$sha" >/dev/null 2>&1; then
  reuse "$@"
else
  build "$@"
fi
summary
