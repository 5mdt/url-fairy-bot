#!/usr/bin/env python3
"""DDD bookkeeping for calsync. Stdlib only.

    ddd check [--fix-nothing] [--only RULE,...] [--quiet]
    ddd close BUG-0002 [--changelog "..."] [--dry-run]
    ddd brief BUG-0070 BUG-0002 ... [--out FILE]

`check` verifies the mechanical rules in docs/DOCS-DRIVEN-DEVELOPMENT.md and
writes nothing. `close` performs the close-out those rules describe across every
file that has to change together. `brief` extracts a self-contained work packet
for a set of items, so an agent can start on them without reading all of BUGS.md.

Never commits; see CLAUDE.md.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import textwrap
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from checks import ERROR, WARN, run_all  # noqa: E402
from model import Corpus, TrackerEntry, code_refs  # noqa: E402

VERSION = "2026-10-06T15:36:00Z"  # RFC 3339 date-time; bump on EVERY edit to this script (`date -u +%Y-%m-%dT%H:%M:%SZ`)

TTY = sys.stdout.isatty()
BOLD, DIM, RED, YELLOW, GREEN, RESET = (
    ("\033[1m", "\033[2m", "\033[31m", "\033[33m", "\033[32m", "\033[0m")
    if TTY
    else ("", "", "", "", "", "")
)


def find_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "docs" / "DOCS-DRIVEN-DEVELOPMENT.md").is_file():
            return p
    raise SystemExit(
        "ddd: not inside a DDD project (no docs/DOCS-DRIVEN-DEVELOPMENT.md found)"
    )


# -- check ----------------------------------------------------------------


def cmd_check(args: argparse.Namespace) -> int:
    c = Corpus(find_root(Path.cwd()))
    only = set(args.only.split(",")) if args.only else None
    findings = run_all(c, only)

    errors = [f for f in findings if f.level == ERROR]
    warns = [f for f in findings if f.level == WARN]

    shown = sorted(
        (f for f in findings if not (args.quiet and f.level == WARN)),
        key=lambda f: (f.level != ERROR, str(f.path), f.line),
    )
    total = len(c.feature_docs()) + len(c.bugs()) + len(c.todos())

    if args.summary:
        if not shown:
            print(f"{GREEN}ok{RESET} {total} items, no findings")
        else:
            counts = Counter(f.rule for f in shown)
            by_rule = ", ".join(f"{r}\u00d7{n}" for r, n in counts.most_common())
            print(f"{RED}FAIL{RESET} " if errors else f"{YELLOW}WARN{RESET} ", end="")
            print(f"{len(errors)} error(s), {len(warns)} warning(s): {by_rule}")
        return 1 if errors else 0

    limit = args.max if args.max is not None else len(shown)
    for f in shown[:limit]:
        colour = RED if f.level == ERROR else YELLOW
        try:
            loc = f.path.resolve().relative_to(c.root)
        except ValueError:
            loc = f.path
        print(
            f"{colour}{f.level}{RESET} {loc}:{f.line} {DIM}[{f.rule}]{RESET} {f.message}"
        )
    if len(shown) > limit:
        print(f"{DIM}\u2026 {len(shown) - limit} more (ddd check --only <rule>){RESET}")

    if not findings:
        print(f"{GREEN}ok{RESET} {total} items, no findings")
    else:
        print(
            f"\n{BOLD}{len(errors)} error(s), {len(warns)} warning(s){RESET} "
            f"across {total} items"
        )
    return 1 if errors else 0


# -- close ----------------------------------------------------------------


@dataclass
class Edit:
    path: Path
    summary: str
    new_text: str


def _strip_citation(head: str, ident: str) -> str:
    """Remove one item's citation from a roadmap line's citation zone.

    Handles the markdown form `[#BUG-0053](BUGS.md)` and the bare `#TODO-0022`,
    then tidies the separator the removal leaves behind.
    """
    patterns = (
        rf"\[#?{re.escape(ident)}\]\([^)]*\)",  # [#BUG-0053](BUGS.md)
        rf"#{re.escape(ident)}\b",  # #TODO-0022
        rf"\b{re.escape(ident)}\b",  # bare, last resort
    )
    for pat in patterns:
        new, n = re.subn(pat, "", head, count=1)
        if n:
            head = new
            break
    head = re.sub(r",\s*,", ",", head)
    head = re.sub(r"\s{2,}", " ", head)
    head = re.sub(r",\s*$", "", head.rstrip())
    head = re.sub(r"^(\s*(?:[-*]|\d+\.)\s*(?:\[[ Xx]\]\s*)?),\s*", r"\1", head)
    return head


def _roadmap_edit(c: Corpus, ident: str) -> tuple[Edit | None, list[str]]:
    """Drop `ident` from ROADMAP.md.

    Only the *citation zone* - everything before the line's first ` - ` - counts.
    Prose after it ("found alongside #CAL-0032") is a cross-reference, not a
    scheduling entry, and must survive.
    """
    notes: list[str] = []
    lines = c.roadmap_path.read_text(encoding="utf-8").splitlines(keepends=True)
    out: list[str] = []
    touched = False
    for raw in lines:
        line = raw.rstrip("\n")
        sep = line.find(" - ")
        head = line if sep < 0 else line[:sep]
        if not re.search(rf"\b{re.escape(ident)}\b", head):
            out.append(raw)
            continue
        touched = True
        new_head = _strip_citation(head, ident)
        remaining = [f"{a}-{b}" for a, b in c.id_re.findall(new_head)]
        if remaining:
            rebuilt = new_head + (line[sep:] if sep >= 0 else "")
            out.append(rebuilt + "\n")
            notes.append(f"kept the line, still cites {', '.join(remaining)}")
        else:
            notes.append(f"deleted the whole line: {line.strip()[:70]}")
            if re.match(r"^\s*\d+\.", line):
                notes.append(
                    "that was a numbered item - the list now skips a number; "
                    "renumber by hand if you care"
                )
    if not touched:
        return None, [f"{ident} is not cited in ROADMAP.md (nothing to delete)"]
    return Edit(c.roadmap_path, f"remove {ident}", "".join(out)), notes


def _tracker_edit(c: Corpus, entry: TrackerEntry) -> Edit:
    lines = entry.path.read_text(encoding="utf-8").splitlines(keepends=True)
    del lines[entry.line - 1 : entry.end_line]
    return Edit(entry.path, f"delete the {entry.id} entry", "".join(lines))


def _changelog_edit(c: Corpus, text: str) -> Edit:
    lines = c.changelog_path.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.strip().lower() == "## unreleased":
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            lines.insert(j, f"- {text}\n")
            return Edit(c.changelog_path, "add an Unreleased entry", "".join(lines))
    raise SystemExit("ddd: docs/CHANGELOG.md has no `## Unreleased` section to add to")


def cmd_close(args: argparse.Namespace) -> int:
    c = Corpus(find_root(Path.cwd()))
    ident = args.id.lstrip("#").upper()

    entry = c.tracker_entry(ident)
    if entry is None:
        print(f"{RED}error{RESET} {ident} is not an open entry in BUGS.md or TODO.md")
        return 1

    edits: list[Edit] = []
    notes: list[str] = []

    edits.append(_tracker_edit(c, entry))
    roadmap_edit, roadmap_notes = _roadmap_edit(c, ident)
    notes.extend(roadmap_notes)
    if roadmap_edit:
        edits.append(roadmap_edit)
    if args.changelog:
        edits.append(_changelog_edit(c, args.changelog))

    # The seed is never auto-edited: its `must` rules are hand-written English whose
    # correctness the fix may or may not have changed. Flagging is the honest move.
    seed_hits = [ln for ln, ids in c.seed_citations().items() if ident in ids]
    if seed_hits:
        notes.append(
            f"{BOLD}deploy/hypermnesia-seed.sql cites {ident} at line(s) "
            f"{', '.join(map(str, seed_hits))}{RESET} - review that `must` rule and re-seed, "
            "or the PreToolUse hook keeps injecting a rule about a closed defect"
        )

    print(f"{BOLD}close {ident}{RESET}  {DIM}{entry.text[:90]}{RESET}\n")
    for e in edits:
        print(f"  {GREEN}edit{RESET} {e.path.relative_to(c.root)} - {e.summary}")
    for n in notes:
        print(f"  {DIM}note{RESET} {n}")

    if args.dry_run:
        print(f"\n{YELLOW}dry run - nothing written{RESET}")
        return 0

    for e in edits:
        e.path.write_text(e.new_text, encoding="utf-8")
    print(
        f"\n{GREEN}written{RESET}. Now: update the feature doc's Status if this closed one, "
        f"run `make fmt`, and re-run `ddd check`."
    )
    if not args.changelog:
        print(
            f"{DIM}no --changelog given - add one by hand if this change is user-visible{RESET}"
        )
    return 0


# -- brief ----------------------------------------------------------------

BRIEF_RULES = """\
## Working rules (docs/DOCS-DRIVEN-DEVELOPMENT.md, CLAUDE.md)

