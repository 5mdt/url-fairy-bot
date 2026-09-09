# Docs-Driven Development Approach

**Version:** 1.1 · **Last updated:** 2026-09-02

<!-- Bump both whenever this document's rules or templates change. -->

## Glossary

- **Feature** – a user-visible behavior. One feature = one document.
- **FRD** – index of all features.
- **Todo** – ideas not yet promoted to features.
- **Bug** – a defect or debt item in shipped behavior; not a feature.

## Rules

- Docs → Tests → Code.
- Docs define behavior.
- Keep docs short: describe behavior and implementation, omit design rationale.
- Edit only what changed; omit unused sections.
- Changed behavior edits the existing document. New behavior gets a new ID.
- Log any quirk, bug, or open question the moment you notice it — as a `TODO.md`
  or `BUGS.md` line — regardless of what you're currently working on. Don't defer
  it until the current task is done.
- Reference an ID as `#<PREFIX>-NNNN` in commit messages, code comments, and
  prose mentions that aren't linking to the doc itself (e.g. `paging #MDV-0018`).
  When linking to the feature doc from within `docs/`, use a real Markdown link
  (`[<PREFIX>-NNNN](<PREFIX>-NNNN-slug.md)`), not a bare mention.

## Directory layout

```text
docs/
  FRD.md
  TODO.md
  BUGS.md
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

Steps 1–6 are for a specific feature. Logging a quirk or bug to `BUGS.md` (or an idea
to `TODO.md`) happens continuously alongside this workflow, whenever one turns up —
see Rules above.

## FRD.md template

```markdown
# Feature Requirements Document

## Available Features

- [x] [<PREFIX>-0001. <Feature Name>](features/<PREFIX>-0001-slug.md) - `#tag1` `#tag2`
- [ ] [<PREFIX>-0002. <Feature Name>](features/<PREFIX>-0002-slug.md) - `#tag2`

## Tags

- `#tag1`: <PREFIX>-0001, <PREFIX>-0003
- `#tag2`: <PREFIX>-0001
```

`[x]` = `Implemented`, `[ ]` = `Planned` or `Deprecated` — the checkbox mirrors the
feature doc's own `## Status`, so it stays in sync when status changes.

Tags are for cross-feature navigation only - use them to group related features.

## Feature document template (`docs/features/TEMPLATE.md`)

```markdown
# ABC-0001. Feature name

**Tags:** #tag1 #tag2

## User Story

## Behavior

## Implementation

## Quirks & Decisions

## Testing

## Status
```

`## User Story` is one sentence: "As a `<role>`, I want `<goal>`, so that `<benefit>`."
The role is whoever directly experiences the behavior — a terminal user, a script
piping input, a contributor writing a plugin — not "the system".

`## Quirks & Decisions` lists every accidental or debatable behavior found while
writing the doc, each as either `- Quirk: <what happens and why it's off>` followed by
`Proposed: <concrete target behavior>`, or `- Quirk: <what happens>` followed by
`Open: <the design question that needs an answer>`.

Omit sections that don't apply. Status is one of: `Planned`, `Implemented`, `Deprecated`.

## Feature document example (`docs/features/EXAMPLE.md`)

```markdown
# GWS-0008. Single-instance enforcement

**Tags:** #process

## User Story

As an operator starting the service, I want a second launch to replace the running
instance instead of failing or running alongside it, so that I never end up with two
instances silently competing.

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

## TODO.md template

```markdown
# Features to add

- <one-line idea>
```

Remove the line once promoted to a feature doc.

## BUGS.md template

```markdown
# Bugs & debt

## Bugs & quirks

- <feature ID>: <one-line defect>

## Tech debt

- <one-line debt item>

## Chores

- <one-line chore>
```

Defects, quirks, tech debt, and chores on already-shipped behavior go here, not in
`TODO.md` (new behavior only).

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

1. Create the directory structure above, with empty `FRD.md`, `TODO.md`, and
   `CHANGELOG.md`, and `TEMPLATE.md`/`EXAMPLE.md` copied into `features/`.
2. Add the Rules section to your project's `CLAUDE.md` or `AGENTS.md`.
3. Choose a project prefix and start numbering at `0001`.

## Known trade-offs

- `FRD.md` and its tag index are maintained manually.
- Sequential IDs are stable references but don't provide thematic grouping.
- Best suited to projects with roughly dozens - not hundreds - of features.
