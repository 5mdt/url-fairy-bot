# UFB-0009. Download allow-list

**Tags:** #config #download #allowlist

## Behavior

`DOWNLOAD_ALLOWED_DOMAINS` restricts which domains real media downloads (via
yt-dlp) are attempted for — nothing else. An empty value (the default) means
no restriction: every domain is eligible for download. A non-empty,
comma-separated list restricts downloads to only those domains; a domain
matches if it equals a listed domain or is a subdomain of one
(`sub.example.com` matches `example.com`, but `evil-example.com` does not).
Whitespace around list entries and empty entries are ignored. This setting
never affects whether a mirror-link alternative is offered — that is governed
independently by [`REWRITE_ALLOWED_DOMAINS`](UFB-0023-rewrite-domain-allowlist.md)
(see [UFB-0010](UFB-0010-mirror-link-disallowed-domains.md)).

## Implementation

- `DOWNLOAD_ALLOWED_DOMAINS`: comma-separated domain list; empty means
  unrestricted.
- Domain comparison is case-insensitive and `www.`-agnostic.

## Testing

### Unit

- Exact domain match, subdomain match.
- Lookalike domain sharing a suffix (`evil-example.com` vs. `example.com`) →
  not allowed.
- List entry with surrounding whitespace → matches as if trimmed.
- Trailing comma / empty entry → does not affect other entries.
- Empty list → every domain allowed (default).
- Non-empty list → only listed domains (and their subdomains) allowed.

## Status

Implemented. Matching used to be a raw string-suffix check with no
domain-boundary or whitespace handling (`tiktok.com` also matched
`evil-tiktok.com`, a trailing comma made every domain match, and untrimmed
whitespace could silently exclude an intended entry); fixed by trimming and
lower-casing each allow-list entry, dropping empties, and requiring an exact
or label-boundary (`.`-prefixed subdomain) match
([BUGS #5](../BUGS.md#5-domain-allow-list-can-be-bypassed-or-trivially-disabled-medium-p1d2),
fixed 2026-08-21).

Changed:

- An empty allow-list used to deny every domain (downloads were opt-in by
  domain); it now allows every domain (downloads are unrestricted by
  default, and an operator opts into *restricting* them instead). This
  matches the semantics of the new
  [`REWRITE_ALLOWED_DOMAINS`](UFB-0023-rewrite-domain-allowlist.md) and
  makes "empty list = no restriction" consistent across both settings
  (2026-08-22).
