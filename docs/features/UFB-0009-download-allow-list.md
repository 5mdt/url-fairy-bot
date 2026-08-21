# UFB-0009. Download allow-list

**Tags:** #config #download #allowlist

## Behavior

Real media downloads (via yt-dlp) are only attempted for domains on an
operator-configured allow-list. A domain matches if it equals a listed
domain or is a subdomain of one (`sub.example.com` matches `example.com`,
but `evil-example.com` does not). Whitespace around list entries and empty
entries are ignored. An empty allow-list allows no domain (downloads are
opt-in). This gate only affects whether a download is attempted — it never
suppresses a mirror-link alternative (see
[UFB-0010](UFB-0010-mirror-link-disallowed-domains.md)).

## Implementation

- `DOWNLOAD_ALLOWED_DOMAINS`: comma-separated domain list.
- Domain comparison is case-insensitive and `www.`-agnostic.

## Testing

### Unit

- Exact domain match, subdomain match.
- Lookalike domain sharing a suffix (`evil-example.com` vs. `example.com`) →
  not allowed.
- List entry with surrounding whitespace → matches as if trimmed.
- Trailing comma / empty entry → does not allow every domain.
- Empty list → nothing allowed.

## Status

Implemented — with known gaps:

- Matching is a raw string-suffix check with no domain-boundary or
  whitespace handling: `tiktok.com` also matches `evil-tiktok.com`, a
  trailing comma makes every domain match, and untrimmed whitespace can
  silently exclude an intended entry
  ([BUGS #5](../BUGS.md#5-domain-allow-list-can-be-bypassed-or-trivially-disabled-medium-p1d2)).
