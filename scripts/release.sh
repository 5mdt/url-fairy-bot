#!/usr/bin/env bash
# Cut a release: gate, move CHANGELOG "Unreleased" into a version section, commit, tag.
# Usage: scripts/release.sh patch|minor|major | --version
# Gates: pre-commit (if configured), `ddd check` (if scripts/ddd exists), and $RELEASE_GATE (any
# command, e.g. RELEASE_GATE="make test"). Nothing is pushed or deployed.
set -euo pipefail

VERSION="2026-10-06T15:57:23Z" # RFC 3339 date-time; bump on EVERY edit to this script (`date -u +%Y-%m-%dT%H:%M:%SZ`)

if [ "${1:-}" = --version ]; then
  echo "release $VERSION"
  exit 0
fi

bump=${1:-patch}
changelog=docs/CHANGELOG.md

die() { echo "release: $*" >&2; exit 1; }

case "$bump" in patch | minor | major) ;; *) die "BUMP must be patch, minor or major (got '$bump')" ;; esac

cd "$(git rev-parse --show-toplevel)"

[ "$(git rev-parse --abbrev-ref HEAD)" = main ] || die "not on main"
[ -z "$(git status --porcelain)" ] || die "working tree not clean; commit or stash first"

# --- next version -----------------------------------------------------------
last=$(git describe --tags --abbrev=0 --match '[0-9]*.[0-9]*.[0-9]*' 2>/dev/null || true)
if [ -z "$last" ]; then
  next=0.1.0
else
  IFS=. read -r major minor patch <<<"$last"
  case "$bump" in
    major) next=$((major + 1)).0.0 ;;
    minor) next=$major.$((minor + 1)).0 ;;
    patch) next=$major.$minor.$((patch + 1)) ;;
  esac
fi
! git rev-parse -q --verify "refs/tags/$next" >/dev/null || die "tag $next already exists"

# --- gates ------------------------------------------------------------------
if [ -f .pre-commit-config.yaml ]; then
  pre-commit run --all-files || die "pre-commit failed"
  [ -z "$(git status --porcelain)" ] || die "pre-commit modified files; review, commit, retry"
fi
if [ -x scripts/ddd/ddd ]; then ./scripts/ddd/ddd check; fi
if [ -n "${RELEASE_GATE:-}" ]; then bash -c "$RELEASE_GATE"; fi

# --- changelog --------------------------------------------------------------
[ -f "$changelog" ] || die "$changelog not found"
grep -qx '## Unreleased' "$changelog" || die "$changelog has no '## Unreleased' section"
entries=$(awk '/^## /{s = ($0 == "## Unreleased"); next} s && /^- /{n++} END{print n+0}' "$changelog")
[ "$entries" -gt 0 ] || die "nothing to release: add entries under '## Unreleased' in $changelog"

trap 'echo "release: failed; undo with: git checkout $changelog" >&2' ERR
heading="## $next ($(date +%F))"
tmp=$(mktemp)
awk -v h="$heading" '{print} $0 == "## Unreleased"{print ""; print h}' "$changelog" >"$tmp"
mv "$tmp" "$changelog"
grep -qxF "$heading" "$changelog" || die "version heading missing from $changelog"

# --- commit and tag ---------------------------------------------------------
git add "$changelog"
if [ -f .pre-commit-config.yaml ]; then
  pre-commit run --files "$changelog" || { git add "$changelog"; pre-commit run --files "$changelog"; }
fi
git commit -m "release $next"
git tag -a "$next" -m "$next"
trap - ERR

echo "Released $next. Next: git push --follow-tags"
