"""The mechanical half of the DDD rules in `docs/DOCS-DRIVEN-DEVELOPMENT.md`.

Only rules a machine can settle are here. Whether a feature doc's Behavior section
is any *good* is not checkable; whether it exists, is linked from FRD.md, and
agrees with the roadmap is. Judgement stays with the reviewer, bookkeeping comes
here.

Every check yields `Finding`s and never raises: one malformed doc must not hide
the other twenty checks' results.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from model import MD_LINK_RE, Corpus

ERROR, WARN = "error", "warn"

REQUIRED_SECTIONS = ("User Story", "Behavior", "Testing", "Status")
VALID_STATUS = ("Planned", "Implemented", "Deprecated")


@dataclass
class Finding:
    level: str
    path: Path
    line: int
    rule: str
    message: str


CODE_SPAN_RE = re.compile(r"`[^`]*`")


def _strip_code(line: str) -> str:
    """Blank out inline code spans.

    `DOCS-DRIVEN-DEVELOPMENT.md` quotes link *syntax* inside backticks - a template
    `[<PREFIX>-NNNN](<PREFIX>-NNNN-slug.md)` and an example `See [dashboard](…)`.
    Those are illustrations of the form, not links to a file that should exist.
    """
    return CODE_SPAN_RE.sub(lambda m: " " * len(m.group(0)), line)


def _rel(corpus: Corpus, p: Path) -> str:
    try:
        return str(p.resolve().relative_to(corpus.root))
    except ValueError:
        return str(p)


# -- trackers -------------------------------------------------------------


def check_next_free_id(c: Corpus) -> list[Finding]:
    """`Next free ID` must be past every ID actually in use, or the next author
    reuses one - and the DDD doc is explicit that IDs are never reused."""
    out: list[Finding] = []
    for path, ids in (
        (c.frd_path, [e.id for e in c.frd()] + [d.id for d in c.feature_docs()]),
        (c.bugs_path, [e.id for e in c.bugs()]),
        (c.todo_path, [e.id for e in c.todos()]),
    ):
        if not path.is_file():
            continue  # tracker not created yet (e.g. a fresh template)
        if "<PREFIX>" in path.read_text(encoding="utf-8"):
            continue  # unfilled template placeholder
        declared = c.next_free_id(path)
        if declared is None:
            out.append(
                Finding(ERROR, path, 1, "next-free-id", "no `Next free ID:` line")
            )
            continue
        ident, line = declared
        prefix, num = ident.rsplit("-", 1)
        used = [int(i.rsplit("-", 1)[1]) for i in ids if i.startswith(prefix + "-")]
        if used and int(num) <= max(used):
            out.append(
                Finding(
                    ERROR,
                    path,
                    line,
                    "next-free-id",
                    f"declares {ident} free but {prefix}-{max(used):04d} is in use",
                )
            )
    return out


def check_duplicate_ids(c: Corpus) -> list[Finding]:
    out: list[Finding] = []
    for entries in (c.bugs(), c.todos()):
        seen: dict[str, int] = {}
        for e in entries:
            if e.id in seen:
                out.append(
                    Finding(
                        ERROR,
                        e.path,
                        e.line,
                        "duplicate-id",
                        f"{e.id} already defined at line {seen[e.id]}",
                    )
                )
            else:
                seen[e.id] = e.line
    seen_frd: dict[str, int] = {}
    for e in c.frd():
        if e.id in seen_frd:
            out.append(
                Finding(
                    ERROR,
                    e.path,
                    e.line,
                    "duplicate-id",
                    f"{e.id} already listed at line {seen_frd[e.id]}",
                )
            )
        else:
            seen_frd[e.id] = e.line
    return out


def check_priority_markers(c: Corpus) -> list[Finding]:
    """Every BUGS.md entry ends with `[P#/D#]`; the roadmap's ordering leans on it."""
    return [
        Finding(
            WARN,
            e.path,
            e.line,
            "priority-marker",
            f"{e.id} has no trailing [P#/D#] marker",
        )
        for e in c.bugs()
        if e.priority is None
    ]


# -- roadmap --------------------------------------------------------------


