# UFB-0001. `/start` greeting

**Tags:** #telegram #commands

## Behavior

Sending `/start` to the bot in any chat replies with a short greeting inviting
the user to send a URL.

## Implementation

- A dedicated command handler answers `/start`, registered wherever the bot's
  message handlers are wired up (not conditionally, not only in an unused
  startup path).

## Testing

### Integration

- `/start` in a private chat gets the greeting reply.
- `/start` in a group chat gets the greeting reply.

## Status

Implemented — with known gaps:

- The handler is only registered inside a function nothing calls; in the
  actual running process `/start` falls through to the generic
  no-URL-found reply instead ([BUGS #4](../BUGS.md#4-start-command-handler-is-unreachable-medium-p2d1)).
