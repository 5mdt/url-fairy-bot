# UFB-0057. Reddit posts, comments, profiles and subreddits

**Tags:** #reddit #download #media #telegram #ux #hosting

## User Story

As a Telegram user, I want a Reddit link to produce a readable reply (text, author, media), so that I can read the post, comment, profile or subreddit without leaving Telegram.

## Behavior

Reddit blocks anonymous API access, so yt-dlp fails on nearly every Reddit link and the reply used to be a mirror link ([UFB-0011](UFB-0011-platform-mirror-rewrites.md)). Reddit links are now read through Reddit's API ([Implementation](#implementation)).

| Link                                                                   | Reply                                                                                                                                                                                                     |
|------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Post (`/r/<sub>/comments/<id>/...`)                                    | Bold title, `👤` clickable `u/author`, the text as a quote, the media (photo, album, or native video). `📖 Read more` opens the Instant View page with the full text and images when the text is clipped. |
| Comment (`/r/<sub>/comments/<id>/comment/<cid>` or `.../<slug>/<cid>`) | `👤` clickable `u/commenter`, the comment as a quote, the comment's media, and `📄 Original post`: an Instant View page showing the comment followed by the full original post.                           |
| Profile (`/user/<name>`, `/u/<name>`)                                  | Avatar photo; caption with display name, clickable `u/name`, karma, cake day and the bio as a quote; `📄 Profile` opens an Instant View page (banner, avatar, bio).                                       |
| Subreddit (`/r/<sub>`)                                                 | Icon photo; caption with title, clickable `r/name`, members, creation date, NSFW flag and the description as a quote; `📄 Subreddit` opens an Instant View page (banner, icon, full description).         |

Hosts `reddit.com` with `www.`, `old.`, `new.`, `m.` or `np.` are matched. Share links (`/r/<sub>/s/<code>`) and `redd.it/<id>` resolve to these shapes through [UFB-0007](UFB-0007-redirect-resolution.md). Any other Reddit URL (wiki, search, ...) keeps the old path (yt-dlp, then mirror link).

Replies with media go out as a photo album ([UFB-0039](UFB-0039-tiktok-photo-galleries.md)) or native video ([UFB-0036](UFB-0036-native-video-replies.md)) with the text as the caption (1024 characters). Text-only replies use Telegram's 4096-character limit. Any API failure (403, 404, 429, deleted, suspended, private) falls back to the mirror link ([UFB-0013](UFB-0013-download-failure-fallback.md)).

## Implementation

- `app/reddit.py`: `parse_link`, an authenticated API client, media extraction and `reddit_download`.
- Auth, in order: app-only OAuth (`REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET`, `client_credentials`, token cached until a minute before expiry, refreshed once on 401) against `oauth.reddit.com`; else the `reddit.com` cookies (from the cookie jar when `COOKIE_JAR_ENABLED`, kept fresh by the keepalive of [UFB-0038](UFB-0038-cookie-keepalive.md); otherwise from `COOKIES_DIR/cookies*.txt`) against `www.reddit.com/*.json`; else anonymous.
- Post and comment come from one `/comments/<id>` call (`comment=<cid>` focuses the comment). Crossposts take their media from the parent.
- Media: gallery order from `gallery_data`, `AnimatedImage` sent as a still, inline images of text posts, `post_hint: image`. An image over 10 MB falls back to its largest preview. A video post passes its `hls_url` to `yt_dlp_download`, cached under the post URL's stem.
- Images are cached in `CACHE_DIR/gallery/<stem>/NN.<ext>` ([UFB-0016](UFB-0016-download-caching.md)); the record goes to the metadata store with a `subtitle` stats line ([UFB-0041](UFB-0041-link-metadata-store.md)).
- `CACHE_DIR/reddit/<stem>.html` is the Instant View page (`reddit.html` template), wrapped with `t.me/iv?...` when `IV_RHASH` is set ([UFB-0032](UFB-0032-telegram-instant-view-embeds.md)). It is swept with the record by TTL ([UFB-0026](UFB-0026-cached-file-ttl-cleanup.md)).
- Settings: `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`. How to get the credentials or cookies: [docs/reddit-setup.md](../reddit-setup.md).

## Quirks & Decisions

- Quirk: Reddit markdown is not rendered. Decision: text is shown as plain paragraphs and line breaks.
- Quirk: animated gallery items are GIFs or videos. Decision: sent as stills.
- Quirk: Reddit pages are written once at download time, not re-rendered on restart like watch pages ([UFB-0033](UFB-0033-static-page-generation.md)). Decision: acceptable, they are cheap to re-fetch after the TTL.
- Quirk: no credentials and no cookies means Reddit 403s. Decision: the link falls back to the mirror as before.
- Quirk: app-only access hides NSFW-gated and quarantined content. Proposed: an opt-in account login, [UFB-0058](UFB-0058-reddit-account-login.md).
- Quirk: `[deleted]` authors have no profile. Decision: shown without a link.

## Testing

### Human

- Send a post, a comment, a gallery post, a video post, a profile and a subreddit link. Each gets the reply above; Instant View opens with images.
- Remove the credentials and cookies. A Reddit link replies with the mirror link.

### Unit

- Link parsing for every shape and host, and non-matches.
- OAuth token fetch, caching and refresh; cookie fallback, from the jar when it is enabled and from the files when it is missing or unreadable; 403/429/non-JSON raise the unsupported error.
- Media extraction: gallery order, animated stills, oversize fallback, HLS URL, crosspost.
- Record mapping, including `[deleted]`.
- Caption `subtitle` line within budget; Instant View pages for post, comment, profile and subreddit, escaped.

### Integration

- `process_url_request` routes each kind, passes a video's HLS URL to yt-dlp, and falls back to the mirror on a Reddit error.
- A cleanup sweep keeps a text-only post's record while its page exists.

## Status

Implemented