- Docs -> Tests -> Code. Never the other order.
- Changed behavior edits the existing doc; new behavior gets a new ID from the
  relevant `Next free ID:` line, bumped in the same commit.
- Every top-level function/class implementing an item, and every test covering
  one, carries its `#<ID>` as a comment above it or the first docstring line.
- **Never commit.** Report the change set to the operator with a summary.
- Do not hand-edit BUGS.md / ROADMAP.md / CHANGELOG.md to close an item - report
  it done and let the parent run `scripts/ddd/ddd close <ID>`.
"""


def cmd_brief(args: argparse.Namespace) -> int:
    c = Corpus(find_root(Path.cwd()))
    idents = [i.lstrip("#").upper() for i in args.ids]

    # Closing an item deletes its tracker entry outright, so a closed ID has no text
    # left to brief from - CHANGELOG.md and git history are the only record. Say that,
    # rather than leaving "not an open entry" to be read as "no such bug".
    missing = [i for i in idents if c.tracker_entry(i) is None]
    if missing:
        known = c.known_ids()
        closed = [i for i in missing if i not in known]
        unknown = [i for i in missing if i in known]
        print(
            f"{RED}error{RESET} no open entry for: {', '.join(missing)}",
            file=sys.stderr,
        )
        if closed:
            print(
                f"  {DIM}{', '.join(closed)} appear closed - the entry is deleted on close. "
                f"Try: git log -S{closed[0]} -- docs/BUGS.md, or grep docs/CHANGELOG.md{RESET}",
                file=sys.stderr,
            )
        if unknown:
            print(
                f"  {DIM}{', '.join(unknown)} exist but are not tracker items "
                f"(a feature ID belongs in FRD.md, not BUGS.md/TODO.md){RESET}",
                file=sys.stderr,
            )
        return 1

    out: list[str] = [f"# Work packet: {', '.join(idents)}\n"]
    out.append(
        "Self-contained. Everything you need is below; you should not need to read "
        "all of `docs/BUGS.md`.\n"
    )

    all_refs: set[str] = set()
    for ident in idents:
        e = c.tracker_entry(ident)
        assert e is not None
        loc = f"{e.section}" + (f" / {e.subsection}" if e.subsection else "")
        out.append(
            f"\n## {ident}  [{e.priority or '?'}/{e.difficulty or '?'}]  ({loc})\n"
        )
        out.append(f"{e.text}\n")
        if e.code_refs:
            all_refs.update(r.split(":", 1)[0] for r in e.code_refs)
            out.append("\n**Cited code:**\n")
            out.extend(f"- `{r}`\n" for r in e.code_refs)

    if all_refs:
        out.append("\n## Files these touch\n\n")
        for r in sorted(all_refs):
            exists = "" if (c.root / r).exists() else "  (MISSING - path may be stale)"
            out.append(f"- `{r}`{exists}\n")

    seed_ids = {i for ids in c.seed_citations().values() for i in ids}
    hit = [i for i in idents if i in seed_ids]
    if hit:
        out.append(
            f"\n## HyperMnesia note\n\n`deploy/hypermnesia-seed.sql` encodes `must` rules that "
            f"describe {', '.join(hit)} as open defects, and the PreToolUse hook injects them "
            "before every edit to those components. Expect to see a rule describing the bug you "
            "are fixing. That is the seed being current, not a new requirement - do not treat it "
            "as an instruction to leave the defect in place.\n"
        )

    out.append("\n" + BRIEF_RULES)
    text = "".join(out)

    if args.out:
        dest = Path(args.out)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
        print(f"{GREEN}wrote{RESET} {dest} ({len(text)} bytes)")
    else:
        sys.stdout.write(text)
    return 0


# -- show -----------------------------------------------------------------


def _wrap(text: str, indent: str = "  ") -> str:
    width = max(48, shutil.get_terminal_size((100, 24)).columns - len(indent))
    return "\n".join(
        textwrap.fill(
            para,
            width=width,
            initial_indent=indent,
            subsequent_indent=indent,
            break_long_words=False,
            break_on_hyphens=False,
        )
        for para in re.split(r"\n\s*\n", text.strip())
        if para.strip()
    )


def _plain_md(text: str) -> str:
    """Flatten Markdown link syntax for terminal display: `[CAL-0014](...md)` -> `CAL-0014`.

    Display only. `brief` writes a Markdown file and deliberately keeps the links.
    """
    return re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)


def _position_line(c: Corpus, ident: str) -> str | None:
    pos = c.roadmap_position(ident)
    if pos is None:
        return None
    epic, item = pos
    where = f"epic {epic.number} ({epic.name})"
    if item.ordinal != "-":  # a checkbox item has no ordinal to cite
        where += f", item {item.ordinal.rstrip('.')}"
    if item.group:
        where += f", under {item.group!r}"
    state = f"{GREEN}done{RESET}" if c.item_is_done(item) else f"{YELLOW}open{RESET}"
    return f"{where} - {state}"


def _show_tracker(c: Corpus, e, view: str) -> None:
    pd = f"[{e.priority or '?'}/{e.difficulty or '?'}]"
    detail = _plain_md(PRIORITY_TRAIL.sub("", re.sub(r"\s+", " ", e.text)).strip())

    if view in ("short", "files"):
        width = max(48, shutil.get_terminal_size((100, 24)).columns - len(e.id) - 12)
        one = detail if len(detail) <= width else detail[: width - 1].rstrip() + "..."
        print(f"{BOLD}{e.id}{RESET} {DIM}{pd}{RESET}  {one}")
        return

    loc = e.section + (f" / {e.subsection}" if e.subsection else "")
    print(f"{BOLD}{e.id}{RESET} {DIM}{pd}{RESET}  {DIM}{loc}{RESET}")
    print(f"{DIM}  {e.path.name}:{e.line}{RESET}")
    pos = _position_line(c, e.id)
    if pos:
        print(f"{DIM}  roadmap:{RESET} {pos}")
    print()
    print(_wrap(detail))

    related = [
        i
        for i in dict.fromkeys(f"{a}-{b}" for a, b in c.id_re.findall(e.text))
        if i != e.id
    ]
    if related:
        print(f"\n  {DIM}mentions:{RESET} {', '.join(related)}")


def _show_feature(c: Corpus, d, view: str) -> None:
    frd = {x.id: x for x in c.frd()}.get(d.id)
    mark = ""
    if frd is not None:
        mark = f"{GREEN}[X]{RESET}" if frd.implemented else f"{YELLOW}[ ]{RESET}"

    if view in ("short", "files"):
        print(
            f"{BOLD}{d.id}{RESET} {mark} {d.title.split('.', 1)[-1].strip()} "
            f"{DIM}{' '.join(d.tags)}{RESET}"
        )
        return

    print(f"{BOLD}{d.title}{RESET} {mark}")
    print(
        f"{DIM}  {d.path.relative_to(c.root)}  -  status: {d.status}  -  "
        f"{' '.join(d.tags)}{RESET}"
    )
    pos = _position_line(c, d.id)
    if pos:
        print(f"{DIM}  roadmap:{RESET} {pos}")
    print(f"{DIM}  sections:{RESET} {', '.join(d.sections)}")
    if d.ux_links:
        print(f"{DIM}  ux:{RESET} {', '.join(Path(u).stem for u in d.ux_links)}")


def _show_files(c: Corpus, ident: str, text: str) -> None:
    refs = code_refs(text)
    print(f"\n  {BOLD}cited code{RESET}")
    if not refs:
        print(f"    {DIM}(none cited){RESET}")
    for r in refs:
        path = r.split(":", 1)[0]
        ok = (c.root / path).exists()
        flag = "" if ok else f"  {RED}MISSING{RESET}"
        print(f"    {r}{flag}")

    print(f"\n  {BOLD}referenced in docs{RESET}")
    rows = c.references(ident)
    if not rows:
        print(f"    {DIM}(nowhere){RESET}")
        return
    # Grouped by file: the question this view answers is "what do I have to touch
    # when this closes", and that is a list of files, not of lines.
    by_file: dict[str, list[int]] = {}
    for p, line, _ in rows:
        try:
            rel = str(p.resolve().relative_to(c.root))
        except ValueError:
            rel = str(p)
        by_file.setdefault(rel, []).append(line)
    width = max(len(f) for f in by_file)
    for rel, lines in by_file.items():
        nums = ", ".join(str(n) for n in lines[:8])
        if len(lines) > 8:
            nums += f", +{len(lines) - 8}"
        note = ""
        if rel.endswith("hypermnesia-seed.sql"):
            note = f"  {YELLOW}<- re-seed if reworded{RESET}"
        print(f"    {rel:<{width}}  {DIM}{nums}{RESET}{note}")


def cmd_show(args: argparse.Namespace) -> int:
    c = Corpus(find_root(Path.cwd()))
    features = {d.id: d for d in c.feature_docs()}
    rc = 0

    for n, raw in enumerate(args.ids):
        ident = raw.lstrip("#").upper()
        entry = c.tracker_entry(ident)
        doc = features.get(ident)
        if entry is None and doc is None:
            print(
                f"{RED}error{RESET} {ident}: no open tracker entry and no feature doc",
                file=sys.stderr,
            )
            if ident not in c.known_ids():
                print(
                    f"  {DIM}not defined anywhere - closed items are deleted on close; "
                    f"try git log -S{ident} -- docs/{RESET}",
                    file=sys.stderr,
                )
            rc = 1
            continue

        if n and args.view != "short":
            print()
        if entry is not None:
            _show_tracker(c, entry, args.view)
            if args.view in ("files", "all"):
                _show_files(c, ident, entry.text)
        else:
            _show_feature(c, doc, args.view)
            if args.view in ("files", "all"):
                _show_files(c, ident, doc.body)
    return rc


# -- roadmap --------------------------------------------------------------

BAR_W = 12


def _bar(done: int, total: int) -> str:
    if not TTY:
        return ""  # decoration only; the done/total count beside it says the same
    if total == 0:
        return " " * BAR_W
    filled = round(BAR_W * done / total)
    colour = GREEN if done == total else YELLOW if done else DIM
    return f"{colour}{'█' * filled}{DIM}{'░' * (BAR_W - filled)}{RESET}"


def _item_label(c: Corpus, item) -> str:
    """One line describing an item, pulled from its tracker entry when there is
    one - the roadmap's own trailing prose is about *ordering*, not the defect."""
    plain, shown = [], []
    for ident in item.ids:
        e = c.tracker_entry(ident)
        if e is None:
            plain.append(ident)
            shown.append(ident)
            continue
        pd = f"[{e.priority or '?'}/{e.difficulty or '?'}]"
        plain.append(f"{ident} {pd}")
        shown.append(f"{ident} {DIM}{pd}{RESET}")

    detail = item.text
    if len(item.ids) == 1:
        e = c.tracker_entry(item.ids[0])
        if e is not None:
            detail = PRIORITY_TRAIL.sub("", re.sub(r"\s+", " ", e.text)).strip()

    # Budget against the *visible* width: the head carries ANSI codes, so len() on
    # the coloured string would over-truncate by ~8 chars per cited ID.
    width = max(48, shutil.get_terminal_size((100, 24)).columns - 12)
    head_plain, head_shown = ", ".join(plain), ", ".join(shown)
    if len(head_plain) > width:
        keep = len(plain)
        while keep > 1 and len(", ".join(plain[:keep])) + 8 > width:
            keep -= 1
        extra = len(plain) - keep
        head_shown = ", ".join(shown[:keep]) + (
            f"{DIM} +{extra} more{RESET}" if extra else ""
        )
        head_plain = ", ".join(plain[:keep]) + (f" +{extra} more" if extra else "")
    if not detail:
        return head_shown
    budget = width - len(head_plain) - 2
    if budget < 12:
        return head_shown
    if len(detail) > budget:
        detail = detail[: budget - 1].rstrip() + "..."
    return f"{head_shown}  {detail}"


