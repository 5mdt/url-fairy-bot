# Roadmap

Order, not scope. An item's contract stays in its feature doc or tracker entry.

| # | Epic                | Why here                                                                                                                        |
|---|---------------------|---------------------------------------------------------------------------------------------------------------------------------|
| 1 | Hardening           | Two P1 bugs: any slow request stalls everyone, and the public API is an open proxy; plus instant feedback while a request runs. |
| 2 | Observability       | Measure before building more; alerts and `/stats` build on the counters.                                                        |
| 3 | Metadata foundation | The store that duplicates, reports and richer replies share.                                                                    |
| 4 | Platform coverage   | New downloaders, judged by the metrics from epic 2.                                                                             |
| 5 | UX extras           | Nice-to-have surfaces on top of a solid base.                                                                                   |
| 6 | Later / scale       | Only if load requires it.                                                                                                       |

## 1. Hardening

1. #BUG-0006 - blocking calls on the event loop, now including the preview and `ffmpeg` calls; one slow download stalls every user.
2. #UFB-0055 - progress chat action ("typing…" / "sending a video…") [P1/D2, target 2.10.0]; needs #BUG-0006 first, since a blocked loop can't refresh the indicator.

**Done when:** one slow download doesn't stall other requests, `/process_url/` rejects private and loopback targets, and a user sees a chat action within a second of posting a link.

## 2. Observability

1. #UFB-0045 - usage metrics [P1/D3]; every later decision needs the numbers.
2. #UFB-0054 - maintainer alerts [P2/D3]; introduces `ADMIN_CHAT_ID`.
3. #UFB-0049 - `/stats` command [P3/D2]; reads the counters and reuses `ADMIN_CHAT_ID`.

**Done when:** failure rate per platform is visible and a dead cookie jar sends an admin alert.

## 3. Metadata foundation

1. #UFB-0041 - link metadata store [P1/D3]; the shared store.
2. #UFB-0050 - duplicate link detection [P3/D2]; reuses the store.
3. #UFB-0051 - report-broken-link button [P3/D2]; reuses the store and the failure reasons.

**Done when:** watch pages show metadata and survive a restart.

## 4. Platform coverage

1. #UFB-0042 - Instagram post downloads [P2/D3]; biggest gap versus the mirror link.
2. #UFB-0052 - cobalt fallback downloader [P2/D3]; keep it only if the epic 2 metrics show it earns its place.
3. #UFB-0053 - multiple cookie jars [P3/D3]; resilience for login-gated platforms.
4. #BUG-0080 - TikTok private extractor dependency; fragile.
5. #BUG-0076 - local-mode video send failure [P3]; undiagnosed and masked by a retry, so add the diagnostic logging and wait for a recurrence.

**Done when:** Instagram posts download natively and the mirror-fallback rate goes down.

## 5. UX extras

1. #UFB-0046 - inline mode [P3/D3].
2. #UFB-0047 - profile link cards [P3/D3].
3. #UFB-0048 - song identification [P3/D3]; opt-in, uses the metadata store.
4. #BUG-0062 - smarter preview frame.
5. #BUG-0034 - configurable rewrite rules.

**Done when:** the bot can be used from any chat and profile links produce a card.

## 6. Later / scale

1. #UFB-0043 - persistent work queue [P3/D4]; the hand-off the split needs.
2. #UFB-0044 - receiver / downloader / messenger split [P3/D4]; only if one process becomes the limit after epic 1.

**Done when:** a container restart no longer drops in-flight requests.

Anytime: #BUG-0078 (the `markdownfmt` hook install failure) and #BUG-0051 (import-time side effects in tests).
