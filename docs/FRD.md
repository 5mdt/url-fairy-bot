# Feature Requirements Document

## Behavior diagrams

The two mermaid flowcharts are the source of truth for how the features below
fit together end to end:

- [Message handling flow](flows/message-handling-flow.md) - Telegram and REST
  entry points: UFB-0001 - UFB-0006, UFB-0019, UFB-0020
- [URL processing flow](flows/url-processing-flow.md) - the shared
  `process_url_request()` decision tree: UFB-0007 - UFB-0018

## Available Features

- [UFB-0001. `/start` greeting](features/UFB-0001-start-greeting.md) - `#telegram` `#commands`
- [UFB-0002. Multi-URL message scanning](features/UFB-0002-multi-url-scanning.md) - `#telegram` `#url`
- [UFB-0003. Private-chat no-URL prompt](features/UFB-0003-private-no-url-prompt.md) - `#telegram` `#ux`
- [UFB-0004. Group-chat quietness](features/UFB-0004-group-chat-quietness.md) - `#telegram` `#groups`
- [UFB-0005. Reply-to-bot easter egg](features/UFB-0005-reply-to-bot-easter-egg.md) - `#telegram` `#groups` `#easter-egg`
- [UFB-0006. URL validation errors](features/UFB-0006-url-validation-errors.md) - `#telegram` `#validation`
- [UFB-0007. Redirect resolution](features/UFB-0007-redirect-resolution.md) - `#url` `#redirects`
- [UFB-0008. Query-string stripping](features/UFB-0008-query-string-stripping.md) - `#url` `#privacy`
- [UFB-0009. Download allow-list](features/UFB-0009-download-allow-list.md) - `#config` `#download` `#allowlist`
- [UFB-0010. Mirror link for disallowed domains](features/UFB-0010-mirror-link-disallowed-domains.md) - `#rewrite` `#url`
- [UFB-0011. Platform mirror-domain rewrites](features/UFB-0011-platform-mirror-rewrites.md) - `#rewrite`
- [UFB-0012. YouTube mirror rewrites](features/UFB-0012-youtube-mirror-rewrites.md) - `#rewrite` `#youtube`
- [UFB-0013. Download-failure fallback](features/UFB-0013-download-failure-fallback.md) - `#rewrite` `#download` `#fallback`
- [UFB-0014. Markdown reply formatting](features/UFB-0014-markdown-reply-formatting.md) - `#telegram` `#ux`
- [UFB-0015. yt-dlp media download](features/UFB-0015-yt-dlp-media-download.md) - `#download` `#media`
- [UFB-0016. Download caching](features/UFB-0016-download-caching.md) - `#download` `#cache`
- [UFB-0017. Cookie file merging](features/UFB-0017-cookie-file-merging.md) - `#download` `#cookies`
- [UFB-0018. Persistent cookie jar](features/UFB-0018-persistent-cookie-jar.md) - `#download` `#cookies` `#config`
- [UFB-0019. REST URL-processing endpoint](features/UFB-0019-rest-url-processing-endpoint.md) - `#api`
- [UFB-0020. In-process bot polling](features/UFB-0020-in-process-bot-polling.md) - `#runtime`
- [UFB-0021. Environment-based configuration](features/UFB-0021-environment-based-configuration.md) - `#config`
- [UFB-0022. Configurable mirror domains](features/UFB-0022-configurable-mirror-domains.md) - `#config` `#rewrite`
- [UFB-0023. Rewrite domain allow-list](features/UFB-0023-rewrite-domain-allowlist.md) - `#config` `#rewrite` `#allowlist`
- [UFB-0024. Configurable log level](features/UFB-0024-configurable-log-level.md) - `#config` `#ops`
- [UFB-0025. Themed download file server](features/UFB-0025-themed-download-file-server.md) - `#ops` `#hosting`
- [UFB-0026. Cached-file TTL cleanup](features/UFB-0026-cached-file-ttl-cleanup.md) - `#ops` `#cache`
- [UFB-0027. Docker Compose stack with Traefik routing](features/UFB-0027-compose-stack-traefik-routing.md) - `#ops` `#deploy`
- [UFB-0028. Multi-arch CI image publishing](features/UFB-0028-multi-arch-ci-image-publishing.md) - `#ops` `#ci`

## Tags

- `#telegram`: UFB-0001, UFB-0002, UFB-0003, UFB-0004, UFB-0005, UFB-0006, UFB-0014
- `#commands`: UFB-0001
- `#url`: UFB-0002, UFB-0007, UFB-0008, UFB-0010
- `#ux`: UFB-0003, UFB-0014
- `#groups`: UFB-0004, UFB-0005
- `#easter-egg`: UFB-0005
- `#validation`: UFB-0006
- `#redirects`: UFB-0007
- `#privacy`: UFB-0008
- `#config`: UFB-0009, UFB-0018, UFB-0021, UFB-0022, UFB-0023, UFB-0024
- `#download`: UFB-0009, UFB-0013, UFB-0015, UFB-0016, UFB-0017, UFB-0018
- `#allowlist`: UFB-0009, UFB-0023
- `#rewrite`: UFB-0010, UFB-0011, UFB-0012, UFB-0013, UFB-0022, UFB-0023
- `#youtube`: UFB-0012
- `#fallback`: UFB-0013
- `#media`: UFB-0015
- `#cache`: UFB-0016, UFB-0026
- `#cookies`: UFB-0017, UFB-0018
- `#api`: UFB-0019
- `#runtime`: UFB-0020
- `#ops`: UFB-0024, UFB-0025, UFB-0026, UFB-0027, UFB-0028
- `#hosting`: UFB-0025
- `#deploy`: UFB-0027
- `#ci`: UFB-0028