PRIORITY_TRAIL = re.compile(r"\s*\[P[1-3]/D[1-4]\]\s*$")


def cmd_roadmap(args: argparse.Namespace) -> int:
    c = Corpus(find_root(Path.cwd()))
    epics = c.roadmap_epics()
    if not epics:
        print("ddd: no epics found (docs/ROADMAP.md missing or has none)")
        return 1

    if args.epic is not None:
        sel = [e for e in epics if e.number == args.epic]
        if not sel:
            print(
                f"{RED}error{RESET} no epic {args.epic} in ROADMAP.md", file=sys.stderr
            )
            return 1
        epic = sel[0]
        done = sum(c.item_is_done(i) for i in epic.items)
        print(
            f"{BOLD}Epic {epic.number}. {epic.name}{RESET}  "
            f"{done}/{len(epic.items)} {_bar(done, len(epic.items))}\n"
        )
        group = object()
        for item in epic.items:
            if item.group != group:
                group = item.group
                if group:
                    print(f"  {BOLD}{group}{RESET}")
            tick = f"{GREEN}✓{RESET}" if c.item_is_done(item) else " "
            print(f"   {tick} {item.ordinal:>3} {_item_label(c, item)}")
        if epic.done_when:
            print(f"\n  {DIM}Done when:{RESET} {epic.done_when}")
        return 0

    width = max(len(e.name) for e in epics)
    current = None
    for e in epics:
        done = sum(c.item_is_done(i) for i in e.items)
        total = len(e.items)
        if current is None and done < total:
            current = e
        flag = f"  {YELLOW}<- current{RESET}" if current is e else ""
        print(
            f"  {e.number}  {e.name:<{width}}  {done:>2}/{total:<2} {_bar(done, total)}{flag}"
        )

    if current is None:
        print(f"\n{GREEN}every roadmap item is done{RESET}")
        return 0

    todo = [i for i in current.items if not c.item_is_done(i)]
    print(f"\n{BOLD}next in epic {current.number} ({current.name}){RESET}")
    group = object()
    for item in todo[: args.next]:
        if item.group != group:
            group = item.group
            if group:
                print(f"  {DIM}{group}{RESET}")
        print(f"   {item.ordinal:>3} {_item_label(c, item)}")
    if len(todo) > args.next:
        print(
            f"   {DIM}... {len(todo) - args.next} more - ddd roadmap --epic "
            f"{current.number}{RESET}"
        )
    return 0


