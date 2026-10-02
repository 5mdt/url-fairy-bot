# UFB-0046. Inline mode

**Tags:** #telegram #ux

## User Story

As a Telegram user, I want to type `@botname <url>` in any chat, so that I get the processed result without adding the bot to that chat.

## Behavior

An `inline_query` handler reuses `process_url_request` ([UFB-0019](UFB-0019-rest-url-processing-endpoint.md)) and answers with an inline result the user can send.

An inline query must be answered within seconds, which a real download usually can't meet. So the first answer is the mirror or text result, or a placeholder that edits in the video once it is ready.

## Implementation

- Inline mode has to be enabled in BotFather.
- Answering reuses the same rewrite and download decision tree as the chat handler.

## Quirks & Decisions

- Quirk: downloads are slower than the inline answer deadline.
  Open: text result immediately, or a placeholder that is edited when the video is ready.
- Quirk: group chats are kept quiet today ([UFB-0004](UFB-0004-group-chat-quietness.md)).
  Open: whether that quietness applies to inline use. The user chose to send, so it likely does not.

## Testing

### Human

- In an unrelated chat, type `@botname <link>` and send the result.

### Unit

- The handler maps a URL to the right inline result type.

### Integration

- A slow download still answers the inline query in time.

## Status

Planned
