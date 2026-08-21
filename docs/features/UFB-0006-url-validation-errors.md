# UFB-0006. URL validation errors

**Tags:** #telegram #validation

## Behavior

A URL extracted from a message that isn't actually a well-formed, valid URL
gets a short, user-friendly rejection reply. Internal validation-library
error details are never shown to the user.

## Implementation

- Each extracted URL is validated before processing; a validation failure is
  logged with full detail and answered with a fixed, short message.

## Testing

### Unit

- A malformed extracted URL → generic rejection reply, no internal error
  detail in the reply text.

## Status

Implemented — with known gaps:

- The reply currently embeds the raw validation-library exception text,
  including internal detail and a documentation URL, instead of a short fixed
  message ([BUGS #27](../BUGS.md#27-raw-pydantic-validationerror-text-is-replied-to-the-user-low-p3d1)).
