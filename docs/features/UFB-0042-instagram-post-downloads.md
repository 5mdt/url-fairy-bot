# UFB-0042. Instagram post downloads

**Tags:** #download #media

## User Story

As a Telegram user, I want an Instagram post, carousel or reel to arrive as real media, so that I don't get a mirror link to a third-party site instead.

## Behavior

Today an Instagram link is only rewritten to the `kkinstagram.com` mirror ([UFB-0011](UFB-0011-platform-mirror-rewrites.md)). With this feature the bot downloads it first and keeps the mirror as the fallback ([UFB-0013](UFB-0013-download-failure-fallback.md)).

| Post type            | Reply                                                                                                           |
|----------------------|-----------------------------------------------------------------------------------------------------------------|
| Reel or single video | Native video, like any other download                                                                           |
| Single photo         | The image                                                                                                       |
| Carousel             | An album of photos and videos, built like the TikTok galleries ([UFB-0039](UFB-0039-tiktok-photo-galleries.md)) |

## Quirks & Decisions

- Quirk: Instagram is matched only on `/p/` and `/reel/`. Open: whether `/tv/` and story links should be included.
- Quirk: Instagram usually needs a logged-in cookie jar ([UFB-0017](UFB-0017-cookie-file-merging.md)). Open: what a reply says when the post needs a login and no jar is configured. It likely falls back to the mirror link.
- Quirk: carousels mix photos and videos. Open: whether the album handling from UFB-0039 can be reused unchanged.

## Testing

### Human

- Send a public reel, a single-photo post and a carousel. Each arrives as native media.
- Send a link that needs a login with no cookie jar. The reply is the mirror link.

### Unit

- URL classification separates reels, single posts and carousels.

### Integration

- A failing Instagram download falls back to the mirror link.

## Status

Planned
