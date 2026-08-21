# UFB-0010. Mirror link for disallowed domains

**Tags:** #rewrite #url

## Behavior

When a URL's domain isn't on the [download allow-list](UFB-0009-download-allow-list.md),
no download is attempted. If the platform has a configured mirror rewrite,
the reply offers the mirror link alongside the original. If it doesn't, the
reply says the domain isn't allowed for downloading and gives only the
original link (or, in a group chat, nothing at all — see
[UFB-0004](UFB-0004-group-chat-quietness.md)). Mirror-link availability
never depends on the allow-list — every platform with a configured mirror
gets one here, YouTube included.

## Implementation

- Runs immediately after the allow-list check fails, applying the same
  [platform](UFB-0011-platform-mirror-rewrites.md) /
  [YouTube](UFB-0012-youtube-mirror-rewrites.md) rewrite rules used on the
  download-failure fallback path.

## Testing

### Unit

- Disallowed domain with a configured mirror → reply with mirror + original
  link.
- Disallowed domain with no mirror, private chat → reply with original link
  only.
- Disallowed domain with no mirror, group chat → no reply.

## Status

Implemented — with known gaps:

- YouTube URLs are rewritten by a separate code path that this branch
  doesn't call, so on a default install (empty allow-list) YouTube links get
  the plain "not allowed" message with no mirror link, unlike every other
  mirror platform
  ([BUGS #23](../BUGS.md#23-youtubes-mirror-link-alternative-is-incorrectly-gated-behind-download_allowed_domains-high-p1d2)).
