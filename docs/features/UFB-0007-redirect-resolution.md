# UFB-0007. Redirect resolution

**Tags:** #url #redirects

## User Story

As a Telegram user, I want shortened and redirecting links resolved to their final destination, so that the bot works on the real URL.

## Behavior

Before any other processing, a submitted URL is resolved to its final destination by following HTTP redirects. If resolution fails (timeout, connection error, unreachable host, etc.), the original URL is used instead and the failure is logged — the user never sees a raw network-error message.

## Implementation

- A `HEAD` request per hop, redirects followed manually (`allow_redirects=False`) up to 10 hops, each with the configurable timeout (`FOLLOW_REDIRECT_TIMEOUT`, default 10s). Too many hops falls back to the original URL.
- Any resolution failure falls back to the original URL rather than propagating an exception.
- #BUG-0012: before the first request and again for every redirect hop, the host is resolved (`socket.getaddrinfo`) and the URL is refused if any address is private, loopback, link-local, reserved, multicast or unspecified, or if a hop is not `http`/`https`. A refused URL raises `BlockedUrlError` instead of falling back to the original URL (which would be downloaded next). The API answers `400`; the bot treats it like an invalid URL ([UFB-0006](UFB-0006-url-validation-errors.md)) in private chats and stays silent in groups. A host that does not resolve is not refused here; the request simply fails and the original URL is used.
- Quirk (accepted): the check and the request resolve the name separately, so a DNS-rebinding host could still slip through; pinning the connection to the checked address is not done.

## Quirks & Decisions

Known gap:

- Runs as a blocking call directly on the event loop ([BUGS #6](../BUGS.md#6-blocking-networkcpu-calls-run-directly-on-the-asyncio-event-loop-medium-p2d3)).

Fixed:

- Previously only `requests.Timeout` was caught, so other network failures (connection errors, unreachable hosts, SSL errors) propagated uncaught; now `requests.RequestException` is caught broadly and the original URL is returned unchanged ([BUGS #11](../BUGS.md#11-follow_redirects-only-handles-the-timeout-case-low-p3d2), fixed 2026-08-21).

## Testing

### Unit

- No redirect → same URL returned.
- One or more redirects → final URL returned.
- Timeout → original URL returned, warning logged.
- #BUG-0012: loopback, private, link-local, metadata (`169.254.169.254`), IPv4-mapped IPv6, multicast and unspecified targets are refused; a public URL redirecting to a private one is refused at that hop; a host resolving to both public and private addresses is refused; a non-http hop is refused; more than 10 hops falls back to the original URL.
- Connection error / unreachable host → original URL returned, warning logged (not just timeouts).

## Status

Implemented
