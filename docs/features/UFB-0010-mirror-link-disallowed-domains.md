# UFB-0010. Mirror link for disallowed domains

**Tags:** #rewrite #url

## Behavior

When a URL's domain isn't on the [download allow-list](UFB-0009-download-allow-list.md)
(`DOWNLOAD_ALLOWED_DOMAINS`), no download is attempted. If the domain also
isn't excluded by the [rewrite allow-list](UFB-0023-rewrite-domain-allowlist.md)
(`REWRITE_ALLOWED_DOMAINS`) and has a configured mirror rewrite, the reply
offers the mirror link alongside the original. If it doesn't (no mirror
configured, or the domain is excluded from `REWRITE_ALLOWED_DOMAINS`), the
reply says the domain isn't allowed for downloading and gives only the
original link (or, in a group chat, nothing at all — see
[UFB-0004](UFB-0004-group-chat-quietness.md)). Mirror-link availability is
independent of `DOWNLOAD_ALLOWED_DOMAINS` — it's governed solely by
`REWRITE_ALLOWED_DOMAINS`, and every platform with a configured mirror is
eligible, YouTube included.

## Implementation

- Runs immediately after the allow-list check fails, applying the same
  [platform/YouTube rewrite map](UFB-0011-platform-mirror-rewrites.md)
  (gated by `REWRITE_ALLOWED_DOMAINS`) used on the download-failure
  fallback path.

## Testing

### Unit

- Disallowed-for-download domain with a configured, rewrite-allowed mirror →
  reply with mirror + original link.
- Disallowed-for-download domain with no mirror, or mirror excluded via
  `REWRITE_ALLOWED_DOMAINS`, private chat → reply with original link only.
- Same, group chat → no reply.

## Status

Implemented

Changed:

- Mirror-link availability here now depends on `REWRITE_ALLOWED_DOMAINS`
  instead of the removed per-platform `*_REWRITE_ENABLED` toggles — see
  [UFB-0023](UFB-0023-rewrite-domain-allowlist.md) (2026-08-22).
