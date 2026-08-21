# UFB-0003. Private-chat no-URL prompt

**Tags:** #telegram #ux

## Behavior

In a private chat, a text message containing no URL gets a reply asking the
user to send a valid URL.

## Implementation

- Runs after [multi-URL scanning](UFB-0002-multi-url-scanning.md) finds zero
  matches, only when the chat is not a group/supergroup.

## Testing

### Unit

- Private-chat message with no URL → prompt reply.

## Status

Implemented
