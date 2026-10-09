# UFB-0047. Profile link cards

**Tags:** #telegram #hosting #ux

## User Story

As a Telegram user, I want a link to a profile to produce a readable profile card, so that sharing an account is as useful as sharing a post.

## Behavior

When a link points at a user profile (Instagram, TikTok, Twitter/X, Reddit, a YouTube channel and so on) instead of a post, the reply is a profile card rendered as an Instant View page ([UFB-0032](UFB-0032-telegram-instant-view-embeds.md)).

| Field                     | Notes                                                              |
|---------------------------|--------------------------------------------------------------------|
| Username and display name | always                                                             |
| Avatar                    | cached like other files ([UFB-0016](UFB-0016-download-caching.md)) |
| Bio or description        | where available                                                    |
| Follower counts           | where available                                                    |

Reddit profiles and subreddits ship first, in [UFB-0057](UFB-0057-reddit-links.md). Other platforms get no useful treatment today. Instagram, for example, is only matched on `/p/` and `/reel/` ([UFB-0011](UFB-0011-platform-mirror-rewrites.md)).

## Implementation

- A new `profile.html` template beside `watch.html` ([UFB-0033](UFB-0033-static-page-generation.md)).
- Per-platform profile fetch: yt-dlp can often extract channel and user info; otherwise a scraper or the platform's mirror service.
- Shares its metadata-extraction groundwork with [UFB-0041](UFB-0041-link-metadata-store.md).

## Quirks & Decisions

- Quirk: platforms expose different profile fields. Open: the minimum card every platform can fill, versus optional fields.
- Quirk: the avatar needs caching. Open: how long it lives and whether it is refreshed.

## Testing

### Human

- Send a profile link for each supported platform. A card with the avatar and bio opens as Instant View.

### Unit

- Profile URL detection separates profiles from posts per platform.

### Integration

- Fetching profile data failing falls back to the existing behavior for that link.

## Status

Planned
