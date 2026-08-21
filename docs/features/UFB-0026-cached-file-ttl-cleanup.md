# UFB-0026. Cached-file TTL cleanup

**Tags:** #ops #cache

## Behavior

Cached download files older than a configured age are automatically and
continuously removed, along with any directories left empty by that
removal, so the cache does not grow without bound. Cleanup keeps running for
the lifetime of the deployment, not just once at startup.

## Implementation

- A dedicated cleanup process runs on a repeating interval, deleting files
  past a configured TTL and pruning empty directories.

## Testing

### Integration

- A file older than the TTL → removed on the next cleanup pass.
- A file younger than the TTL → kept.
- Cleanup continues to run after the first pass (not a one-shot).

## Status

Implemented — with known gaps:

- The shipped cleanup runs its `find` deletions once, then sleeps 60 minutes
  and exits, with no restart policy — cleanup effectively never repeats
  ([BUGS #9](../BUGS.md#9-cache-cleanup-cron-compose-service-runs-once-and-then-stops-forever-medium-p2d2)).
- A more complete, looping, argument-validated cleanup script exists in the
  repo but isn't wired into the deployment at all
  ([BUGS #10](../BUGS.md#10-cleanupsh-is-never-shipped-or-run-low-p3d2)).
