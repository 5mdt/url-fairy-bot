# Docs-Driven Development Approach

## Glossary

- **Feature** – a user-visible behavior. One feature = one document.
- **FRD** – index of all features.
- **Todo** – ideas not yet promoted to features.

## Rules

- Docs → Tests → Code.
- Docs define behavior.
- Keep docs short: describe behavior and implementation, omit design rationale.
- Edit only what changed; omit unused sections.
- Changed behavior edits the existing document. New behavior gets a new ID.

## Directory layout

```text
docs/
  FRD.md
  todo.md
  CHANGELOG.md
  features/
    TEMPLATE.md
    EXAMPLE.md
    <PREFIX>-NNNN-slug.md
```

- `<PREFIX>` = project code.
- IDs are sequential and never reused.

## Workflow

1. Create a feature doc.
2. Add it to `FRD.md`.
3. Write tests.
4. Implement.
5. Update status.
6. If implemented or deprecated, add a changelog entry.

## FRD.md template

```markdown
# Feature Requirements Document

## Available Features

- [<PREFIX>-0001. <Feature Name>](features/<PREFIX>-0001-slug.md) - `#tag1` `#tag2`

## Tags

- `#tag1`: <PREFIX>-0001, <PREFIX>-0003
- `#tag2`: <PREFIX>-0001
```

Tags are for cross-feature navigation only - use them to group related features.

## Feature document template (`docs/features/TEMPLATE.md`)

```markdown
# ABC-0001. Feature name

**Tags:** #tag1 #tag2

## Behavior

## Implementation

## Testing

## Status
```

Omit sections that don't apply. Status is one of: `Planned`, `Implemented`, `Deprecated`.

## Feature document example (`docs/features/EXAMPLE.md`)

```markdown
# GWS-0008. Single-instance enforcement

**Tags:** #process

## Behavior

Starting a second instance replaces the running one. The new instance always
continues startup.

## Implementation

- Read the pidfile.
- Ignore missing, invalid, or foreign PIDs.
- Send `SIGTERM` to the existing instance.
- Wait up to 5 seconds for exit.
- Continue startup regardless.

The existing instance exits on `SIGTERM`.

## Testing

### Human

- Start two instances. The first exits, the second keeps running.
- Verify the pidfile contains the second instance's PID.
- Stop the first instance with `SIGSTOP`. The second starts after ~5 seconds.

### Unit

- Missing or invalid pidfile.
- Pidfile points to another executable.
- Pidfile contains the current process PID.

### Integration

- Starting two instances leaves only the second running.
- An unresponsive first instance does not block startup.

## Status

Implemented
```

## todo.md template

```markdown
# Features to add

- <one-line idea>
```

Remove the line once promoted to a feature doc.

## CHANGELOG.md template

```markdown
# Changelog

## Unreleased

- <PREFIX>-NNNN: <one-line summary>

## <YYYY-MM-DD or version>

- <PREFIX>-NNNN: <one-line summary>
```

Rules:

- Newest releases first; within `## Unreleased`, newest entries first.
- One line per feature - the feature document has the details.
- On release, rename `## Unreleased` to the version/date and start a new
  `## Unreleased` section above it.

## Adopting this approach

1. Create the directory structure above, with empty `FRD.md`, `todo.md`, and
   `CHANGELOG.md`, and `TEMPLATE.md`/`EXAMPLE.md` copied into `features/`.
2. Add the Rules section to your project's `CLAUDE.md` or `AGENTS.md`.
3. Choose a project prefix and start numbering at `0001`.

## Known trade-offs

- `FRD.md` and its tag index are maintained manually.
- Sequential IDs are stable references but don't provide thematic grouping.
- Best suited to projects with roughly dozens - not hundreds - of features.
