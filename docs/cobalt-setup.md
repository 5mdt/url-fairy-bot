# Setting up cobalt

Operator runbook for [UFB-0052](features/UFB-0052-cobalt-fallback-downloader.md). Skip it and nothing changes: the bot works without cobalt.

## Overview

[cobalt](https://github.com/imputnet/cobalt) is a media downloader with an HTTP API. The `cobalt` service in `docker-compose.yml` runs it next to the bot as a fallback for when yt-dlp fails.

- **Internal only.** No host port, no traefik route. `app` reaches it at `http://cobalt:9000/` on the compose network.
- **License.** cobalt is AGPL-3.0. It runs as its own container and the bot only speaks HTTP to it, so the license stays on its side.
- **Not the public instance.** `cobalt.tools` has no public API: it is rate-limited and needs auth.
- **Profile-gated.** A plain `docker compose up -d` never starts it.
- **Not wired in yet.** The service and this guide ship first; the bot's client is UFB-0052's implementation.

## Steps

1. Optional: change the defaults in `.env` (all have working defaults):

   ```dotenv
   COBALT_API_URL=http://cobalt:9000/
   COBALT_DURATION_LIMIT=10800
   COBALT_RATELIMIT_MAX=20
   ```

   `COBALT_API_URL` must be the service name, not `localhost` and not a public URL: cobalt builds its download ("tunnel") links from it and `app` fetches them.
2. Start it:

   ```sh
   sudo docker compose --profile cobalt up -d
   ```
3. Wait for `healthy`:

   ```sh
   sudo docker compose ps cobalt
   ```
4. Smoke test from inside the network:

   ```sh
   sudo docker compose exec app curl -sS -X POST http://cobalt:9000/ \
     -H 'Accept: application/json' -H 'Content-Type: application/json' \
     -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
   ```

   Expect `"status":"tunnel"` with a `url` under `http://cobalt:9000/tunnel`. `"status":"error"` carries an `error.code` such as `error.api.fetch.fail`; check `sudo docker compose logs cobalt`.

## Cookies (optional)

For login-gated content. cobalt has its own JSON format, **not** the Netscape jar the bot uses ([UFB-0017](features/UFB-0017-cookie-file-merging.md)).

1. Create `${GLOBAL_DATA_FOLDER}/url-fairy-bot/config/cobalt-cookies.json` (the same directory the bot's cookies live in, mounted read-only into cobalt):

   ```json
   {
     "instagram": ["sessionid=<value>; csrftoken=<value>; ds_user_id=<value>"],
     "twitter": ["auth_token=<value>; ct0=<value>"]
   }
   ```

   Other keys: `reddit`, `youtube`, `vimeo`, `instagram_bearer`; see [cookies.example.json](https://github.com/imputnet/cobalt/blob/main/docs/examples/cookies.example.json).
2. Set `COBALT_COOKIE_PATH=/config/cobalt-cookies.json` in `.env` and recreate: `sudo docker compose --profile cobalt up -d cobalt`.

## Hardening (only if the port is ever exposed)

The default setup is unreachable from outside, so it needs none. If you publish it anyway, require API keys: put a `keys.json` in the config directory, set `API_KEY_URL=file:///config/cobalt-keys.json` and `API_AUTH_REQUIRED=1` on the service, and send `Authorization: Api-Key <uuid>`. Format: [protect-an-instance.md](https://github.com/imputnet/cobalt/blob/main/docs/protect-an-instance.md). For YouTube blocks, cobalt supports a `yt-session-generator` sidecar (`YOUTUBE_SESSION_SERVER`); not included here.

## Removing

```sh
sudo docker compose --profile cobalt down cobalt
```

## API: what the bot can reuse

cobalt API: `POST /` takes `{"url": …, options}` and answers by `status`; `GET /` returns instance info; `GET /tunnel` streams the file. The default rate limit is 20 requests per 60 s per client, and the bot is the only client.

| cobalt piece                                                     | Reuse in the bot                                                                                                                                                                                                                   | Verdict              |
|------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------|
| `POST /` → `tunnel` / `redirect` + `url`                         | Stream the file into the cache under `url_to_filename_stem()` (`app/download.py`); the existing post-download path in `attempt_download` (preview, watch page, Instant View, native send) then runs unchanged                      | Core of UFB-0052     |
| `picker` (`picker[]` of `{type, url, thumb}` + optional `audio`) | Maps onto `GalleryDownload` and `_attempt_gallery_download`: Instagram carousels ([UFB-0042](features/UFB-0042-instagram-post-downloads.md)), TikTok slideshows (a backup for the fragile extractor, BUG-0080), multi-media tweets | High value           |
| `error` → `error.code`                                           | Permanent codes (unsupported, content unavailable) become `UnsupportedUrlError`; transient ones (rate limit, fetch fail) fall through to the mirror link ([UFB-0013](features/UFB-0013-download-failure-fallback.md))              | Needed by the client |
| `GET /tunnel` `Content-Length` / `Estimated-Content-Length`      | Check against `CLOUD_SEND_VIDEO_MAX_MB` / `LOCAL_SEND_VIDEO_MAX_MB` before downloading                                                                                                                                             | Nice to have         |
| `GET /` (`cobalt.version`, `cobalt.services`)                    | A `cobalt` field in `/health` ([UFB-0034](features/UFB-0034-health-endpoints.md)), an unreachable alert ([UFB-0054](features/UFB-0054-maintainer-alerts.md)), skipping hosts cobalt doesn't support                                | Nice to have         |
| Request options                                                  | Fixed client defaults: `videoQuality: "720"`, `youtubeVideoCodec: "h264"` (plays in Telegram, keeps files small), `downloadMode: "auto"` (`"audio"` for audio-only links), `filenameStyle: "basic"`, `localProcessing: "disabled"` | Constants            |
| Metrics                                                          | `DOWNLOADERS = ("yt-dlp", "cobalt")` in `app/metrics.py` is already reserved                                                                                                                                                       | Ready                |
| Metadata                                                         | Almost none (a filename), so no help for [UFB-0041](features/UFB-0041-link-metadata-store.md)                                                                                                                                      | Not reusable         |
| Cookies                                                          | Different JSON format, so no sharing with the bot's jar                                                                                                                                                                            | Separate file        |
| `POST /session`, Turnstile, `local-processing`                   | Browser-client features                                                                                                                                                                                                            | Not used             |

Coverage beyond yt-dlp's strong suits: Bluesky, Snapchat, Pinterest, Rutube, Loom, OK.ru. Most other services overlap with yt-dlp, which is the point of a second downloader that breaks at different times.
