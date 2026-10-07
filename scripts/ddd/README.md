# `ddd` - DDD bookkeeping

Stdlib Python 3, no dependencies, no database, no network. Reads `docs/` only, so it runs in CI and inside a subagent whether or not the HyperMnesia store is up.

```sh
./scripts/ddd/ddd help [COMMAND]             # examples for everything, or one command
./scripts/ddd/ddd check                      # verify; writes nothing; exit 1 on any error
./scripts/ddd/ddd roadmap                    # epic progress and what is next
./scripts/ddd/ddd show BUG-0002              # one item: details, position, references
./scripts/ddd/ddd close BUG-0002             # do the close-out across every file at once
./scripts/ddd/ddd brief BUG-0070 BUG-0002    # extract a self-contained work packet
make ddd                                     # same as `check`
```

## For agents

Query, don't read. These keep context small:

- `ddd check --summary` - the gate: one line, exit 1 on error. Follow up with `--only <rule>` for detail.
- `ddd show --view short ID...` - triage; escalate to `details`/`files` only for the item being worked.
- `ddd brief ID... --out build/brief.md` - hand a subagent a ~3 KB packet instead of the trackers.
- Run `check` once per change set; it writes nothing.

## Prefixes

`BUG-` and `TODO-` are fixed by the spec. The feature prefix (`CAL`, `GWS`, `MDV`, ...) is per-project and is detected, not configured: from `Next free ID:` in `docs/FRD.md`, else from the `docs/features/<PREFIX>-NNNN-*.md` filenames. While FRD.md still holds the `<PREFIX>` placeholder there is no feature prefix and only tracker IDs are recognised.

## Why

[`docs/DOCS-DRIVEN-DEVELOPMENT.md`](../../docs/DOCS-DRIVEN-DEVELOPMENT.md) makes several rules that span files and must hold in one commit - "closing a `BUGS.md` entry -> delete its `ROADMAP.md` line", "status change -> update `FRD.md`", "the link goes both ways". Those are mechanical, so they are checked here rather than remembered. Anything needing judgement - whether a Behavior section is any good - stays with the reviewer.

`check` is also how a coordinating agent verifies a doc change without re-reading four files: it reads a pass/fail instead.

## `check`

| Rule                              | Level | What it catches                                                                          |
|-----------------------------------|-------|------------------------------------------------------------------------------------------|
| `next-free-id`                    | error | `Next free ID:` no longer past every ID in use                                           |
| `duplicate-id`                    | error | an ID defined twice - the spec says IDs are never reused                                 |
| `roadmap-dangling`                | error | ROADMAP.md cites an item no tracker or FRD defines - a half-done close-out               |
| `status-mismatch`                 | error | FRD.md's `[X]`/`[ ]` disagrees with the feature doc's `## Status`                        |
| `status-invalid`                  | error | a `## Status` that is not Planned/Implemented/Deprecated                                 |
| `frd-missing` / `frd-broken-link` | error | a feature doc not indexed, or an index row pointing nowhere                              |
| `feature-sections`                | error | a required section (User Story, Behavior, Testing, Status) absent                        |
| `ux-backlink` / `ux-broken-link`  | error | a feature->page link the page's `**Features:**` does not return                          |
| `broken-link`                     | error | a relative link inside `docs/` that resolves to nothing                                  |
| `check-crashed`                   | error | a check itself raised - never silently skipped                                           |
| `priority-marker`                 | warn  | a `BUGS.md` entry with no trailing `[P#/D#]`                                             |
| `roadmap-uncovered`               | warn  | a P1 bug on no roadmap line                                                              |
| `roadmap-priority`                | warn  | an item under a `**P1 - ...**` heading whose `BUGS.md` marker says otherwise             |
| `status-qualifier`                | warn  | a Status carrying prose beyond the keyword                                               |
| `tag-index`                       | warn  | FRD.md's hand-maintained tag index drifted                                               |
| `ux-index`                        | warn  | a page or module missing from `docs/ux/README.md`                                        |
| `bare-id`                         | warn  | a bare `#<PREFIX>-NNNN` inside `docs/features/` or `docs/ux/`, where a link is available |
| `seed-stale`                      | warn  | `deploy/hypermnesia-seed.sql` describes a *closed* item as open - see below              |

`--only rule,rule` narrows the report; `--quiet` drops warnings; `--summary` prints a single line of counts per rule; `--max N` prints N findings then a count of the rest. Exit is 1 if any error, 0 otherwise, so warnings never fail CI.

Every command carries its own worked examples: `ddd help close` (or `ddd close --help`). Bare `ddd` prints the top-level help rather than an argparse error. Prefer `ddd help` for day-to-day use - this file is the reference for *why* each rule exists, the help is the reference for how to run it.

## `show`

Looks up any `BUG-`, `TODO-` or feature ID and renders it at one of three depths. Takes several IDs at once.

