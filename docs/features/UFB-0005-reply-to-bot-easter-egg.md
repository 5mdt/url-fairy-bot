# UFB-0005. Reply-to-bot easter egg

**Tags:** #telegram #groups #easter-egg

## Behavior

In a group or supergroup, replying to one of the bot's own messages gets a
shrug emoticon (`¯\_(ツ)_/¯`) back instead of URL processing, even if the
reply text contains a URL.

## Implementation

- Checked before URL extraction: group/supergroup chat, message is a reply,
  and the replied-to message's author is the bot.

## Testing

### Unit

- Group reply to the bot's message → shrug reply, regardless of content.
- Group reply to another user's message → normal URL processing.
- Private-chat reply to the bot's message → normal URL processing (the
  easter egg is group-only).

## Status

Implemented — with known gaps:

- The emoticon sent is malformed (`\_ (ツ)_/`, missing both `¯` marks and
  with a stray space) rather than `¯\_(ツ)_/¯`
  ([BUGS #25](../BUGS.md#25-the-reply-to-bot-shrug-is-malformed-low-p3d1)).
- Sent with legacy Markdown parsing, which can fail to render or reject the
  message depending on surrounding characters
  ([BUGS #16](../BUGS.md#16-markdown-replies-can-break-telegrams-parser-low-p2d2)).
