# filepath: scripts/docs-snippets.py
# layer: Tooling
# module: n/a (repository root)
# since: 0.1.0
# purpose: Verify doc code snippets against the public API and sample source
# NOTES:
#   - Extracts fenced ```python blocks from docs/*.md.
#   - Each block must parse as valid Python (ast.parse).
#   - Every `from flowsemantics import ...` name must be in the package
#     public surface (__all__). This catches doc/API drift mechanically.
#   - Full behavioral equivalence with samples is enforced by the
#     docs-consumer.yml sample run, not by this script.

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
PY_DIR = ROOT / "python"


def _public_names() -> set[str]:
    sys.path.insert(0, str(PY_DIR / "src"))
    try:
        import flowsemantics

        return set(flowsemantics.__all__)
    finally:
        sys.path.remove(str(PY_DIR / "src"))


def _iter_python_blocks(path: Path):
    text = path.read_text(encoding="utf-8")
    in_block = False
    buf: list[str] = []
    for line in text.splitlines():
        if line.strip().startswith("```"):
            if in_block:
                yield "\n".join(buf)
                buf = []
            in_block = not in_block
            continue
        if in_block:
            buf.append(line)
    if buf:
        yield "\n".join(buf)


def _check_block(source: str, names: set[str], origin: str) -> list[str]:
    errors: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"{origin}: snippet does not parse: {exc}"]
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "flowsemantics":
            for alias in node.names:
                if alias.name not in names:
                    errors.append(
                        f"{origin}: imports non-public name {alias.name!r} "
                        "from flowsemantics"
                    )
    return errors


def main() -> int:
    if not DOCS.is_dir():
        print("no docs/ directory; nothing to verify")
        return 0
    names = _public_names()
    errors: list[str] = []
    checked = 0
    for md in sorted(DOCS.rglob("*.md")):
        for block in _iter_python_blocks(md):
            if "flowsemantics" not in block:
                continue
            checked += 1
            errors.extend(_check_block(block, names, str(md.relative_to(ROOT))))
    if errors:
        for error in errors:
            print("FAIL: " + error)
        return 1
    print(f"OK: {checked} flowsemantics snippet(s) verified against public API")
    return 0


if __name__ == "__main__":
    sys.exit(main())
