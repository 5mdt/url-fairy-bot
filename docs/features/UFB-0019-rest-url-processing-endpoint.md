# UFB-0019. REST URL-processing endpoint

**Tags:** #api

## Behavior

An HTTP API exposes the same URL-processing logic used by the Telegram bot:
a client `POST`s a URL and gets back the processed result (download link,
mirror link, or explanation), or a client-facing error if processing fails.
The submitted value is validated as a well-formed URL before any network
request is made from it, and failure responses never leak internal error
detail.

## Implementation

- `POST /process_url/` with JSON body `{"url": "..."}`.
- Delegates to the same processing used by
  [message handling](../flows/message-handling-flow.md); always behaves as
  a non-group request.
- Success: `{"status": "success", "data": "<reply text>"}`.
- Failure: an HTTP error response with a safe, generic message.

## Testing

### Integration

- Valid URL → 200 with the processed reply text.
- Malformed input → 4xx before any outbound request is made.
- A processing failure → error response with no internal exception detail.

## Status

Implemented — with known gaps:

- The request body's `url` field is untyped `str` (no URL-format
  validation), and a `HEAD` request is issued to whatever value is given —
  usable to probe internal/link-local addresses from the server
  ([BUGS #12](../BUGS.md#12-unauthenticated-api-is-an-ssrf-capable-open-proxy-lowcontextual-p2d3)).
- On failure, the raw exception message (e.g. DNS errors, internal paths) is
  returned as the HTTP error detail
  ([BUGS #11](../BUGS.md#11-follow_redirects-only-handles-the-timeout-case-low-p3d2)).