def check_roadmap_dangling(c: Corpus) -> list[Finding]:
    """ "Closing a BUGS.md/TODO.md entry -> delete its ROADMAP.md line, same commit."

    This is the rule most likely to rot during a long epic, and the one `ddd close`
    exists to automate. An ID on the roadmap that no tracker or FRD still defines
    means a close-out was left half-done."""
    known = c.known_ids()
    out: list[Finding] = []
    for line, ids in c.roadmap_citations().items():
        for ident in ids:
            if ident not in known:
                out.append(
                    Finding(
                        ERROR,
                        c.roadmap_path,
                        line,
                        "roadmap-dangling",
                        f"{ident} is cited here but defined nowhere - closed without "
                        "deleting its roadmap line?",
                    )
                )
    return out


GROUP_PRIORITY_RE = re.compile(r"^(P[1-3])\b")


def check_roadmap_priority(c: Corpus) -> list[Finding]:
    """An epic can group its items under a `**P1 - …**` heading. When it does, the
    heading and the entry's own `[P#/D#]` marker are two claims about the same
    thing, and they drift: the roadmap gets reordered as understanding improves
    while `BUGS.md` keeps the priority from triage day.

    Reported against the roadmap line, because the heading is usually the newer
    judgement - but either side may be the one to fix."""
    out: list[Finding] = []
    for epic in c.roadmap_epics():
        for item in epic.items:
            if not item.group:
                continue
            m = GROUP_PRIORITY_RE.match(item.group)
            if not m:
                continue
            for ident in item.ids:
                e = c.tracker_entry(ident)
                if e is None or e.priority is None or e.priority == m.group(1):
                    continue
                out.append(
                    Finding(
                        WARN,
                        c.roadmap_path,
                        item.line,
                        "roadmap-priority",
                        f"{ident} sits under {item.group!r} but BUGS.md marks it "
                        f"{e.priority} - reconcile the two",
                    )
                )
    return out


def check_roadmap_covers_p1(c: Corpus) -> list[Finding]:
    """A P1 bug that no roadmap line mentions is a scheduling gap, not an error -
    the DDD doc says the roadmap is "never a blocker"."""
    cited = {i for ids in c.roadmap_citations().values() for i in ids}
    return [
        Finding(
            WARN,
            e.path,
            e.line,
            "roadmap-uncovered",
            f"{e.id} is P1 but appears nowhere in ROADMAP.md",
        )
        for e in c.bugs()
        if e.priority == "P1" and e.id not in cited
    ]


# -- FRD <-> feature docs -------------------------------------------------


def check_frd_status_sync(c: Corpus) -> list[Finding]:
    """`[X]`/`[ ]` in FRD.md must agree with the feature doc's own `## Status`."""
    docs = {d.id: d for d in c.feature_docs()}
    out: list[Finding] = []
    for e in c.frd():
        d = docs.get(e.id)
        if d is None:
            continue
        if d.status is None:
            out.append(
                Finding(
                    ERROR,
                    d.path,
                    1,
                    "status-missing",
                    f"{d.id} has no `## Status` value",
                )
            )
            continue
        word = _status_word(d.status)
        if word is None:
            out.append(
                Finding(
                    ERROR,
                    d.path,
                    1,
                    "status-invalid",
                    f"{d.id} status {d.status!r} does not start with one of "
                    f"{', '.join(VALID_STATUS)}",
                )
            )
            continue
        if word != d.status:
            # e.g. "Implemented. Push notifications deferred to #TODO-0022." - off-spec
            # but genuinely informative, so it is a warning and the qualifier is kept.
            out.append(
                Finding(
                    WARN,
                    d.path,
                    1,
                    "status-qualifier",
                    f"{d.id} status carries a qualifier beyond {word!r}; "
                    "the spec says Status is one word",
                )
            )
        if e.deprecated:
            if word != "Deprecated":
                out.append(
                    Finding(
                        ERROR,
                        e.path,
                        e.line,
                        "status-mismatch",
                        f"{e.id} sits under `## Deprecated` but its doc says {word}",
                    )
                )
            continue
        expected = "Implemented" if e.implemented else "Planned"
        if word != expected:
            mark = "[X]" if e.implemented else "[ ]"
            out.append(
                Finding(
                    ERROR,
                    e.path,
                    e.line,
                    "status-mismatch",
                    f"{e.id} is {mark} in FRD.md but its doc says {word}",
                )
            )
    return out


def _status_word(status: str) -> str | None:
    """The leading status keyword, ignoring any trailing qualifier."""
    for valid in VALID_STATUS:
        if status == valid or status.startswith(valid + "."):
            return valid
    return None


