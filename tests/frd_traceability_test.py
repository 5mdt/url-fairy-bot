# frd_traceability_test.py
#
# Enforces CLAUDE.md's "FRD feature id must be added to functions as
# comments" rule and docs/DOCS-DRIVEN-DEVELOPMENT.md's `#<PREFIX>-NNNN`
# reference format (#BUG-0060). Reads app/*.py source directly rather than
# importing it, so it never touches app.config's env-dependent settings.

import ast
import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(ROOT, "app")
FRD_PATH = os.path.join(ROOT, "docs", "FRD.md")

ID_PATTERN = re.compile(r"#UFB-\d{4}")


def _known_feature_ids() -> set[str]:
    with open(FRD_PATH, "r", encoding="utf-8") as f:
        text = f.read()
    return {f"#{m}" for m in re.findall(r"UFB-\d{4}", text)}


def _app_source_files() -> list[str]:
    return sorted(glob.glob(os.path.join(APP_DIR, "*.py")))


def _comment_block_above(lines: list[str], start_line: int) -> str:
    """Contiguous `#`-comment lines directly above a 1-indexed source line,
    skipping decorator lines above the def/class itself."""
    idx = start_line - 1  # 0-indexed line of the def/class/decorator stack top
    # Walk upward over decorator lines first (they sit between the comment
    # block and the def/class for a decorated function).
    while idx > 0 and lines[idx - 1].strip().startswith("@"):
        idx -= 1
    comment_lines = []
    idx -= 1
    while idx >= 0 and lines[idx].strip().startswith("#"):
        comment_lines.append(lines[idx])
        idx -= 1
    return "\n".join(reversed(comment_lines))


def _top_level_nodes(tree: ast.Module):
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield node


def test_every_top_level_function_and_class_has_a_feature_id():
    missing = []
    for path in _app_source_files():
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
        lines = source.splitlines()
        tree = ast.parse(source, filename=path)
        for node in _top_level_nodes(tree):
            region = _comment_block_above(lines, node.lineno)
            docstring = ast.get_docstring(node) or ""
            if not ID_PATTERN.search(region) and not ID_PATTERN.search(docstring):
                rel = os.path.relpath(path, ROOT)
                missing.append(f"{rel}:{node.lineno} {node.name}")

    assert not missing, (
        "Missing #UFB-NNNN feature-id comment (CLAUDE.md / "
        "DOCS-DRIVEN-DEVELOPMENT.md) above:\n" + "\n".join(missing)
    )


def test_every_referenced_feature_id_exists_in_frd():
    known = _known_feature_ids()
    unknown = set()
    for path in _app_source_files():
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
        for match in ID_PATTERN.findall(source):
            if match not in known:
                unknown.add(f"{match} ({os.path.relpath(path, ROOT)})")

    assert not unknown, f"Feature id(s) not found in docs/FRD.md: {sorted(unknown)}"