# -- entry ----------------------------------------------------------------


MAIN_EPILOG = """\
a typical pass through one item
  ddd roadmap                             what is next, and in which epic
  ddd show BUG-0002 --view all            read it, with its code and doc references
  ddd brief BUG-0070 BUG-0002 \\
      --out build/lane-b.md               hand a work packet to an agent
  ...do the work: docs -> tests -> code...
  ddd check                               did the docs stay consistent?
  ddd close BUG-0002 --dry-run            preview the close-out
  ddd close BUG-0002 --changelog "..."    do it

exit codes
  0  no errors (warnings do not fail)
  1  at least one error, or an ID that does not resolve

ddd help <command> prints that command's own examples.
Never commits - see CLAUDE.md. Full reference: scripts/ddd/README.md
"""

CHECK_EPILOG = """\
examples
  ddd check                            everything; exit 1 if any error
  ddd check --quiet                    errors only, for a pre-commit gate
  ddd check --summary                  agent gate: one line, exit 1 on error
  ddd check --max 5                    first 5 findings, then "... K more"
  ddd check --only roadmap-dangling    one rule, while fixing it
  ddd check --only ux-backlink,ux-index

Rule names are the bracketed tags in the output, e.g. [bare-id].
Warnings never affect the exit code.
"""

CLOSE_EPILOG = """\
examples
  ddd close BUG-0070 --dry-run         see the plan, write nothing
  ddd close BUG-0070                   internal fix, no changelog line
  ddd close BUG-0023 --changelog "#BUG-0023: sign-in consume is now POST-only"

Deletes the tracker entry, removes it from ROADMAP.md (keeping the line if it
cites other items), and optionally adds an Unreleased changelog line. It does
not touch the feature doc's Status or FRD.md, and it never edits the
HyperMnesia seed - it only tells you the seed cites this item.
"""