def check_frd_completeness(c: Corpus) -> list[Finding]:
    """Every feature doc is indexed, and every index row points at a real doc."""
    out: list[Finding] = []
    frd = c.frd()
    listed = {e.id for e in frd}
    for d in c.feature_docs():
        if d.id not in listed:
            out.append(
                Finding(
                    ERROR,
                    d.path,
                    1,
                    "frd-missing",
                    f"{d.id} exists on disk but is not listed in FRD.md",
                )
            )
    for e in frd:
        target = (c.docs / e.doc_path).resolve()
        if not target.is_file():
            out.append(
                Finding(
                    ERROR,
                    e.path,
                    e.line,
                    "frd-broken-link",
                    f"{e.id} points at {e.doc_path}, which does not exist",
                )
            )
    return out


def check_frd_tag_index(c: Corpus) -> list[Finding]:
    """The tag index is maintained by hand - the DDD doc lists that as a known
    trade-off - so drift here is expected and reported as a warning."""
    index = c.frd_tag_index()
    out: list[Finding] = []
    for d in c.feature_docs():
        for tag in d.tags:
            if tag in index and d.id not in index[tag]:
                out.append(
                    Finding(
                        WARN,
                        c.frd_path,
                        1,
                        "tag-index",
                        f"{d.id} carries {tag} but is missing from its tag index row",
                    )
                )
            elif tag not in index:
                out.append(
                    Finding(
                        WARN,
                        c.frd_path,
                        1,
                        "tag-index",
                        f"{d.id} carries {tag}, which has no row in FRD.md's tag index",
                    )
                )
    return out


def check_feature_sections(c: Corpus) -> list[Finding]:
    out: list[Finding] = []
    for d in c.feature_docs():
        have = {s.lower() for s in d.sections}
        for required in REQUIRED_SECTIONS:
            if required.lower() not in have:
                out.append(
                    Finding(
                        ERROR,
                        d.path,
                        1,
                        "feature-sections",
                        f"{d.id} is missing the required `## {required}` section",
                    )
                )
        if not d.title.startswith(d.id):
            out.append(
                Finding(
                    WARN,
                    d.path,
                    1,
                    "feature-title",
                    f"title {d.title!r} does not open with {d.id}",
                )
            )
        if not d.tags:
            out.append(
                Finding(
                    WARN, d.path, 1, "feature-tags", f"{d.id} has no **Tags:** line"
                )
            )
    return out


# -- UX -------------------------------------------------------------------


def check_ux_backlinks(c: Corpus) -> list[Finding]:
    """ "the link goes both ways" - a feature's `## UX` section and the page's
    `**Features:**` header must agree, as must a page's `Uses modules` and the
    module's `Used by`."""
    ux = {(d.kind, d.slug): d for d in c.ux_docs()}
    out: list[Finding] = []

    for d in c.feature_docs():
        for target in d.ux_links:
            p = Path(target)
            kind = (
                "page"
                if p.parent.name == "pages"
                else "module"
                if p.parent.name == "modules"
                else None
            )
            if kind is None:
                continue
            doc = ux.get((kind, p.stem))
            if doc is None:
                out.append(
                    Finding(
                        ERROR,
                        d.path,
                        1,
                        "ux-broken-link",
                        f"{d.id} links {target}, which does not exist",
                    )
                )
            elif kind == "page" and d.id not in doc.features:
                out.append(
                    Finding(
                        ERROR,
                        doc.path,
                        1,
                        "ux-backlink",
                        f"{d.id} links this page but its **Features:** does not list {d.id}",
                    )
                )

    feature_ids = {d.id for d in c.feature_docs()}
    for doc in ux.values():
        for ident in doc.features:
            if ident not in feature_ids:
                out.append(
                    Finding(
                        ERROR,
                        doc.path,
                        1,
                        "ux-backlink",
                        f"**Features:** names {ident}, which has no feature doc",
                    )
                )
        if doc.kind == "page":
            for slug in doc.uses_modules:
                mod = ux.get(("module", slug))
                if mod is None:
                    out.append(
                        Finding(
                            ERROR,
                            doc.path,
                            1,
                            "ux-broken-link",
                            f"uses module {slug!r}, which does not exist",
                        )
                    )
                elif doc.slug not in mod.used_by:
                    out.append(
                        Finding(
                            WARN,
                            mod.path,
                            1,
                            "ux-backlink",
                            f"page {doc.slug!r} uses this module but **Used by:** omits it",
                        )
                    )
    return out


def check_ux_index(c: Corpus) -> list[Finding]:
    """ "keep `docs/ux/README.md` current when a page or module is added, renamed,
    or removed"."""
    indexed = c.ux_readme_slugs()
    return [
        Finding(
            WARN,
            c.ux_readme_path,
            1,
            "ux-index",
            f"{d.kind} {d.slug!r} is not indexed in docs/ux/README.md",
        )
        for d in c.ux_docs()
        if d.slug not in indexed
    ]


