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

1. Begin your adventure by cloning this repository:

   ```bash
   git clone https://github.com/5mdt/urlfairy-bot.git
   cd urlfairy-bot
   ```

2. Craft a `.env` file in the root directory and set the necessary enchantments:

   ```dotenv
   BOT_TOKEN=your_bot_token
   BASE_URL=your_base_url
   ```

3. Create a Traefik reverse proxy `docker-compose.yml` file:

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
         - --providers.docker.network=traefik_default1
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
   docker-compose up -d
   ```

## Configuration

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | _(required)_ | Telegram bot token |
| `BASE_URL` | _(required)_ | Public base URL for serving downloaded files |
| `CACHE_DIR` | `/tmp/url-fairy-bot-cache/` | Directory for cached downloads |
| `COOKIES_DIR` | `/config/` | Directory containing cookie files for authenticated downloads |
| `COOKIE_JAR_ENABLED` | `false` | Use a persistent `cookie_jar.txt` so yt-dlp can save updated session tokens across requests. On first use, the jar is initialized by merging all `cookies*.txt` files in `COOKIES_DIR`. |
| `DOWNLOAD_ALLOWED_DOMAINS` | _(empty)_ | Comma-separated list of domains allowed for video download (e.g. `instagram.com,twitter.com`) |
| `FOLLOW_REDIRECT_TIMEOUT` | `10` | Timeout in seconds when following URL redirects |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `INSTAGRAM_REWRITE_ENABLED` | `true` | Rewrite Instagram URLs to `kkinstagram.com` when download fails |
| `REDDIT_REWRITE_ENABLED` | `true` | Rewrite Reddit URLs to `rxddit.com` |
| `SPOTIFY_REWRITE_ENABLED` | `true` | Rewrite Spotify URLs to `fxspotify.com` |
| `TIKTOK_REWRITE_ENABLED` | `true` | Rewrite TikTok URLs to `tfxktok.com` |
| `TWITTER_REWRITE_ENABLED` | `true` | Rewrite Twitter/X URLs to `fxtwitter.com` |

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

## Contributing

Join the enchanting circle! If you stumble upon a bug or have an idea for a new spell, conjure an issue or send a magical pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for spellbinding details.

## Authors

- Vladimir Budylnikov aka [@nett00n](https://github.com/nett00n)

---

2023-2024, Tbilisi, Sakartvelo
