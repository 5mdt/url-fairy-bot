# UFB-0014. HTML reply formatting

**Tags:** #telegram #ux

## User Story

As a Telegram user, I want replies formatted with clickable labeled links, so that messages are readable and special characters never break them.

## Behavior

Bot replies render as formatted HTML in Telegram: links appear as clickable labeled text (e.g. "📎 Original") rather than raw URLs. Any characters in a URL or other reply text that have special meaning in HTML are escaped so formatting never breaks or gets rejected.

## Implementation

- Replies are sent with `parse_mode=HTML`.
- Reply text is rendered from Jinja templates ([UFB-0037](UFB-0037-message-templates.md)); Jinja's autoescaping escapes `& < > "` in every interpolated URL, so no manual escaping is needed.

## Quirks & Decisions

History: Previously sent as legacy Markdown with unescaped URL interpolation, which could break the link syntax or get the message rejected outright ([BUG-0016](../BUGS.md), fixed by switching to HTML + Jinja autoescaping via UFB-0037).

## Testing

### Unit

- A URL containing `)`, `_`, `&`, or other HTML-significant characters → renders correctly as a link, message is not rejected.

## Status

Implemented
