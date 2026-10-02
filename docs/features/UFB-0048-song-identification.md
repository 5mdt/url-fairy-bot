# UFB-0048. Song identification

**Tags:** #media #ux

## User Story

As a Telegram user, I want to know which song plays in a video, so that I can find and listen to it.

## Behavior

The reply and watch page get a title, an artist and a link for the music in a downloaded video.

| Step           | Source                                                                                                                   |
|----------------|--------------------------------------------------------------------------------------------------------------------------|
| 1. Cheap       | `track` / `artist` from yt-dlp's info dict where the platform provides them (for example TikTok). No recognition needed. |
| 2. Recognition | 10-20 s of mono audio extracted from the cached file, sent to a recognizer.                                              |

It is opt-in through a setting and on demand (a button on the reply or a `/song` command) rather than on every download, since recognition adds seconds of latency and an external dependency.

## Implementation

- Audio extraction with ffmpeg, as `app/media.py` already does for loudness ([UFB-0040](UFB-0040-near-silent-audio-normalization.md)). The recognizer runs off the event loop.
- Recognizer candidates: `shazamio` (async, easiest, unofficial, can break and sits in a terms-of-service gray area); ACRCloud or AudD (stable commercial APIs with free tiers); AcoustID/Chromaprint (open but weak on music under speech). Dejavu, audfprint and Olaf only match a self-built database, so they don't fit.
- Results are cached in the store from [UFB-0041](UFB-0041-link-metadata-store.md), so repeat requests don't pay for recognition again.

## Quirks & Decisions

- Quirk: every recognizer has a trade-off between reliability, cost and terms of service.
  Open: which one to use.
- Quirk: recognition is slow and external.
  Open: button on the reply versus a `/song` command.

## Testing

### Human

- With the setting on, press the song button on a reply to a video with known music. The title and artist appear.
- With the setting off, no button appears.

### Unit

- Info-dict `track`/`artist` extraction, and the audio-clip command line.

### Integration

- A cached recognition result is reused instead of calling the recognizer again.

## Status

Planned
