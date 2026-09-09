# UFB-0029. Threads mirror-domain rewrites

**Tags:** #rewrite

## Behavior

Links to Threads (`threads.com`) are rewritten to an equivalent link on a
configured "mirror" domain, the same way as the other platforms covered by
[UFB-0011](UFB-0011-platform-mirror-rewrites.md). Defaults to
[FxThreads](https://github.com/AkitsukiNagi/FxThreads)'s `fx.akitsuki.me`
until `fxthreads.com` becomes available.

## Implementation

- Pattern `^https://(www\.)?threads\.com` in the `rewrite_map` in
  `apply_rewrite_map` (`app/url_processing.py`), gated by
  [`is_rewrite_allowed`](UFB-0023-rewrite-domain-allowlist.md) like every
  other entry.
- Mirror destination is operator-configurable via `THREADS_MIRROR_DOMAIN`
  (default `fx.akitsuki.me`), per [UFB-0022](UFB-0022-configurable-mirror-domains.md).

## Testing

### Unit

- A `threads.com` URL (with or without `www.`) → rewritten to the configured
  mirror domain.
- A domain that merely contains `threads.com` as a substring (e.g.
  `threadsXcom.example`) → not rewritten.
- Overriding `THREADS_MIRROR_DOMAIN` changes the rewritten host.

## Status

Implemented
