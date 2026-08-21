# UFB-0014. Markdown reply formatting

**Tags:** #telegram #ux

## Behavior

Bot replies render as formatted Markdown in Telegram: links appear as
clickable labeled text (e.g. "📎 Original") rather than raw URLs. Any
characters in a URL or other reply text that have special meaning in
Telegram's Markdown are escaped so formatting never breaks or gets rejected.

## Implementation

- Replies are sent with Markdown parsing enabled.
- URL and text content that could contain Markdown-significant characters is
  escaped before being embedded in a reply.

## Testing

### Unit

- A URL containing `)`, `_`, or other Markdown-significant characters →
  renders correctly as a link, message is not rejected.

## Status

Implemented — with known gaps:

- URLs are embedded in `[text](url)` links and other Markdown-formatted text
  without escaping; a URL containing `)` or an odd number of `_` breaks the
  surrounding Markdown or causes Telegram to reject the message outright
  ([BUGS #16](../BUGS.md#16-markdown-replies-can-break-telegrams-parser-low-p2d2)).
