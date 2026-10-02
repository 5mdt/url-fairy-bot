# UFB-0050. Duplicate link detection

**Tags:** #telegram #cache

## User Story

As a Telegram chat member, I want the bot to point at the earlier reply when someone posts the same link again, so that the chat isn't flooded with identical videos.

## Behavior

When the same link was already processed in this chat recently, the bot replies by linking the earlier reply (or re-sending the cached file) instead of repeating the download and a second full reply.

The download cache already avoids re-downloading ([UFB-0016](UFB-0016-download-caching.md)). What is missing is remembering, per chat, which message answered which URL and for how long.

## Implementation

- A small persistent store keyed by chat and normalized URL, holding the reply message ID and a timestamp. It shares groundwork with [UFB-0041](UFB-0041-link-metadata-store.md).

## Quirks & Decisions

- Quirk: there is no memory of earlier replies today.
  Open: how long the window is, for example one hour or one day.
- Quirk: group chats are kept quiet ([UFB-0004](UFB-0004-group-chat-quietness.md)).
  Open: whether duplicate detection applies there at all.
- Quirk: the earlier reply may have been deleted.
  Proposed: fall back to a normal reply.

## Testing

### Human

- Post the same link twice in one chat. The second time the bot links the first reply.

### Unit

- Window expiry, and URL normalization before lookup.

### Integration

- A deleted earlier message produces a normal full reply.

## Status

Planned