ROADMAP_EPILOG = """\
examples
  ddd roadmap                          progress bars, then the next 5 items
  ddd roadmap --next 12                a fuller queue
  ddd roadmap --epic 4                 one epic in full, with its "Done when:"

Epic 4's items have no checkbox: state is derived from whether the IDs they
cite are still open, so `ddd close` alone moves the bar.
"""

SHOW_EPILOG = """\
examples
  ddd show BUG-0002                    default: full text, position, mentions
  ddd show BUG-0002 --view short       one line
  ddd show BUG-0070 BUG-0002 --view short    a lane at a glance
  ddd show BUG-0002 --view files       what to touch when this closes
  ddd show GWS-0030 --view all         a feature: status, tags, UX, references

Accepts BUG-, TODO- and feature IDs (the project prefix is read from FRD.md); the leading # is optional.
"""

BRIEF_EPILOG = """\
examples
  ddd brief BUG-0070                   to stdout
  ddd brief BUG-0070 BUG-0002 --out build/lane-b.md

Open items only. Closing an item deletes its entry, so there is nothing left
to brief from - use git log -S<ID> -- docs/BUGS.md for a closed one.
"""


def _fmt(**kw):
    kw.setdefault("formatter_class", argparse.RawDescriptionHelpFormatter)
    return kw


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="ddd",
        description=__doc__.splitlines()[0],
        epilog=MAIN_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--version", action="version", version=f"ddd {VERSION}")
    sub = p.add_subparsers(dest="cmd")

    pc = sub.add_parser(
        "check",
        help="verify the mechanical DDD rules (writes nothing)",
        **_fmt(epilog=CHECK_EPILOG),
    )
    pc.add_argument("--only", help="comma-separated rule names to report")
    pc.add_argument(
        "--quiet", action="store_true", help="errors only, suppress warnings"
    )
    pc.add_argument(
        "--summary",
        action="store_true",
        help="one line: counts per rule, no per-finding output",
    )
    pc.add_argument(
        "--max",
        type=int,
        metavar="N",
        help="print at most N findings, then a count of the rest",
    )
    pc.set_defaults(fn=cmd_check)

    pl = sub.add_parser(
        "close",
        help="perform an item's close-out across every file",
        **_fmt(epilog=CLOSE_EPILOG),
    )
    pl.add_argument("id", metavar="ID", help="e.g. BUG-0002")
    pl.add_argument(
        "--changelog", help="one-line CHANGELOG entry; omit if not user-visible"
    )
    pl.add_argument(
        "--dry-run", action="store_true", help="print the plan, write nothing"
    )
    pl.set_defaults(fn=cmd_close)

    pr = sub.add_parser(
        "roadmap", help="epic progress and what is next", **_fmt(epilog=ROADMAP_EPILOG)
    )
    pr.add_argument(
        "--epic", type=int, metavar="N", help="show one epic's items in full"
    )
    pr.add_argument(
        "--next",
        type=int,
        default=5,
        metavar="N",
        help="how many upcoming items to list (default 5)",
    )
    pr.set_defaults(fn=cmd_roadmap)

    ps = sub.add_parser(
        "show", help="view one or more items", **_fmt(epilog=SHOW_EPILOG)
    )
    ps.add_argument("ids", nargs="+", metavar="ID")
    ps.add_argument(
        "--view",
        choices=("short", "details", "files", "all"),
        default="details",
        help="short: one line; details: full text and position; files: cited code and "
        "doc references; all: details + files (default: details)",
    )
    ps.set_defaults(fn=cmd_show)

    pb = sub.add_parser(
        "brief",
        help="extract a self-contained work packet",
        **_fmt(epilog=BRIEF_EPILOG),
    )
    pb.add_argument("ids", nargs="+", metavar="ID")
    pb.add_argument("--out", help="write to this path instead of stdout (use build/)")
    pb.set_defaults(fn=cmd_brief)

    # `ddd help close` reads better than `ddd close --help` for anyone who has not
    # used the tool before, and costs one dispatch.
    ph = sub.add_parser("help", help="show help, optionally for one command")
    ph.add_argument("topic", nargs="?", metavar="COMMAND")
    ph.set_defaults(fn=None)

    args = p.parse_args(argv)

    if args.cmd is None:  # bare `ddd`: help is more use than an argparse error
        p.print_help()
        return 0
    if args.cmd == "help":
        topic = getattr(args, "topic", None)
        if topic is None:
            p.print_help()
            return 0
        if topic not in sub.choices:
            print(f"{RED}error{RESET} no such command: {topic}", file=sys.stderr)
            print(
                f"  {DIM}try one of: {', '.join(sub.choices)}{RESET}", file=sys.stderr
            )
            return 1
        sub.choices[topic].print_help()
        return 0
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
