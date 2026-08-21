# UFB-0007. Redirect resolution

**Tags:** #url #redirects

## Behavior

Before any other processing, a submitted URL is resolved to its final
destination by following HTTP redirects. If resolution fails (timeout,
connection error, unreachable host, etc.), the original URL is used instead
and the failure is logged — the user never sees a raw network-error message.

## Implementation

- A `HEAD` request follows redirects up to a configurable timeout
  (`FOLLOW_REDIRECT_TIMEOUT`, default 10s).
- Any resolution failure falls back to the original URL rather than
  propagating an exception.

## Testing

### Unit

- No redirect → same URL returned.
- One or more redirects → final URL returned.
- Timeout → original URL returned, warning logged.
- Connection error / unreachable host → original URL returned, warning
  logged (not just timeouts).

## Status

Implemented — with a known gap:

- Runs as a blocking call directly on the event loop
  ([BUGS #6](../BUGS.md#6-blocking-networkcpu-calls-run-directly-on-the-asyncio-event-loop-medium-p2d3)).

Fixed:

- Previously only `requests.Timeout` was caught, so other network failures
  (connection errors, unreachable hosts, SSL errors) propagated uncaught;
  now `requests.RequestException` is caught broadly and the original URL is
  returned unchanged
  ([BUGS #11](../BUGS.md#11-follow_redirects-only-handles-the-timeout-case-low-p3d2),
  fixed 2026-08-21).