# -- links ----------------------------------------------------------------


def check_doc_links(c: Corpus) -> list[Finding]:
    """Relative links inside `docs/` resolve. External and anchor-only links are
    left alone - this check never touches the network."""
    out: list[Finding] = []
    for p in c.markdown_files():
        in_fence = False
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for target in MD_LINK_RE.findall(_strip_code(line)):
                if re.match(r"^(https?:|mailto:|#)", target) or "<" in target:
                    continue  # external, anchor, or a template <PLACEHOLDER>
                dest = (p.parent / target.split("#", 1)[0]).resolve()
                if not dest.exists():
                    out.append(
                        Finding(
                            ERROR,
                            p,
                            i,
                            "broken-link",
                            f"link target {target!r} does not exist",
                        )
                    )
    return out


def check_bare_id_links(c: Corpus) -> list[Finding]:
    """ "When linking to the feature doc from within `docs/`, use a real Markdown
    link, not a bare mention." Flags a bare `#<PREFIX>-NNNN` inside docs/features/ and
    docs/ux/, where a link is always available. Trackers and the roadmap cite bare
    IDs by design, so they are exempt."""
    out: list[Finding] = []
    linked_ids: set[str]
    for p in c.markdown_files():
        rel = p.relative_to(c.docs)
        if rel.parts[0] not in ("features", "ux"):
            continue
        text = p.read_text(encoding="utf-8")
        linked_ids = {
            f"{a}-{b}"
            for target in MD_LINK_RE.findall(text)
            for a, b in c.id_re.findall(target)
        }
        in_fence = False
        for i, line in enumerate(text.splitlines(), start=1):
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            stripped = MD_LINK_RE.sub("", line)
            for a, b in c.id_re.findall(stripped):
                ident = f"{a}-{b}"
                if (
                    a == c.prefix
                    and ident not in linked_ids
                    and not p.name.startswith(ident)
                ):
                    out.append(
                        Finding(
                            WARN,
                            p,
                            i,
                            "bare-id",
                            f"bare mention of {ident}; link the feature doc instead",
                        )
                    )
    return out


# -- HyperMnesia seed -----------------------------------------------------


def check_seed_citations(c: Corpus) -> list[Finding]:
    """`deploy/hypermnesia-seed.sql` encodes `must` rules that cite open defects
    on purpose - its own header says so. That makes it a close-out artifact: once
    the bug is closed the rule describes a defect that no longer exists, and the
    PreToolUse hook keeps injecting it on every edit to that component.

    Only the `Open #BUG-NNNN:` form is checked. A bare `(#BUG-NNNN)` in a rationale
    is historical provenance - "hand-rolled JSON broke the calendar-delete dialog
    once" justifies the rule permanently, and stays true after the fix.
    """
    if not c.seed_path.is_file():
        return []
    known = c.known_ids()
    out: list[Finding] = []
    for line, ids in c.seed_open_citations().items():
        for ident in ids:
            if ident not in known:
                out.append(
                    Finding(
                        WARN,
                        c.seed_path,
                        line,
                        "seed-stale",
                        f"describes {ident} as open, but it is closed - re-check this rule, "
                        "drop the `Open` marker or reword it, and re-seed "
                        "(psql -v ON_ERROR_STOP=1 -f deploy/hypermnesia-seed.sql)",
                    )
                )
    return out


ALL_CHECKS = (
    check_next_free_id,
    check_duplicate_ids,
    check_priority_markers,
    check_roadmap_dangling,
    check_roadmap_covers_p1,
    check_roadmap_priority,
    check_frd_status_sync,
    check_frd_completeness,
    check_frd_tag_index,
    check_feature_sections,
    check_ux_backlinks,
    check_ux_index,
    check_doc_links,
    check_bare_id_links,
    check_seed_citations,
)


def run_all(c: Corpus, only: set[str] | None = None) -> list[Finding]:
    out: list[Finding] = []
    for fn in ALL_CHECKS:
        try:
            found = fn(c)
        except Exception as exc:  # a broken check must not hide the others
            out.append(
                Finding(
                    ERROR, c.docs, 1, "check-crashed", f"{fn.__name__} raised {exc!r}"
                )
            )
            continue
        out.extend(f for f in found if only is None or f.rule in only)
    return out
