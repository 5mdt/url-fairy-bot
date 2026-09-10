# UFB-0037. Jinja message templates

**Tags:** #telegram #ux #i18n

## User Story

As a maintainer, I want every reply the bot sends to live in one templated
place instead of scattered inline strings, so that copy changes don't touch
Python and every link is safely escaped.

## Behavior

Every reply text the bot or the REST endpoint returns (greeting, no-URL
prompt, invalid-URL rejection, reply-to-bot shrug, download result, too-large
notice, domain-not-allowed variants, download-failure fallback) is rendered
from a Jinja template rather than built as an inline literal or f-string.
Wording is unchanged from before this feature. Replies are sent as Telegram
HTML (`parse_mode=HTML`) instead of legacy Markdown — Jinja's autoescaping
then escapes `& < > "` in every interpolated URL automatically, which fixes
[BUG-0016](../BUGS.md): a URL containing `)` or `_` no longer breaks the
reply or gets it rejected by Telegram.

## Implementation

- `app/messages.py`: a Jinja `Environment` (`autoescape=True`,
  `trim_blocks`/`lstrip_blocks`, `StrictUndefined`) over
  `app/templates/messages/<locale>/`, separate from `app/pages.py`'s HTML-page
  environment. One thin function per message renders its template and falls
  back to the `en` locale if `MESSAGE_LOCALE` has no matching template.
- `app/templates/messages/en/*.html.j2`: one template per message.
- `app/config.py`: `MESSAGE_LOCALE` (default `"en"`).
- `app/bot.py`/`app/url_processing.py`: call the `messages.*` functions
  instead of building strings inline; all replies use
  `parse_mode=ParseMode.HTML`.

## Quirks & Decisions

- Locale-aware paths (`messages/<locale>/...`) are in place even though only
  `en` ships today — this is groundwork for translation, not a general i18n
  system (no pluralization, no per-request locale selection).

## Testing

### Unit

- Each message function renders non-empty output containing its expected
  copy.
- A URL containing `)`, `_`, `&`, `<`, `"` renders inside `href="..."`
  correctly escaped and doesn't break the surrounding tag.
- Rendering with an unknown `MESSAGE_LOCALE` falls back to `en`.
- Rendering with a missing required variable raises (`StrictUndefined`).

## Status

Implemented
