# UFB-0004. Group-chat quietness

**Tags:** #telegram #groups

## Behavior

In a group or supergroup, the bot never sends a reply that carries no useful
information: a message with no URL is ignored, and a processed URL that has
nothing to add over the original (no allowed download, no mirror rewrite
available) produces no reply. Only genuinely useful responses — a
successful download link, or a mirror link that differs from the original —
are sent to the group.

## Implementation

- Chat type (`group`/`supergroup` vs. private) is passed through from the
  message handler into [URL processing](../flows/url-processing-flow.md),
  which returns no reply text for the "nothing to add" cases when the flag is
  set.

## Testing

### Unit

- Group message with no URL → no reply.
- Group message with a URL that has no allowed download and no mirror
  rewrite → no reply.
- Group message with a URL that does have a mirror rewrite → reply sent.

## Status

Implemented
