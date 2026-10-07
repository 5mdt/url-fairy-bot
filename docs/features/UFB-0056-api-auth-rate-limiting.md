# UFB-0056. API authentication and rate limiting

**Tags:** #api #ops #config

## User Story

As a bot operator, I want `POST /process_url/` to require a key and limit how often it can be called, so that a public deployment can't be used as a free download and fetch service.

## Behavior

The REST URL-processing endpoint ([UFB-0019](UFB-0019-rest-url-processing-endpoint.md)) checks two things before doing any work:

| Check                                                                        | Failure                           |
|------------------------------------------------------------------------------|-----------------------------------|
| The `X-API-Key` header matches one of the keys in `API_KEY`                  | `401`                             |
| The caller is within `API_RATE_LIMIT` requests per `API_RATE_WINDOW` seconds | `429` with a `Retry-After` header |

`/health` and `/healthz` ([UFB-0034](UFB-0034-health-endpoints.md)) stay open. The SSRF protection (validating the URL and blocking private targets) was #BUG-0012 and does not depend on this feature.

| Setting           | Default   | Meaning                                                                                 |
|-------------------|-----------|-----------------------------------------------------------------------------------------|
| `API_KEY`         | *(empty)* | Comma-separated list of accepted keys; empty leaves the endpoint open (startup warning) |
| `API_RATE_LIMIT`  | `30`      | Requests allowed per client per window; `0` disables rate limiting                      |
| `API_RATE_WINDOW` | `60`      | Window length in seconds                                                                |
| `TRUSTED_PROXIES` | *(empty)* | Comma-separated IPs/CIDRs of reverse proxies whose `X-Forwarded-For` is believed        |

## Implementation

- A FastAPI dependency on the `POST /process_url/` route only, so the checks run before the body is processed. The rate limit is checked first, so every request counts, including ones with a bad key (this also throttles key guessing).
- `API_KEY` is split on commas; a request passes if its key matches any entry, each compared with `hmac.compare_digest`.
- In-memory sliding-window limiter keyed by client address. `Retry-After` is the whole seconds until the client's oldest counted request leaves the window.
- Client address: the direct peer address, unless the peer is in `TRUSTED_PROXIES`; then the rightmost `X-Forwarded-For` entry that is not itself a trusted proxy (falling back to the peer). Behind Traefik ([UFB-0027](UFB-0027-compose-stack-traefik-routing.md)) set `TRUSTED_PROXIES` to the proxy's address or network.

## Quirks & Decisions

- Decided: an empty `API_KEY` leaves the endpoint open, as before this feature. A warning is logged at startup so the choice is visible. Rate limiting still applies.
- Decided: an in-memory limiter is per process and resets on restart; accepted for a single container. Revisit if the receiver and downloader are split ([UFB-0044](UFB-0044-component-split.md)).
- Decided: several keys are accepted (comma-separated), so a key can be rotated without downtime by listing old and new, then dropping the old.
- Decided: `X-Forwarded-For` is ignored unless the direct peer is in `TRUSTED_PROXIES`, so a client cannot dodge the limit by forging it.

## Testing

### Human

- Set `API_KEY=a,b`. Call the endpoint without a key and with a wrong key: both get `401`. Keys `a` and `b` both work.
- Exceed the rate. The next call gets `429` and a `Retry-After`.
- Start with `API_KEY` unset: the endpoint is open and the log shows a warning.

### Unit

- Key comparison: no header, wrong key, any of several keys, unset key.
- Limiter window: allowance, `429` + `Retry-After`, window expiry, separate clients.
- Client address: peer used by default; `X-Forwarded-For` honored only from a trusted proxy (IP and CIDR); a forged header from an untrusted peer is ignored.

### Integration

- `/health` answers without a key while `/process_url/` requires one.
- A startup warning is logged when `API_KEY` is unset.

## Status

Implemented
