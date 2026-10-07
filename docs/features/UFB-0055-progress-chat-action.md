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

- `ChatActionIndicator` (`app/bot.py`): a background task that calls `send_chat_action` every `CHAT_ACTION_INTERVAL_SECONDS` (4 s) with its current `action`. `handle_message` starts it per URL and cancels it in a `finally`; a failed send is logged and never breaks the reply.
- The first send waits `CHAT_ACTION_START_DELAY_SECONDS` (0.5 s), so a cache hit that replies at once never shows it, yet a slow link shows it well within a second.
- Private chats: started right after URL validation, so redirect resolution is covered. Group chats: started by an `on_download` callback that `process_url_request` calls once the link passed the domain check and a download is about to be attempted, so links the bot answers or ignores at once ([UFB-0004](UFB-0004-group-chat-quietness.md)) show nothing.
- `_reply_with_video` switches the action to `upload_video` before the native send.
- The refresh task only runs if the event loop is free, which holds since the blocking calls run in worker threads (#BUG-0006, fixed).

## Quirks & Decisions

- Quirk: the bot is kept quiet in group chats ([UFB-0004](UFB-0004-group-chat-quietness.md)). Decided: the indicator shows in group chats too, but only for a link the bot has decided to reply to. A link it stays quiet about shows nothing. Known limit: whether a download failure ends in silence is only known after the attempt, so the indicator can show during a download that then ends quietly.
- Quirk: the action has to stop when processing fails. Proposed: always cancel the refresh task in a `finally`.
- Quirk: a link that resolves to nothing to do (disallowed, invalid) would flash the indicator for no reason. Proposed: start it only after the URL passes validation.

## Testing

### Human

- Send a slow link in a private chat. "typing…" appears right away and stays until the reply arrives, switching to "sending a video…" for the upload.
- Send an invalid link. No indicator appears.
- In a group chat, post a link the bot replies to. The indicator shows. Post one it stays quiet about ([UFB-0004](UFB-0004-group-chat-quietness.md)). Nothing shows.

### Unit

- The refresh task re-sends on its interval, honours the start delay, picks up an `action` change, survives a failing send, and is cancelled by `stop()`.
- `handle_message` starts it for a private link and not for an invalid one; in a group it starts only through `on_download`.

### Integration

- A failing download still cancels the task and does not leave it running.
- A native video send switches the action to `upload_video`.

## Status

Implemented
