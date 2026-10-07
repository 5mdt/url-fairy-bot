# UFB-0053. Multiple cookie jars

**Tags:** #cookies #download

## User Story

As a bot operator, I want several cookie sets per site, so that one burned or throttled account doesn't fail every request for that platform.

## Behavior

Instead of merging every `cookies*.txt` into a single jar ([UFB-0017](UFB-0017-cookie-file-merging.md), [UFB-0018](UFB-0018-persistent-cookie-jar.md)), the bot keeps several jars per site and picks one per request. When a download hits a login wall or a rate limit, it moves to the next jar.

The keepalive ([UFB-0038](UFB-0038-cookie-keepalive.md)) tracks health per jar and takes a dead one out of rotation. `/health` ([UFB-0034](UFB-0034-health-endpoints.md)) reports per-jar state.

## Quirks & Decisions

- Quirk: jars are all merged today, so there is no way to tell accounts apart. Open: how jars are named and mapped to sites, by file-name convention or a small config.
- Quirk: rotation strategy is undecided. Open: round-robin, or on-failure only.
- Quirk: a jar that is out of rotation has to come back. Open: when it is retried.

## Testing

### Human

- Configure two jars for one site and burn the first. Requests succeed with the second, and `/health` shows the first as unhealthy.

### Unit

- Jar selection and rotation order, including skipping a dead jar.

### Integration

- A login-wall failure on one jar retries once with the next jar.

## Status

Planned
