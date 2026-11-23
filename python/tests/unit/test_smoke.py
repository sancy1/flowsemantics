"""Smoke tests: package imports, version wiring, subpackages.

Layer:      Tests
Module:     tests.unit.test_smoke
Since:      0.0.0
Implements: Phase 0.0 exit-gate behavioral proofs
Depends on: pytest, flowsemantics
Used by:    pytest; CI ci.yml; Phase 0.0 close probe
See also:   VERSION, python/src/flowsemantics/_version.py

Notes:
  - These are real behavioral assertions, not file-existence checks.
  - If they fail, the version wiring or the package surface is broken.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import flowsemantics


def _expected_version() -> str:
    """Walk up to the repository root and read VERSION."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "VERSION"
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8").strip()
    raise AssertionError("VERSION file not found above " + str(here))


def test_version_matches_version_file() -> None:
    """flowsemantics.__version__ must equal VERSION at the repository root."""
    expected = _expected_version()
    assert flowsemantics.__version__ == expected, (
        "flowsemantics.__version__ = "
        + repr(flowsemantics.__version__)
        + " but VERSION file says "
        + repr(expected)
    )


def test_public_api_is_explicit() -> None:
    """__all__ is an explicit list of strings containing __version__."""
    assert "__version__" in flowsemantics.__all__, "__version__ missing from public surface"
    assert all(isinstance(name, str) for name in flowsemantics.__all__), (
        "__all__ must contain only strings"
    )


def test_subpackages_import() -> None:
    """All seven subpackages plus testing must import cleanly."""
    subpackages = [
        "abstractions",
        "configuration",
        "errors",
        "execution",
        "finalization",
        "trace",
        "validation",
        "portable",
        "testing",
    ]
    for name in subpackages:
        mod = importlib.import_module("flowsemantics." + name)
        assert mod is not None, "failed to import flowsemantics." + name
