# UFB-0044. Receiver / downloader / messenger split

**Tags:** #runtime #ops

## User Story

As a bot operator, I want the receiver, downloader and messenger to run as separate components, so that I can scale and restart each one independently.

## Behavior

| Component  | Job                                          |
|------------|----------------------------------------------|
| Receiver   | Gets updates from Telegram and enqueues work |
| Downloader | Takes jobs, downloads and caches the media   |
| Messenger  | Sends the replies back to Telegram           |

All three run in one process today ([UFB-0020](UFB-0020-in-process-bot-polling.md)) and downloads block inline.

## Implementation

- The hand-off between components is the queue from [UFB-0043](UFB-0043-persistent-work-queue.md), so that feature comes first.
- The components share the cache volume, which the downloader writes and the file server and messenger read ([UFB-0016](UFB-0016-download-caching.md)).

## Quirks & Decisions

- Quirk: the component boundaries are not drawn yet. Open: whether the messenger is separate at all, or part of the receiver.
- Quirk: the downloader and messenger must see the same cache files. Open: a shared volume, or the downloader returning a file reference only.
- Quirk: it multiplies the compose services. Open: one image with a role switch, or separate images.

## Testing

### Human

- Start the three components separately. A link sent to the bot still gets its reply.
- Stop the downloader. Requests queue up and are served when it returns.

### Unit

- Each component's entry point starts only its own responsibilities.

### Integration

- End to end with all three components and the queue: link in, native video out.

## Status

Planned
