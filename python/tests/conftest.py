"""Pytest configuration: insert src/ into sys.path for source-tree imports.

Layer:      Tests
Module:     tests.conftest
Since:      0.0.0
Implements: pytest conftest hook
Depends on: stdlib (pathlib, sys)
Used by:    every pytest run in python/tests
See also:   python/pyproject.toml [tool.pytest.ini_options]

Notes:
  - Option A confirmed: source tree importable without pip install.
  - In CI, uv sync installs editable; this sys.path insert is then redundant but harmless.
  - Do NOT add fixtures here that depend on third-party packages in Phase 0.0.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_SRC = _HERE.parent.parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

