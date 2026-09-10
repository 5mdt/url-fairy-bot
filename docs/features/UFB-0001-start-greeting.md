# UFB-0001. `/start` greeting

**Tags:** #telegram #commands

## Behavior

Sending `/start` to the bot in any chat replies with a short greeting inviting
the user to send a URL.

## Implementation

- A dedicated command handler answers `/start`, registered wherever the bot's
  message handlers are wired up (not conditionally, not only in an unused
  startup path).
- Greeting text is rendered from `app/templates/messages/en/start.html.j2`
  via `app.messages.start()` ([UFB-0037](UFB-0037-message-templates.md)).

## Testing

### Integration

- `/start` in a private chat gets the greeting reply.
- `/start` in a group chat gets the greeting reply.

## Status

Implemented
