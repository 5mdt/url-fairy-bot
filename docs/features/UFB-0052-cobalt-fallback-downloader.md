# UFB-0052. Cobalt fallback downloader

**Tags:** #download #fallback

## User Story

As a Telegram user, I want the bot to try a second downloader when the first fails, so that I get the video instead of a mirror link.

## Behavior

When `yt-dlp` fails, the bot tries a self-hosted [cobalt](https://github.com/imputnet/cobalt) API before falling back to the mirror link ([UFB-0013](UFB-0013-download-failure-fallback.md)). cobalt and yt-dlp break at different times, so it catches some failures the other misses.

With `COBALT_API_URL` empty, nothing changes. The result is saved under the same cache stem ([UFB-0016](UFB-0016-download-caching.md)). cobalt returns little metadata, so it doesn't help [UFB-0041](UFB-0041-link-metadata-store.md).

## Implementation

- An optional `cobalt` service in `docker-compose.yml` behind a profile, like `telegram-bot-api`.
- A `COBALT_API_URL` setting.
- cobalt runs as a separate container and the bot calls its HTTP API only, so its AGPL license doesn't reach the bot.
- The public `cobalt.tools` instance is not used: it is rate-limited and needs auth.
- The successful downloader is recorded in the metrics ([UFB-0045](UFB-0045-usage-metrics.md)) to judge whether the fallback earns its keep.

## Quirks & Decisions

- Quirk: a second downloader is another dependency to run.
  Open: keep it only if the metrics show it recovers a meaningful share of failures.

## Testing

### Human

- Break yt-dlp for a platform on purpose (bad URL pattern). With cobalt running, the video still arrives.
- With `COBALT_API_URL` empty, the reply is the mirror link as before.

### Unit

- The client parses cobalt's responses, including its error forms.

### Integration

- A yt-dlp failure followed by a cobalt success saves the file under the usual cache stem.

## Status

Planned
