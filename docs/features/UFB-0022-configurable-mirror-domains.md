# UFB-0022. Configurable mirror domains

**Tags:** #config #rewrite

## Behavior

Every mirror domain used by [platform](UFB-0011-platform-mirror-rewrites.md)
and [YouTube](UFB-0012-youtube-mirror-rewrites.md) rewrites is
operator-configurable, independent of the source-matching pattern which
stays fixed in code.

## Implementation

- `SPOTIFY_MIRROR_DOMAIN`, `INSTAGRAM_MIRROR_DOMAIN`, `REDDIT_MIRROR_DOMAIN`,
  `TIKTOK_MIRROR_DOMAIN`, `TWITTER_MIRROR_DOMAIN`, `YOUTUBE_MIRROR_DOMAIN`,
  `YOUTUBE_SHORT_MIRROR_DOMAIN` — bare domains, without `www.`/`music.`
  prefixes (those are added automatically where needed).

## Testing

### Unit

- Overriding a `*_MIRROR_DOMAIN` value changes the rewritten host for that
  platform only.

## Status

Implemented
