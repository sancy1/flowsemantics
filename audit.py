# filepath: audit.py
# layer: Tooling
# module: n/a (repository root)
# since: 0.0.0
# purpose: Enforce zero third-party runtime deps and ban ambient-time APIs in Core
# NOTES:
#   - Pure stdlib. No third-party imports. Satisfies Feature L itself.
#   - Exit 0 = all checks pass; 1 = any check fails; 2 = missing/corrupt config.
#   - Category 5 (source scan) is deferred until python/src/flowsemantics/ exists.
#     It fails closed: if the directory exists and contains any offending import,
#     the audit fails. Empty package dir is not "unchecked"; it is "nothing to check".

from __future__ import annotations

import ast
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYPROJECT = ROOT / "python" / "pyproject.toml"
SRC_DIR = ROOT / "python" / "src" / "flowsemantics"

ALLOWED_DEV_TOOLS = {"ruff", "mypy", "pytest", "pytest-asyncio", "uv"}
ALLOWED_BUILD_REQUIRES = {"hatchling"}
SELF_PACKAGE = "flowsemantics"
ALLOWLISTED_SOURCE_DIRS = {"interfaces", "testing"}
BANNED_AMBIENT_TIME = {
    ("datetime", "now"),
    ("datetime", "utcnow"),
    ("time", "time"),
}

results: list[tuple[str, bool, str]] = []

def record(name: str, passed: bool, detail: str) -> None:
    results.append((name, passed, detail))

def fail_early(msg: str) -> "None":
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(2)

def main() -> int:
    if not PYPROJECT.is_file():
        fail_early(f"missing config: {PYPROJECT}")
    with PYPROJECT.open("rb") as f:
        try:
            data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            fail_early(f"invalid TOML in {PYPROJECT}: {e}")

    # 1. runtime dependencies empty
    runtime = data.get("project", {}).get("dependencies", None)
    record(
        "runtime-dependencies-empty",
        runtime == [],
        f"project.dependencies = {runtime!r}",
    )

    # 2. dev group limited to declared tools
    dev = data.get("dependency-groups", {}).get("dev", [])
    dev_names: set[str] = set()
    for entry in dev:
        # entries are PEP 508 strings like "ruff>=0.6"; strip version specifier
        name = re.split(r"[<>=!~ ]", entry, maxsplit=1)[0].lower()
        dev_names.add(name)
    unknown_dev = dev_names - ALLOWED_DEV_TOOLS
    record(
        "dev-group-known-tools-only",
        not unknown_dev,
        f"unknown dev tools: {sorted(unknown_dev)}" if unknown_dev else f"dev = {sorted(dev_names)}",
    )

    # 3. build requires hatchling only
    build_req = data.get("build-system", {}).get("requires", [])
    build_names = {re.split(r"[<>=!~ ]", r, maxsplit=1)[0].lower() for r in build_req}
    record(
        "build-requires-hatchling-only",
        build_names == ALLOWED_BUILD_REQUIRES,
        f"build-system.requires = {build_req!r}",
    )

    # 4. no runtime optional-dependencies
    opt = data.get("project", {}).get("optional-dependencies", None)
    record(
        "no-runtime-optional-dependencies",
        opt is None or opt == {},
        f"project.optional-dependencies = {opt!r}",
    )

    # 5. source scan (deferred until package exists; fails closed)
    if not SRC_DIR.is_dir():
        record(
            "source-scan",
            True,
            f"source dir not yet present at {SRC_DIR}; nothing to scan",
        )
    else:
        violations: list[str] = []
        for py in SRC_DIR.rglob("*.py"):
            rel = py.relative_to(SRC_DIR)
            parts = rel.parts
            if parts and parts[0] in ALLOWLISTED_SOURCE_DIRS:
                continue
            try:
                src = py.read_text(encoding="utf-8")
            except OSError as e:
                violations.append(f"{py}: unreadable ({e})")
                continue
            try:
                tree = ast.parse(src, filename=str(py))
            except SyntaxError as e:
                violations.append(f"{py}:{e.lineno}: syntax error ({e.msg})")
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        top = a.name.split(".")[0]
                        if top not in sys.stdlib_module_names and top != SELF_PACKAGE:
                            violations.append(f"{py}:{node.lineno}: non-stdlib import {a.name!r}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module is None:
                        continue
                    top = node.module.split(".")[0]
                    if top not in sys.stdlib_module_names and top != SELF_PACKAGE:
                        violations.append(f"{py}:{node.lineno}: non-stdlib import {node.module!r}")
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute):
                        if isinstance(node.func.value, ast.Name):
                            mod = node.func.value.id
                            attr = node.func.attr
                            if (mod, attr) in BANNED_AMBIENT_TIME:
                                violations.append(
                                    f"{py}:{node.lineno}: banned ambient-time call {mod}.{attr}()"
                                )
        record(
            "source-scan",
            not violations,
            "; ".join(violations) if violations else f"scanned {SRC_DIR}",
        )

    print("=== AUDIT ===")
    all_pass = True
    for name, passed, detail in results:
        tag = "PASS" if passed else "FAIL"
        print(f"  [{tag}] {name}: {detail}")
        if not passed:
            all_pass = False
    print("=== RESULT ===")
    print("PASS" if all_pass else "FAIL")
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())