| View                         | Shows                                                                                                                                            |
|------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------|
| `--view short`               | one line per item: ID, `[P#/D#]`, summary, truncated to the terminal                                                                             |
| `--view details` *(default)* | full entry text wrapped, section, source line, roadmap position and state, and the other IDs it mentions                                         |
| `--view files`               | the one-line header, then **cited code** (each path checked against the tree, `MISSING` if it moved) and **referenced in docs**, grouped by file |
| `--view all`                 | `details` + `files`                                                                                                                              |

A feature ID renders from its feature doc instead: title, status, tags, sections, and the UX pages/modules it drives.

`files` is the close-out view - it answers "what do I have to touch when this closes", so it groups by file rather than listing every line, and marks `deploy/hypermnesia-seed.sql` when the seed is among them.

Markdown link syntax is flattened for the terminal, so `[GWS-0014](...md)` reads as `GWS-0014`. `brief` writes a Markdown file and keeps the links.

`DOCS-DRIVEN-DEVELOPMENT.md` is excluded from references: its templates use `BUG-0001`/`CAL-0001` as placeholders, which would otherwise match real items by coincidence.

## `roadmap`

Epic progress with a bar per epic, then the next few open items of the first unfinished epic, grouped under the roadmap's own `**P1 - ...**` headings and annotated with each item's `[P#/D#]` from `BUGS.md`.

```sh
ddd roadmap              # summary + next 5
ddd roadmap --next 10    # summary + next 10
ddd roadmap --epic 4     # one epic in full, with its Done when:
```

Two item forms are understood. A `- [X]`/`- [ ]` checkbox (epics 1-3, 5, 6) is authoritative. A bare `N.` numbered entry (epic 4) has no mark, so its state is derived: done once every ID it cites has left `BUGS.md`/`TODO.md` or is Implemented in `FRD.md`. That means `ddd close` alone moves the bar - there is no second place to tick.

Only the citation zone of a line counts, the same rule `close` uses, so `- ... found alongside #CAL-0032` in the trailing prose never reads as an item.

## `close`

Does every mechanical part of closing one item, atomically:

1. deletes the entry from `BUGS.md` / `TODO.md`;
2. removes it from `ROADMAP.md` - deleting the line if it was the only item cited, otherwise removing just that citation and keeping the rest;
3. adds a `## Unreleased` CHANGELOG line, with `--changelog "..."`;
4. **flags** - never edits - a `deploy/hypermnesia-seed.sql` rule citing it.

Only the *citation zone* of a roadmap line (everything before the first `-`) is rewritten, so a cross-reference in the trailing prose survives. Numbered lists are not renumbered; the tool says so when it leaves a gap.

It does not touch the feature doc's `## Status` or `FRD.md` - closing a bug usually is not a status change, and when it is, the wording is yours. Run `check` afterwards.

`--dry-run` prints the plan and writes nothing. It never commits (see `CLAUDE.md`).

## `brief`

Extracts one or more items into a standalone packet: full entry text, the `file:line` pointers already written into `BUGS.md` (checked against the tree, so a stale path is marked), the working rules, and the HyperMnesia note below. Roughly 3 KB for two bugs against 28 KB for all of `BUGS.md` - the point is that a fresh agent can start without reading the whole tracker.

`--out build/brief-lane-b.md` writes to a file; build artifacts belong under `build/`.

**Open items only.** Closing an item deletes its tracker entry, so a closed ID has no text left to brief from and the command refuses the whole batch rather than silently briefing a subset. `CHANGELOG.md` and `git log -S<ID> -- docs/BUGS.md` are the record of a closed item; the error says so.

## The HyperMnesia seed is a close-out artifact

`deploy/hypermnesia-seed.sql` maps paths -> components -> `must` constraints, and its own header says several of those rules describe *currently-open* defects on purpose, so the `PreToolUse` hook surfaces them when someone edits that code. Correct while the bug is open; wrong the moment it closes, and the hook keeps injecting it either way.

The file distinguishes the two kinds of citation, and the tooling relies on it:

| Form                  | Means                                                       | Goes stale on close?          |
|-----------------------|-------------------------------------------------------------|-------------------------------|
| `Open #BUG-0002: ...` | this rule describes a defect that is open right now         | yes - `seed-stale` flags it   |
| `(#BUG-0057)`         | historical provenance: the incident that justifies the rule | no - still true after the fix |

So "hand-rolled JSON broke the calendar-delete dialog once (#BUG-0057)" stays as written forever, while an `Open` marker is a promise that expires. Keep using both forms deliberately.

After closing an item, check whether the seed describes it as open, reword the rule, and re-seed -

```sh
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f deploy/hypermnesia-seed.sql
```

`check`'s `seed-stale` rule and `close`'s flag both exist to make that step hard to forget. `close` flags *any* citation, `Open` or not, since a fix may have invalidated the provenance too - it never edits the seed, because that call needs a human.

## Adding a check

Write a function in `checks.py` taking a `Corpus` and returning `list[Finding]`, then add it to `ALL_CHECKS`. A check that raises is reported as `check-crashed` rather than taking the run down, so one bad rule cannot hide the other thirteen. Parsing lives in `model.py` and is deliberately forgiving - an unrecognised line yields no entry instead of an exception.
