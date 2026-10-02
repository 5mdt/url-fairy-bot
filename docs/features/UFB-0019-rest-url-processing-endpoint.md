# UFB-0019. REST URL-processing endpoint

**Tags:** #api

## User Story

As an API client, I want to POST a URL and get the processed result, so that I can use the bot's logic outside Telegram.

## Behavior

An HTTP API exposes the same URL-processing logic used by the Telegram bot: a client `POST`s a URL and gets back the processed result (download link, mirror link, or explanation), or a client-facing error if processing fails. The submitted value is validated as a well-formed URL before any network request is made from it, and failure responses never leak internal error detail.

## Implementation

- `POST /process_url/` with JSON body `{"url": "..."}`.
- Delegates to the same processing used by [message handling](../flows/message-handling-flow.md); always behaves as a non-group request.
- Success: `{"status": "success", "data": "<reply text>"}`.
- Failure: an HTTP error response with a safe, generic message.

## Quirks & Decisions

Fixed:

- #BUG-0012: `url` is validated as `HttpUrl` (malformed input gets `422` before any outbound request), and redirect resolution refuses private, loopback, link-local, reserved, multicast and unspecified targets, including via redirects ([UFB-0007](UFB-0007-redirect-resolution.md)); a refused target gets a `400` with a generic message. Authentication and rate limiting are [UFB-0056](UFB-0056-api-auth-rate-limiting.md).

Known gaps:

- On failure, the raw exception message (e.g. DNS errors, internal paths) is returned as the HTTP error detail ([BUGS #11](../BUGS.md#11-follow_redirects-only-handles-the-timeout-case-low-p3d2)).

## Testing

### Integration

- Valid URL → 200 with the processed reply text.
- A target resolving to a private/loopback address → 400, no request sent.
- Malformed input → 4xx before any outbound request is made.
- A processing failure → error response with no internal exception detail.

## Status

Implemented
