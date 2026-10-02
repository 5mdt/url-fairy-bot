# UFB-0055. Progress chat action

**Tags:** #telegram #ux

## User Story

As a Telegram user, I want to see "typing…" or "sending a video…" as soon as I post a link, so that I know the bot is working on it instead of ignoring me.

## Behavior

While the bot processes a link, the chat shows a Telegram chat action. It leaves no message behind, so there is nothing to edit or delete afterwards.

| Phase                                                                 | Chat action    |
|-----------------------------------------------------------------------|----------------|
| Resolving the URL and downloading                                     | `typing`       |
| Sending a native video ([UFB-0036](UFB-0036-native-video-replies.md)) | `upload_video` |

Telegram clears a chat action after about 5 seconds or when the bot sends a message, so the bot re-sends it every few seconds until the reply is out. It stops on success and on failure, and a cache hit that replies immediately never shows it.

## Implementation

- A background task that calls `send_chat_action` on an interval, started when a URL is accepted and cancelled in a `finally` once the reply is sent or fails.
- The refresh task only runs if the event loop is free. Today `ydl.download()` blocks it (#BUG-0006), so that bug has to be fixed first or the indicator would freeze during the download.

## Quirks & Decisions

- Quirk: the bot is kept quiet in group chats ([UFB-0004](UFB-0004-group-chat-quietness.md)).
  Decided: the indicator shows in group chats too, but only for a link the bot has decided to reply to. A link it stays quiet about shows nothing.
- Quirk: the action has to stop when processing fails.
  Proposed: always cancel the refresh task in a `finally`.
- Quirk: a link that resolves to nothing to do (disallowed, invalid) would flash the indicator for no reason.
  Proposed: start it only after the URL passes validation.

## Testing

### Human

- Send a slow link in a private chat. "typing…" appears right away and stays until the reply arrives, switching to "sending a video…" for the upload.
- Send an invalid link. No indicator appears.
- In a group chat, post a link the bot replies to. The indicator shows. Post one it stays quiet about ([UFB-0004](UFB-0004-group-chat-quietness.md)). Nothing shows.

### Unit

- The refresh task re-sends on its interval and is cancelled when the reply finishes or raises.

### Integration

- A failing download still cancels the task and does not leave it running.

## Status

Planned
