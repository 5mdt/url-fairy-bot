# UFB-0041. Link metadata in replies

**Tags:** #download #hosting #ux

## User Story

As a Telegram user, I want a reply to carry the link's description, uploader and subtitles, so that I can tell what a video is without opening the original post.

## Behavior

A successful download stores a trimmed metadata record next to its media, and the reply and watch page use it.

| Where                                                             | What it shows                                                                                                                                                                                                                                  |
|-------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Reply caption                                                     | Short form: title, `👤` uploader (linked to the profile), a clipped description as a quote, and a `📖 Read more` link to the watch page when the description is clipped or left out. Stays well under Telegram's 1024-character caption limit. |
| Watch page ([UFB-0032](UFB-0032-telegram-instant-view-embeds.md)) | Full form: long description (paragraphs and line breaks kept), uploader and avatar, subtitle files.                                                                                                                                            |

The source is yt-dlp's info dict, plus the TikTok photo-post item data ([UFB-0039](UFB-0039-tiktok-photo-galleries.md)). A download without metadata (for example a future fallback downloader) still replies exactly as today.

## Implementation

- `app/metadata.py` owns the store. Public API: `meta_path(name)`, `trim_info(info)`, `trim_tiktok_item(item)`, `write(name, record)`, `read(name)`, `lookup(url)`, `delete(name)`, `caption(record, budget)`.
- A trimmed JSON is written to `CACHE_DIR/meta/<stem>.json`, not yt-dlp's full `.info.json`. `<stem>` is the URL's cache stem ([UFB-0016](UFB-0016-download-caching.md)); `name` accepts a stem or a media file name.
- Record fields (all optional on read): `title`, `uploader`, `uploader_url`, `description`, `avatar_url`, `subtitles` (file names), `source_url`, `extractor`, `duration`, `saved_at`.
- yt-dlp runs through `extract_info(url, download=True)`; its info dict is trimmed and written after a successful download. A TikTok photo post is trimmed from its item data the same way.
- Subtitles (`en.*`, manual tracks only) are saved to `CACHE_DIR/subs/<stem>/`, never next to the media, so they cannot be mistaken for it.
- `render_watch_page` reads the record itself, so `seed_static_pages` re-renders it after a restart ([UFB-0033](UFB-0033-static-page-generation.md)).
- The cleanup sweep removes `meta/<stem>.json` and `subs/<stem>/` with their media, and as orphans once the media is gone ([UFB-0026](UFB-0026-cached-file-ttl-cleanup.md)).
- It is the shared store for [UFB-0048](UFB-0048-song-identification.md), [UFB-0050](UFB-0050-duplicate-link-detection.md), [UFB-0051](UFB-0051-report-broken-link.md) and [UFB-0047](UFB-0047-profile-cards.md): they call `lookup(url)` / `read` / `write` and may add their own keys, which `read` returns untouched.

## Quirks & Decisions

- Quirk: nothing besides the media, preview, watch page and gallery files was saved to the cache, so there was nothing to render metadata from after a restart. Decision: the trimmed JSON store above.
- Quirk: which fields go in the caption was undecided. Decision: title (bold), `👤` plus the uploader name (a link when the record has an `https://` profile URL of at most 300 characters, plain text otherwise), and a description excerpt in a quote (`<blockquote>`), clipped to fit. The excerpt shrinks first, then is dropped, then the title is clipped, so caption plus links stays under 1024 characters.
- Quirk: TikTok gives the same text as title and description. Decision: the text shows once. A description contained in the title (or equal to it) is left out; a title contained in the description (ignoring case and a trailing `…` or `...`, which TikTok adds when it cuts the title) is left out and the description quote stays.
- Quirk: the caption can only hold a short excerpt. Decision: when the description is clipped or left out, the caption gets a `📖 Read more` line linking the watch page (`#description`), wrapped as `t.me/iv?...` when `IV_RHASH` is set ([UFB-0032](UFB-0032-telegram-instant-view-embeds.md)), so Instant View shows the full text. No link when the whole description fits, or when there is no watch page (a TikTok gallery without audio). The link costs caption budget like any other line.
- Quirk: Instant View ignores `white-space: pre-wrap`. Decision: the watch page renders a blank line as a new `<p>` and a single newline as `<br>`.
- Quirk: stored descriptions were capped at 5000 characters. Decision: the cap is 100 000.
- Quirk: subtitles may be long or absent. Decision: the watch page links them, never inlines them, and the caption never mentions them.
- Quirk: avatar URLs are remote CDN links that may expire. Decision: the watch page hotlinks `https` avatars only and omits the image when absent; nothing is downloaded.
- Quirk: a cache hit has no yt-dlp info. Decision: the record written by the first download is reused; a download whose record is missing replies as before.

## Testing

### Human

- Send a YouTube or TikTok link. The reply caption shows the short metadata and the watch page shows the full text.
- Restart the container and open the same watch page. It still renders its metadata.

### Unit

- The trimming function keeps only the agreed fields and tolerates missing keys.
- The caption builder never exceeds its budget, escapes HTML, and shrinks the excerpt first.
- A clipped or dropped description with a `more_url` adds a `📖 Read more` link within the budget; a fully shown or empty description, or no `more_url`, adds none; the URL is escaped.
- The uploader line links the profile only for `https://` URLs, and repeated title/description text is shown once.
- `write`/`read`/`lookup`/`delete` round-trip a record; a missing or corrupt file reads as `None`.
- A download with no info dict writes no record and replies as before.
- The watch page shows title, uploader, avatar, full description (blank line → `<p>`, newline → `<br>`) and subtitle links, and escapes them.

### Integration

- A cleanup sweep removes the `meta/<stem>.json` file and `subs/<stem>/` together with their media, and an orphaned record once its media is gone.
- `seed_static_pages` re-renders a watch page with its metadata.

## Status

Implemented
