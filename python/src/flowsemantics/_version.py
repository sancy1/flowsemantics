"""Single source of truth for the FlowSemantics package version.

Reads VERSION from the repository root when running from a source checkout,
and falls back to importlib.metadata when installed as a wheel. Both paths
agree because hatchling bakes the same VERSION content into the wheel
metadata via [tool.hatch.version] in python/pyproject.toml.

Layer:      Contracts
Module:     flowsemantics._version
Since:      0.0.0
Implements: n/a
Depends on: stdlib only (pathlib, importlib.metadata)
Used by:    flowsemantics.__init__, test_smoke, pip-consumer-path
See also:   VERSION (repository root), python/pyproject.toml

Notes:
  - VERSION is NOT shipped inside the wheel; the fallback path is the
    authoritative path for installed consumers.
  - No f-strings with nested quotes (F-010 lesson).
"""

from __future__ import annotations

from importlib import metadata
from pathlib import Path

DISTRIBUTION_NAME = "flow-semantics"


def _read_from_source_tree() -> str | None:
    """Walk up from this file to find VERSION at the repository root.

    Returns:
        The stripped VERSION content, or None if not found.

    Raises:
        None. Missing VERSION is not an error here; the caller falls back.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "VERSION"
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8").strip()
    return None


def _read_from_installed_metadata() -> str:
    """Read the version from installed distribution metadata.

    Returns:
        The version string reported by importlib.metadata.

    Raises:
        metadata.PackageNotFoundError: If the distribution is not installed.
    """
    return metadata.version(DISTRIBUTION_NAME)


def _resolve_version() -> str:
    """Resolve the version, preferring the source tree, falling back to metadata.

    Returns:
        The version string.

    Raises:
        RuntimeError: If neither path produces a version.
    """
    v = _read_from_source_tree()
    if v is not None and v != "":
        return v
    try:
        return _read_from_installed_metadata()
    except metadata.PackageNotFoundError as exc:
        raise RuntimeError(
            "Cannot resolve flowsemantics version: no VERSION in source tree "
            "and distribution not installed"
        ) from exc


__version__: str = _resolve_version()

