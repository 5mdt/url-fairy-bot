"""Read-only model of the calsync DDD doc corpus.

Stdlib only, no DB, no network - this parses `docs/` and nothing else, so it runs
in CI and inside a subagent without the HyperMnesia store being reachable.

Parsing is deliberately forgiving: a shape this code does not recognise yields no
entry rather than an exception, because a linter that crashes on the first odd
line gets switched off. Anything genuinely malformed is reported as a finding by
`checks.py`, not raised from here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# The tracker prefixes are fixed by the spec; the feature prefix is per-project and
# is read from the docs - see `Corpus.prefix`. `Corpus.id_re` etc. build the
# patterns that include it.
TRACKER_PREFIXES = ("BUG", "TODO")
# `deploy/hypermnesia-seed.sql` marks a rationale that describes a still-open defect
# with a literal `Open #BUG-NNNN:` prefix. See `Corpus.seed_open_citations`.
NEXT_FREE_RE = re.compile(r"^Next free ID:\s*\*\*([A-Z]+-\d{4})\*\*")
# `- [X] [CAL-0001. Magic-link sign-in](features/CAL-0001-slug.md) - `#auth` `#mail`
# (with this project's prefix in place of CAL)
FRD_ROW_TEMPLATE = (
    r"^-\s*\[(?P<mark>[Xx ])\]\s*\[(?P<id>{prefix}-\d{{4}})\.\s*(?P<title>[^\]]*)\]"
    r"\((?P<path>[^)]+)\)(?P<rest>.*)$"
)
# A tracker entry opens with `- #BUG-0001 ` / `- #TODO-0001 ` and runs until the
# next entry or heading. Entries here are one long wrapped line in practice, but
# treating them as blocks means a future multi-line entry does not silently lose
# its tail.
ENTRY_OPEN_RE = re.compile(r"^-\s*#(?P<id>(?:BUG|TODO)-\d{4})\s+(?P<text>.*)$")
PRIORITY_RE = re.compile(r"\[(P[1-3])/(D[1-4])\]\s*$")
MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
TAG_RE = re.compile(r"`(#[a-z0-9-]+)`")
# `internal/syncengine/engine.go:229-243` - the pointers already written into BUGS.md
CODE_REF_RE = re.compile(
    r"`((?:internal|cmd|deploy|docs)/[^`:\s]+\.[a-z]+)(?::([0-9,\-]+))?`"
)


@dataclass
class Located:
    """Anything that knows which file and line it came from."""

    path: Path
    line: int  # 1-indexed


@dataclass
class FrdEntry(Located):
    id: str
    title: str
    doc_path: str  # as written, relative to docs/
    implemented: bool
    deprecated: bool
    tags: list[str] = field(default_factory=list)


def code_refs(text: str) -> list[str]:
    """Source paths cited in backticks, `path` or `path:lines`.

    Order-preserving and deduplicated: the same file is often cited twice in one
    entry, once per call site.
    """
    out = [f"{p}:{lines}" if lines else p for p, lines in CODE_REF_RE.findall(text)]
    return list(dict.fromkeys(out))


@dataclass
class TrackerEntry(Located):
    """A `BUGS.md` or `TODO.md` item."""

    id: str
    text: str
    section: str  # "Bugs" / "Tech debt" / "Chores"
    subsection: str | None  # the `###` heading, if any
    priority: str | None  # "P1"
    difficulty: str | None  # "D2"
    end_line: int  # 1-indexed, inclusive

    @property
    def code_refs(self) -> list[str]:
        return code_refs(self.text)


@dataclass
class FeatureDoc(Located):
    id: str
    title: str
    sections: list[str]
    status: str | None
    tags: list[str]
    ux_links: list[str]  # resolved, repo-relative
    body: str = ""


@dataclass
class RoadmapItem(Located):
    """One ordered entry under an epic heading.

    Two forms coexist: a `- [X]`/`- [ ]` checkbox (epics 1-3, 5, 6) whose mark is
    authoritative, and a bare `N.` numbered entry (epic 4) whose state has to be
    derived from whether the items it cites are still open.
    """

    ids: list[str]
    text: str
    group: str | None  # the bold lead-in above it, e.g. "P1 - security front door"
    mark: str | None  # "x", " ", or None for a numbered entry
    ordinal: str  # "1." or "-", as written


@dataclass
class RoadmapEpic(Located):
    number: int
    name: str
    items: list[RoadmapItem]
    done_when: str | None


@dataclass
class UxDoc(Located):
    slug: str
    kind: str  # "page" | "module"
    features: list[str]
    uses_modules: list[str]  # slugs
    used_by: list[str]  # slugs


def _read(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except OSError, UnicodeDecodeError:
        return []


def _heading(line: str) -> tuple[int, str] | None:
    m = re.match(r"^(#{1,6})\s+(.*)$", line)
    return (len(m.group(1)), m.group(2).strip()) if m else None


class Corpus:
    """The whole doc set, parsed once."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.docs = self.root / "docs"
        self.frd_path = self.docs / "FRD.md"
        self.bugs_path = self.docs / "BUGS.md"
        self.todo_path = self.docs / "TODO.md"
        self.roadmap_path = self.docs / "ROADMAP.md"
        self.changelog_path = self.docs / "CHANGELOG.md"
        self.ux_readme_path = self.docs / "ux" / "README.md"
        self.seed_path = self.root / "deploy" / "hypermnesia-seed.sql"
        self.prefix = self._detect_prefix()
        alt = "|".join(
            re.escape(p)
            for p in (*([self.prefix] if self.prefix else []), *TRACKER_PREFIXES)
        )
        self.id_re = re.compile(rf"\b({alt})-(\d{{4}})\b")
        self.seed_open_re = re.compile(rf"\bOpen\s+#({alt})-(\d{{4}})\b")
        self.frd_row_re = re.compile(
            FRD_ROW_TEMPLATE.format(
                prefix=re.escape(self.prefix) if self.prefix else r"(?!)"
            )
        )

    def _detect_prefix(self) -> str | None:
        """The feature-ID prefix, which differs per project (CAL, GWS, MDV...).
        Read from FRD.md's `Next free ID:` line; failing that, from the feature
        doc filenames. An unfilled `<PREFIX>` template yields None."""
        for line in _read(self.frd_path):
            m = NEXT_FREE_RE.match(line)
            if m:
                return m.group(1).rsplit("-", 1)[0]
        feats = self.docs / "features"
        if feats.is_dir():
            for p in sorted(feats.glob("*.md")):
                m = re.match(r"([A-Z]+)-\d{4}\b", p.name)
                if m and m.group(1) not in TRACKER_PREFIXES:
                    return m.group(1)
        return None

    # -- trackers ---------------------------------------------------------

    def next_free_id(self, path: Path) -> tuple[str, int] | None:
        for i, line in enumerate(_read(path), start=1):
            m = NEXT_FREE_RE.match(line)
            if m:
                return m.group(1), i
        return None

    def _tracker_entries(self, path: Path) -> list[TrackerEntry]:
        lines = _read(path)
        section, subsection = "", None
        open_entry: TrackerEntry | None = None
        out: list[TrackerEntry] = []

        def close(at: int) -> None:
            nonlocal open_entry
            if open_entry is not None:
                open_entry.end_line = at
                open_entry.text = open_entry.text.strip()
                m = PRIORITY_RE.search(open_entry.text)
                if m:
                    open_entry.priority, open_entry.difficulty = m.group(1), m.group(2)
                out.append(open_entry)
                open_entry = None

        for i, line in enumerate(lines, start=1):
            h = _heading(line)
            if h:
                close(i - 1)
                level, title = h
                if level == 2:
                    section, subsection = title, None
                elif level == 3:
                    subsection = title
                continue
            m = ENTRY_OPEN_RE.match(line)
            if m:
                close(i - 1)
                open_entry = TrackerEntry(
                    path=path,
                    line=i,
                    id=m.group("id"),
                    text=m.group("text"),
                    section=section,
                    subsection=subsection,
                    priority=None,
                    difficulty=None,
                    end_line=i,
                )
            elif open_entry is not None:
                if line.strip() and not line.startswith("-"):
                    open_entry.text += " " + line.strip()
                elif line.startswith("-"):
                    # a sibling list item that is not an entry ends the block
                    close(i - 1)
        close(len(lines))
        return out

    def bugs(self) -> list[TrackerEntry]:
        return self._tracker_entries(self.bugs_path)

    def todos(self) -> list[TrackerEntry]:
        return self._tracker_entries(self.todo_path)

    def tracker_entry(self, ident: str) -> TrackerEntry | None:
        for e in self.bugs() + self.todos():
            if e.id == ident:
                return e
        return None

    # -- FRD --------------------------------------------------------------

    def frd(self) -> list[FrdEntry]:
        out: list[FrdEntry] = []
        section = ""
        for i, line in enumerate(_read(self.frd_path), start=1):
            h = _heading(line)
            if h and h[0] == 2:
                section = h[1]
                continue
            m = self.frd_row_re.match(line)
            if not m:
                continue
            out.append(
                FrdEntry(
                    path=self.frd_path,
                    line=i,
                    id=m.group("id"),
                    title=m.group("title").strip(),
                    doc_path=m.group("path"),
                    implemented=m.group("mark").lower() == "x",
                    deprecated=section.lower().startswith("deprecated"),
                    tags=TAG_RE.findall(m.group("rest")),
                )
            )
        return out

    def frd_tag_index(self) -> dict[str, list[str]]:
        """The hand-maintained `## Tags` block at the bottom of FRD.md."""
        out: dict[str, list[str]] = {}
        in_tags = False
        for line in _read(self.frd_path):
            h = _heading(line)
            if h and h[0] == 2:
                in_tags = h[1].strip().lower() == "tags"
                continue
            if not in_tags:
                continue
            m = re.match(r"^-\s*`(#[a-z0-9-]+)`:\s*(.*)$", line)
            if m:
                out[m.group(1)] = [
                    f"{p}-{n}" for p, n in self.id_re.findall(m.group(2))
                ]
        return out

    # -- feature docs -----------------------------------------------------

    def feature_docs(self) -> list[FeatureDoc]:
        out: list[FeatureDoc] = []
        d = self.docs / "features"
        if not d.is_dir():
            return out
        for p in sorted(d.glob(f"{self.prefix}-*.md") if self.prefix else []):
            lines = _read(p)
            title, sections, status, tags, ux = "", [], None, [], []
            cur = None
            for line in lines:
                h = _heading(line)
                if h:
                    level, text = h
                    if level == 1 and not title:
                        title = text
                    elif level in (2, 3):
                        sections.append(text)
                        cur = text.lower()
                    continue
                if line.startswith("**Tags:**"):
                    tags = re.findall(r"#([a-z0-9-]+)", line)
                elif cur == "status" and line.strip() and status is None:
                    status = line.strip()
                elif cur == "ux":
                    for target in MD_LINK_RE.findall(line):
                        if target.startswith("#"):
                            continue
                        ux.append(
                            str((p.parent / target).resolve().relative_to(self.root))
                        )
            m = self.id_re.search(p.name)
            out.append(
                FeatureDoc(
                    path=p,
                    line=1,
                    id=f"{m.group(1)}-{m.group(2)}" if m else p.stem,
                    title=title,
                    sections=sections,
                    status=status,
                    tags=[f"#{t}" for t in tags],
                    ux_links=ux,
                    body="\n".join(lines),
                )
            )
        return out

    # -- UX ---------------------------------------------------------------

    def ux_docs(self) -> list[UxDoc]:
        out: list[UxDoc] = []
        base = self.docs / "ux"
        for kind, sub in (("page", "pages"), ("module", "modules")):
            d = base / sub
            if not d.is_dir():
                continue
            for p in sorted(d.glob("*.md")):
                features: list[str] = []
                uses: list[str] = []
                used_by: list[str] = []
                for line in _read(p):
                    # the header packs several bold fields onto one line
                    for label, bucket in (
                        ("Features:", features),
                        ("Uses modules:", uses),
                        ("Used by:", used_by),
                    ):
                        idx = line.find(f"**{label}**")
                        if idx < 0:
                            continue
                        tail = line[idx + len(label) + 4 :]
                        # stop at the next bold field on the same line
                        nxt = tail.find("**")
                        seg = tail[:nxt] if nxt >= 0 else tail
                        if bucket is features:
                            bucket.extend(
                                f"{a}-{b}" for a, b in self.id_re.findall(seg)
                            )
                        else:
                            bucket.extend(Path(t).stem for t in MD_LINK_RE.findall(seg))
                    if line.startswith("## "):
                        break
                out.append(
                    UxDoc(
                        path=p,
                        line=1,
                        slug=p.stem,
                        kind=kind,
                        features=features,
                        uses_modules=uses,
                        used_by=used_by,
                    )
                )
        return out

    def ux_readme_slugs(self) -> set[str]:
        return {
            Path(t).stem
            for line in _read(self.ux_readme_path)
            for t in MD_LINK_RE.findall(line)
            if "pages/" in t or "modules/" in t
        }

    # -- roadmap / changelog / seed ---------------------------------------

    def roadmap_citations(self) -> dict[int, list[str]]:
        """1-indexed line number -> IDs cited on it, excluding the epic table."""
        out: dict[int, list[str]] = {}
        for i, line in enumerate(_read(self.roadmap_path), start=1):
            ids = [f"{a}-{b}" for a, b in self.id_re.findall(line)]
            if ids:
                out[i] = list(dict.fromkeys(ids))
        return out

    def roadmap_epics(self) -> list[RoadmapEpic]:
        """Parse ROADMAP.md into epics and ordered items.

        The `| # | Epic | Why here |` summary table at the top is skipped: it holds
        no items, and its cells would otherwise read as citations.
        """
        epics: list[RoadmapEpic] = []
        cur: RoadmapEpic | None = None
        group: str | None = None
        for i, line in enumerate(_read(self.roadmap_path), start=1):
            h = _heading(line)
            if h and h[0] == 2:
                m = re.match(r"^(\d+)\.\s*(.*)$", h[1])
                cur = RoadmapEpic(
                    path=self.roadmap_path,
                    line=i,
                    number=int(m.group(1)) if m else len(epics) + 1,
                    name=(m.group(2) if m else h[1]).strip(),
                    items=[],
                    done_when=None,
                )
                epics.append(cur)
                group = None
                continue
            if cur is None or line.lstrip().startswith("|"):
                continue
            if line.startswith("**Done when:**"):
                cur.done_when = line[len("**Done when:**") :].strip()
                continue
            gm = re.match(r"^\*\*(.+?)\*\*", line)
            if gm and not line.startswith("**Done when:**"):
                group = gm.group(1).strip()
                continue
            im = re.match(
                r"^(?P<ord>-|\d+\.)\s+(?:\[(?P<mark>[Xx ])\]\s*)?(?P<rest>.*)$", line
            )
            if not im:
                continue
            rest = im.group("rest")
            sep = rest.find(" - ")
            head = rest if sep < 0 else rest[:sep]
            ids = list(dict.fromkeys(f"{a}-{b}" for a, b in self.id_re.findall(head)))
            if not ids:
                continue
            cur.items.append(
                RoadmapItem(
                    path=self.roadmap_path,
                    line=i,
                    ids=ids,
                    text=(rest[sep + 3 :] if sep >= 0 else "").strip(),
                    group=group,
                    mark=(im.group("mark") or "").lower().strip() or None,
                    ordinal=im.group("ord"),
                )
            )
        return epics

    def item_is_done(self, item: RoadmapItem) -> bool:
        """A checkbox mark wins; otherwise the item is done once every ID it cites
        has left `BUGS.md`/`TODO.md` (closed) or is Implemented in `FRD.md`."""
        if item.mark is not None:
            return item.mark == "x"
        open_tracker = {e.id for e in self.bugs()} | {e.id for e in self.todos()}
        planned = {e.id for e in self.frd() if not e.implemented}
        return not any(i in open_tracker or i in planned for i in item.ids)

    def seed_citations(self) -> dict[int, list[str]]:
        out: dict[int, list[str]] = {}
        for i, line in enumerate(_read(self.seed_path), start=1):
            ids = [f"{a}-{b}" for a, b in self.id_re.findall(line)]
            if ids:
                out[i] = list(dict.fromkeys(ids))
        return out

    def seed_open_citations(self) -> dict[int, list[str]]:
        """Only the citations the seed marks as describing a *currently-open* defect.

        The file uses `Open #BUG-NNNN: …` for exactly that, and a bare `(#BUG-NNNN)`
        for historical provenance - "hand-rolled JSON broke this once" stays true
        after the bug is fixed and is the rule's whole justification. Only the
        `Open` form goes stale on close.
        """
        out: dict[int, list[str]] = {}
        for i, line in enumerate(_read(self.seed_path), start=1):
            ids = [f"{a}-{b}" for a, b in self.seed_open_re.findall(line)]
            if ids:
                out[i] = list(dict.fromkeys(ids))
        return out

    def roadmap_position(self, ident: str) -> tuple[RoadmapEpic, RoadmapItem] | None:
        """The epic and ordered item that schedules `ident`, if any."""
        for epic in self.roadmap_epics():
            for item in epic.items:
                if ident in item.ids:
                    return epic, item
        return None

    def references(self, ident: str) -> list[tuple[Path, int, str]]:
        """Every line under `docs/` (plus the seed) that mentions `ident`.

        This is what makes a close-out reviewable: an item is rarely cited only by
        its own tracker entry, and the other mentions are the ones that quietly go
        stale.

        `DOCS-DRIVEN-DEVELOPMENT.md` is excluded: its templates use `BUG-0001`,
        `BUG-0002` and `CAL-0001` as generic placeholders, so every one of them
        would match some real item here by coincidence.
        """
        pat = re.compile(rf"\b{re.escape(ident)}\b")
        out: list[tuple[Path, int, str]] = []
        files = [
            p for p in self.markdown_files() if p.name != "DOCS-DRIVEN-DEVELOPMENT.md"
        ]
        if self.seed_path.is_file():
            files.append(self.seed_path)
        for p in files:
            for i, line in enumerate(_read(p), start=1):
                if pat.search(line):
                    out.append((p, i, line.strip()))
        return out

    def known_ids(self) -> set[str]:
        return (
            {e.id for e in self.bugs()}
            | {e.id for e in self.todos()}
            | {e.id for e in self.frd()}
            | {d.id for d in self.feature_docs()}
        )

    def markdown_files(self) -> list[Path]:
        return sorted(p for p in self.docs.rglob("*.md") if p.is_file())
