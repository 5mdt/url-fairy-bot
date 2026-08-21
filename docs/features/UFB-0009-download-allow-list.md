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

Implemented. Matching used to be a raw string-suffix check with no
domain-boundary or whitespace handling (`tiktok.com` also matched
`evil-tiktok.com`, a trailing comma made every domain match, and untrimmed
whitespace could silently exclude an intended entry); fixed by trimming and
lower-casing each allow-list entry, dropping empties, and requiring an exact
or label-boundary (`.`-prefixed subdomain) match
([BUGS #5](../BUGS.md#5-domain-allow-list-can-be-bypassed-or-trivially-disabled-medium-p1d2),
fixed 2026-08-21).
