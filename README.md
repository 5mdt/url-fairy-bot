# URLFairyBot

![Logo](logo.svg)

URLFairyBot is a whimsical Telegram bot and REST API that sprinkles its magic on messy URLs, transforming them into organized and enchanting links. Let the bot be your URL-cleaning companion, waving its digital wand to reveal the hidden wonders behind every web address.

## Features

- Casts a spell on URLs, turning them from chaos to clarity.
- Conjures up valuable data from URLs, like a true magical oracle.
- Offers URL processing through both Telegram and a REST API, adding flexibility and utility.
- Your trusty URL fairy with a touch of whimsy and humor.

## Getting Started

Prepare for a magical journey as you set up and deploy the URLFairyBot.

### Prerequisites

- Docker and Docker Compose installed on your system (or your fairy dust, whichever is handier).

### Installation

The bot deploys straight from published images — no repository checkout
needed, just two files.

1. Fetch the compose file and an example `.env`:

   ```bash
   curl -sO https://raw.githubusercontent.com/5mdt/url-fairy-bot/main/docker-compose.yml
   curl -so .env https://raw.githubusercontent.com/5mdt/url-fairy-bot/main/.env.example
   ```

2. Edit `.env` and set the necessary enchantments (at minimum):

   ```dotenv
   BOT_TOKEN=your_bot_token
   BASE_URL=your_base_url
   ```

   The full list of variables `.env.example` ships with — all optional
   beyond `BOT_TOKEN`/`BASE_URL` — is documented in
   [Environment variables](#environment-variables) below.

   The bot also lets you override the "mirror" domains it rewrites URLs to
   (e.g. when a platform's domain isn't downloadable). All are optional;
   defaults shown below — values should be bare domains without `www.`/`music.`
   prefixes, since those are added automatically where needed:

   | Variable                      | Default           | Applies to                              |
   |-------------------------------|-------------------|-----------------------------------------|
   | `SPOTIFY_MIRROR_DOMAIN`       | `fxspotify.com`   | `open.spotify.com` / `spotify.com`      |
   | `INSTAGRAM_MIRROR_DOMAIN`     | `kkinstagram.com` | `instagram.com` `/p/` and `/reel/`      |
   | `REDDIT_MIRROR_DOMAIN`        | `rxddit.com`      | `reddit.com`                            |
   | `THREADS_MIRROR_DOMAIN`       | `fx.akitsuki.me`  | `threads.com`                           |
   | `TIKTOK_MIRROR_DOMAIN`        | `tfxktok.com`     | `tiktok.com`                            |
   | `TWITTER_MIRROR_DOMAIN`       | `fxtwitter.com`   | `twitter.com` / `x.com`                 |
   | `YOUTUBE_MIRROR_DOMAIN`       | `yfxtube.com`     | `music.youtube.com` / `www.youtube.com` |
   | `YOUTUBE_SHORT_MIRROR_DOMAIN` | `fxyoutu.be`      | `youtu.be`                              |

3. If you don't already run one, create a Traefik reverse proxy stack in a
   separate `docker-compose.yml` (own directory, own project):

   ```yaml
   ---
   version: "3"
   services:
   app:
      command:
         - --api.insecure=true
         - --providers.docker=true
         - --providers.docker.exposedbydefault=false
         - --entrypoints.web.address=:80
         - --entrypoints.websecure.address=:443
         - --certificatesResolvers.le.acme.email=user@example.com # CHANGE THIS
         - --certificatesResolvers.le.acme.storage=acme.json
         - --certificatesResolvers.le.acme.tlsChallenge=true
         - --certificatesResolvers.le.acme.httpChallenge=true
         - --certificatesResolvers.le.acme.httpChallenge.entryPoint=web
         - --entrypoints.web.http.redirections.entrypoint.to=websecure
         - --entrypoints.web.http.redirections.entrypoint.scheme=https
         - --providers.docker.network=traefik_default
      image: "traefik:latest"
      labels:
         com.centurylinklabs.watchtower.enable: "true"
      logging:
         driver: "json-file"
         options:
         max-file: "3"
         max-size: "1m"
      ports:
         - "80:80"
         - "443:443"
      restart: always
      volumes:
         - "/var/run/docker.sock:/var/run/docker.sock:ro"
         - "/opt/traefik/acme.json:/acme.json"
   ```

4. Brew your concoction of Docker spells to awaken the bot and API:

   ```shell
   docker compose up -d
   ```

## Configuration

### Environment variables

| Variable                    | Default                                | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
|-----------------------------|----------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `BOT_TOKEN`                 | *(required)*                           | Telegram bot token                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `BASE_URL`                  | *(required)*                           | Public base URL for serving downloaded files                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `IV_RHASH`                  | *(empty)*                              | `rhash` of a Telegram Instant View template you created for `BASE_URL` at [instantview.telegram.org](https://instantview.telegram.org) — see [docs/telegram-instant-view-setup.md](docs/telegram-instant-view-setup.md). Empty (the default): watch links use a themed `og:video` page, which Telegram already renders as an inline-playable card with no template needed. Set: watch links become `https://t.me/iv?url=...&rhash=...` and open in true Instant View |
| `INLINE_VIDEO_MAX_MB`       | `10`                                   | A watch page for a media file larger than this omits `og:video`/`twitter:player` tags and the inline `<video>` element — Telegram's Instant View fetches media server-side and fails the whole page for large files, so the tags/element are dropped instead of left broken                                                                                                                                                                                          |
| `TELEGRAM_API_URL`          | *(empty)*                              | Base URL of a self-hosted [Bot API server](https://github.com/tdlib/telegram-bot-api) run in local mode — see [docs/telegram-bot-api-setup.md](docs/telegram-bot-api-setup.md). e.g. `http://telegram-bot-api:8081`. Empty (the default): use Telegram's cloud API, 50 MB upload ceiling                                                                                                                                                                             |
| `CLOUD_SEND_VIDEO_MAX_MB`   | `10`                                   | A file at or under this size is always sent as a native video reply (works over Telegram's cloud API or a connected local one alike)                                                                                                                                                                                                                                                                                                                                 |
| `LOCAL_SEND_VIDEO_MAX_MB`   | `500`                                  | A file between `CLOUD_SEND_VIDEO_MAX_MB` and this is sent natively only if a local Bot API server (`TELEGRAM_API_URL`) is configured and reachable; above this, the bot never tries to upload — it replies with a "cannot upload" notice and the watch/download links instead                                                                                                                                                                                        |
| `IMAGE_TAG`                 | `latest`                               | Tag of the `url-fairy-bot` GHCR image to deploy                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `PUBLIC_PORT`               | `80:80`                                | Host:container port mapping for the `nginx` service                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `GLOBAL_DATA_FOLDER`        | `/Data`                                | Host directory whose `<folder>/url-fairy-bot/config` is mounted at `/config` (cookie files)                                                                                                                                                                                                                                                                                                                                                                          |
| `LETSENCRYPT_RESOLVER_NAME` | `letsencrypt-cloudflare-dns-challenge` | Traefik certresolver name used for TLS                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `FILE_TTL`                  | `3`                                    | Days a cached download may go **untouched** (access time, not modification time) before the in-app cleanup thread deletes it. With the default `relatime` mount behavior, a read only refreshes access time once per 24h, so values below 1 day aren't meaningful                                                                                                                                                                                                    |
| `CLEANUP_INTERVAL`          | `3600`                                 | Seconds between cache-cleanup sweeps                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `CACHE_DIR`                 | `/tmp/url-fairy-bot-cache/`            | Directory for cached downloads                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| `COOKIES_DIR`               | `/config/`                             | Directory containing cookie files for authenticated downloads                                                                                                                                                                                                                                                                                                                                                                                                        |
| `COOKIE_JAR_ENABLED`        | `false`                                | Use a persistent `cookie_jar.txt` so yt-dlp can save updated session tokens across requests. On first use, the jar is initialized by merging all `cookies*.txt` files in `COOKIES_DIR`.                                                                                                                                                                                                                                                                              |
| `DOWNLOAD_ALLOWED_DOMAINS`  | *(empty)*                              | Comma-separated list of domains real video downloads are restricted to. Empty means every domain is allowed (the default) — this setting only ever *restricts* downloads, it never affects whether a mirror link is offered (e.g. `instagram.com,twitter.com`)                                                                                                                                                                                                       |
| `REWRITE_ALLOWED_DOMAINS`   | *(empty)*                              | Comma-separated list of domains eligible for mirror-link rewriting (Spotify/Instagram/Reddit/TikTok/Twitter/X/YouTube). Empty means every platform is rewritten (the default). Independent of `DOWNLOAD_ALLOWED_DOMAINS`                                                                                                                                                                                                                                             |
| `FOLLOW_REDIRECT_TIMEOUT`   | `10`                                   | Timeout in seconds when following URL redirects                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `LOG_LEVEL`                 | `INFO`                                 | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)                                                                                                                                                                                                                                                                                                                                                                                                                  |

See [`.env.example`](.env.example) for a ready-to-copy file with every
variable, including the mirror-domain overrides above.

### Cookie Support

The bot supports authenticated downloads through cookies. To enable access to Instagram and other platforms requiring login:

1. Create a cookies file named `cookies.txt` or `cookies*.txt` in the directory specified by the `COOKIES_DIR` environment variable (defaults to `/config/`)

2. Browser extensions like [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookies-txt-locally/cjpalhdlnbpafiagobnlogmdbifnnodlj) can extract cookies from your browser

3. The bot will automatically merge all cookie files matching the pattern and use them for authenticated downloads

## Usage

### Telegram Bot

1. Initiate a conversation with the bot on Telegram.
2. Bestow upon it a twisted and tangled URL.
3. Witness the bot's incantations as it transforms the URL into an elegant masterpiece of clarity.
4. Share the now-gleaming link with fellow travelers to spread the charm of URLFairyBot.

### REST API

You can also access the URL processing functionality through the REST API. This makes URLFairyBot accessible through `curl` requests or other HTTP clients.

#### Endpoint

- **URL**: `POST /process_url/`
- **Body**: JSON with `url` field

#### Example Request

```bash
curl -X POST "http://localhost:8000/process_url/" -H "Content-Type: application/json" -d '{"url": "https://example.com/some-url"}'
```

#### Example Response

```json
{
  "status": "success",
  "data": "https://example.com/processed-url"
}
```

This flexibility allows you to use URLFairyBot in various applications outside of Telegram, making it a versatile tool for URL cleaning and transformation.

#### Health Endpoints

- **`GET /healthz`**: liveness probe, always returns `200 {"status": "ok"}` while the process is up.
- **`GET /health`**: readiness probe. Returns `200 {"status": "ok", "polling": true, "pages_seeded": true}`
  when the Telegram bot's polling loop is alive and the static pages have been seeded, or
  `503 {"status": "degraded", ...}` with the failing flag(s) set to `false` otherwise.

```bash
curl -i "http://localhost:8000/health"
```

## Contributing

Join the enchanting circle! If you stumble upon a bug or have an idea for a new spell, conjure an issue or send a magical pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for spellbinding details.

## Authors

- Vladimir Budylnikov aka [@nett00n](https://github.com/nett00n)

---

2023-2024, Tbilisi, Sakartvelo
