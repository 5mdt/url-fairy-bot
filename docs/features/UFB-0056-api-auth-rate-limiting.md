# UFB-0056. API authentication and rate limiting

**Tags:** #api #ops #config

## User Story

As a bot operator, I want `POST /process_url/` to require a key and limit how often it can be called, so that a public deployment can't be used as a free download and fetch service.

## Behavior

The REST URL-processing endpoint ([UFB-0019](UFB-0019-rest-url-processing-endpoint.md)) checks two things before doing any work:

| Check                                            | Failure                           |
|--------------------------------------------------|-----------------------------------|
| An API key in a request header matches `API_KEY` | `401`                             |
| The caller is within a per-client request rate   | `429` with a `Retry-After` header |

`/health` ([UFB-0034](UFB-0034-health-endpoints.md)) stays open. The SSRF protection (validating the URL and blocking private targets) is a separate fix, tracked in #BUG-0012, and does not depend on this feature.

## Implementation

- `API_KEY` setting, compared in constant time. A FastAPI dependency on the route, so the check runs before the body is processed.
- An in-memory rate limiter keyed by client. Behind Traefik ([UFB-0027](UFB-0027-compose-stack-traefik-routing.md)) the client address comes from the forwarded header, so it is only trusted from the proxy.

## Quirks & Decisions

- Quirk: an empty `API_KEY` could mean "no auth" or "refuse everything".
  Open: whether an unset key leaves the endpoint open, as today, or the endpoint stays disabled until a key is configured.
- Quirk: an in-memory limiter is per process and resets on restart.
  Proposed: accept that for a single container; revisit if the receiver and downloader are split ([UFB-0044](UFB-0044-component-split.md)).
- Quirk: the key is a shared secret in a header.
  Open: a single key or several, so a key can be rotated without downtime.

## Testing

### Human

- Call the endpoint without a key and with a wrong key. Both get `401`. With the right key it works.
- Exceed the rate. The next call gets `429` and a `Retry-After`.

### Unit

- Key comparison and the limiter window, including the proxy-trusted client address.

### Integration

- `/health` answers without a key while `/process_url/` requires one.

## Status

Planned
