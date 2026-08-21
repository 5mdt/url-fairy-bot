# UFB-0002. Multi-URL message scanning

**Tags:** #telegram #url

## Behavior

Every `http(s)://` URL in an incoming text message is extracted and processed
independently, each producing its own reply. Trailing punctuation or
enclosing brackets/quotes adjacent to a URL (e.g. a sentence ending in
`https://example.com/page.`) are not part of the URL and must not be
included.

## Implementation

- A regex scans the message text for all `http(s)://` matches.
- Each match is processed via [UFB-0007 through UFB-0013](../flows/url-processing-flow.md)
  and replied to separately.

## Testing

### Unit

- Message with zero, one, and multiple URLs.
- A URL followed immediately by sentence punctuation or a closing bracket.

## Status

Implemented. The extraction regex used to capture trailing punctuation as
part of the URL; fixed by trimming trailing `.,;:!?)]}'"` characters from
each match
([BUGS #24](../BUGS.md#24-url-extraction-captures-trailing-punctuation-and-markdown-syntax-low-p3d1),
fixed 2026-08-21).
