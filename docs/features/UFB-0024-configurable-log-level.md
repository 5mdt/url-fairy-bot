# UFB-0024. Configurable log level

**Tags:** #config #ops

## User Story

As an operator, I want to set the log verbosity, so that I can debug in development and keep logs quiet in production.

## Behavior

The application's logging verbosity is operator-configurable. An unrecognized value is rejected at startup with a clear error rather than crashing later or being silently ignored.

## Implementation

- `LOG_LEVEL` (default `INFO`): one of `DEBUG`, `INFO`, `WARNING`, `ERROR`.

## Quirks & Decisions

Known gaps:

- `LOG_LEVEL` isn't validated against the documented set; an unrecognized value reaches the logging setup call directly and fails there with a generic error instead of a clear startup-configuration message (new `TODO.md` item).

## Testing

### Unit

- Each documented level → logging configured at that level.
- An unrecognized value → startup fails with a clear error.

## Status

Implemented
