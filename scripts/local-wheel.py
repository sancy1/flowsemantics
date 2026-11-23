# filepath: scripts/local-wheel.py
# layer: Tooling
# module: n/a (repository root)
# since: 0.0.0
# purpose: Build a wheel from python/ and place it in artifacts/ for local install
# NOTES:
#   - Uses python -m build (the standard, pip-compatible builder).
#   - The wheel it produces is what the pip-consumer-path exit gate installs.
#   - No third-party runtime dependency; build tools installed ad-hoc.

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY_DIR = ROOT / "python"
ARTIFACTS = ROOT / "artifacts"
PYPROJECT = PY_DIR / "pyproject.toml"

def main() -> int:
    if not PY_DIR.is_dir():
        print("ERROR: python directory missing: " + str(PY_DIR), file=sys.stderr)
        return 2
    if not PYPROJECT.is_file():
        print("ERROR: pyproject.toml missing: " + str(PYPROJECT), file=sys.stderr)
        return 2
    ARTIFACTS.mkdir(exist_ok=True)
    print("BUILD: python -m build --wheel " + str(PY_DIR))
    rc = subprocess.call([sys.executable, "-m", "build", "--wheel", str(PY_DIR)])
    if rc != 0:
        print("ERROR: build failed (exit " + str(rc) + ")", file=sys.stderr)
        return rc
    dist = PY_DIR / "dist"
    if not dist.is_dir():
        print("ERROR: no dist directory: " + str(dist), file=sys.stderr)
        return 2
    copied = 0
    for whl in dist.glob("*.whl"):
        dest = ARTIFACTS / whl.name
        shutil.copy2(whl, dest)
        print("COPIED: " + whl.name + " -> " + str(dest))
        copied += 1
    if copied == 0:
        print("ERROR: no wheel files found in " + str(dist), file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())

