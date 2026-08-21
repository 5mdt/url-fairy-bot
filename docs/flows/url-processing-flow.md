# URL Processing Flow

What happens inside `process_url_request()` (`app/url_processing.py`) once a URL has arrived
from either the Telegram bot or the REST API — see
[`message-handling-flow.md`](./message-handling-flow.md) for how it gets there.

```mermaid
flowchart TD
    A["url (string)"] --> B["follow_redirects(url)<br/>HTTP HEAD, follow redirects,<br/>drop query string"]

    B --> C{"is_domain_allowed(final_url)?<br/>(checked against<br/>DOWNLOAD_ALLOWED_DOMAINS)"}

    C -- "not allowed" --> D["apply_rewrite_map(final_url)<br/>(Spotify/Instagram/Reddit/TikTok/Twitter → mirror domain)"]
    D --> E{"Rewrite changed the URL?"}
    E -- no --> F{"Group chat?"}
    F -- yes --> G["Stay silent"]
    F -- no --> H["Reply: domain not allowed<br/>+ original link"]
    E -- yes --> I["Reply: domain not allowed,<br/>here's an alternative<br/>+ modified link + original link"]

    C -- "allowed" --> J{"transform_youtube_url(final_url)<br/>matches a YouTube pattern?"}
    J -- yes --> K["Reply: can't download YouTube,<br/>here's an alternative<br/>+ mirror link + original link"]

    J -- no --> L["attempt_download(final_url)<br/>→ yt_dlp_download()"]
    L --> M{"Download succeeded?"}
    M -- yes --> N["Reply: Watch/Download link<br/>(served from CACHE_DIR via nginx)<br/>+ original link"]

    M -- "UnsupportedUrlError<br/>or any other failure" --> O["apply_rewrite_map(final_url)<br/>(same mirror rewrite as above)"]
    O --> P{"Rewrite changed the URL?"}
    P -- "no, and group chat" --> Q["Stay silent"]
    P -- "no, and private chat" --> R["Reply: alternative link<br/>(same as original,<br/>Telegram may parse it better)<br/>+ original link"]
    P -- yes --> S["Reply: alternative link<br/>+ modified link + original link"]
```

## Step-by-step summary

1. **Resolve redirects** — `follow_redirects()` sends a `HEAD` request and follows redirects to
   get the real destination URL, stripping its query string. Falls back to the original URL on
   timeout (see [`BUGS.md` #1](../BUGS.md#1-redirect-resolution-strips-query-strings-breaking-youtube-rewrites-high)
   and [#11](../BUGS.md#11-follow_redirects-only-handles-the-timeout-case-low) for gaps here).
2. **Domain allow-list gate** — if `DOWNLOAD_ALLOWED_DOMAINS` is configured and the resolved
   domain isn't on it, the bot never attempts a download; it only offers a rewritten "mirror"
   link if one exists for that platform (see
   [`BUGS.md` #5](../BUGS.md#5-domain-allow-list-can-be-bypassed-or-trivially-disabled-medium)
   for allow-list matching caveats).
3. **YouTube special-case** — YouTube videos are never downloaded; if the URL matches a known
   YouTube pattern, the bot immediately offers the mirror-domain alternative instead of trying
   `yt-dlp` at all.
4. **Attempt download** — for every other allowed domain, `yt_dlp_download()` tries to fetch
   and cache the media file. On success, the reply links to the cached file served over HTTP.
5. **Fallback on failure** — any download failure (unsupported site, network error, yt-dlp
   error) falls back to the same mirror-rewrite logic used for disallowed domains, so the user
   still gets a usable link when possible.
6. **Group-chat quietness** — throughout, if the "alternative" link would be identical to the
   original URL (nothing useful to add) and the message came from a group chat, the bot stays
   silent instead of replying — this is what keeps the bot from being noisy in group chats
   full of ordinary links.

## Where the mirror domains come from

`apply_rewrite_map()` and `transform_youtube_url()` both rewrite the URL's domain to a
configurable "mirror" service (e.g. `fxtwitter.com`, `kkinstagram.com`) that renders richer
previews/embeds than the original site. The domains are configurable via environment variables
(`*_MIRROR_DOMAIN` in `app/config.py`) and default to the values documented in `README.md`.
