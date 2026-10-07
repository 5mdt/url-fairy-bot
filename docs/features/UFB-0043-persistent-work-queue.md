# UFB-0043. Persistent work queue

**Tags:** #runtime #ops

## User Story

As a bot operator, I want pending and in-flight requests to survive a container restart, so that a deploy doesn't silently drop what users just sent.

## Behavior

Requests go onto a queue held outside process memory. A worker takes jobs from it with a concurrency limit, and a restarted worker resumes or re-replies to whatever was not finished.

Today there is no explicit queue: updates are handled in-process by aiogram polling ([UFB-0020](UFB-0020-in-process-bot-polling.md)) and downloads run inline, so a restart drops whatever is mid-download, and a slow download has no concurrency limit or backpressure.

## Implementation

- Store options: Redis, or a SQLite file on a mounted volume.
- The head only enqueues. One or more workers consume, with a cap on simultaneous downloads and a bounded queue so a flood is rejected instead of piling up.
- This pairs with [UFB-0044](UFB-0044-component-split.md), which needs this hand-off between components.

## Quirks & Decisions

- Quirk: there is no queue shape yet. Open: one queue for everything, or separate ones for download and reply.
- Quirk: a job killed mid-download leaves a partial file. Open: resume, restart the download, or re-reply with the mirror link.
- Quirk: the store adds an operational dependency. Open: Redis (another container) versus SQLite (a file, no extra service, but one writer).

## Testing

### Human

- Send a long download, restart the container mid-way. The user still gets a reply.

### Unit

- Enqueue, dequeue, ack and requeue-on-timeout behave as specified.

### Integration

- Kill the worker with a job in flight. A fresh worker picks it up exactly once.

## Status

Planned
