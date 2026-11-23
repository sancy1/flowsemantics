"""Generate a CycloneDX SBOM for the FlowSemantics Python package (SPEC 15.3).

Lists runtime, build, and development dependencies with resolved versions
where the environment provides them. Stdlib only.

Usage:
    python scripts/sbom.py > sbom.cdx.json

Reproducibility: the dependency *names and version constraints* come from
python/pyproject.toml at the release commit; resolved versions come from
the environment running the script (recorded as "resolved" or "unresolved").
"""

from __future__ import annotations

import json
import sys
import tomllib
from importlib import metadata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "python" / "pyproject.toml"


def _version_of(dist_name: str) -> str:
    """Resolve an installed distribution version, or 'unresolved'."""
    try:
        return metadata.version(dist_name)
    except metadata.PackageNotFoundError:
        return "unresolved"


def _dep_name(spec: str) -> str:
    """Extract the distribution name from a PEP 508 requirement string."""
    for sep in (">=", "<=", "==", "~=", "!=", ">", "<", ";", " ", "["):
        if sep in spec:
            return spec.split(sep, 1)[0].strip()
    return spec.strip()


def main() -> int:
    """Emit the CycloneDX document on stdout."""
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    version = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()

    components: list[dict[str, object]] = []

    runtime = data.get("project", {}).get("dependencies", [])
    for spec in runtime:
        name = _dep_name(spec)
        components.append(
            {
                "type": "library",
                "name": name,
                "version": _version_of(name),
                "scope": "required",
                "purl": f"pkg:pypi/{name}",
            }
        )

    build = data.get("build-system", {}).get("requires", [])
    for spec in build:
        name = _dep_name(spec)
        components.append(
            {
                "type": "library",
                "name": name,
                "version": _version_of(name),
                "scope": "required",
                "purl": f"pkg:pypi/{name}",
            }
        )

    dev = data.get("dependency-groups", {}).get("dev", [])
    for spec in dev:
        name = _dep_name(spec)
        components.append(
            {
                "type": "library",
                "name": name,
                "version": _version_of(name),
                "scope": "excluded",
                "purl": f"pkg:pypi/{name}",
            }
        )

    doc = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": "urn:uuid:flowsemantics-python-sbom",
        "version": 1,
        "metadata": {
            "timestamp": "2026-11-22T00:00:00Z",
            "tools": [{"name": "scripts/sbom.py", "version": "1.0"}],
            "component": {
                "type": "application",
                "name": "flow-semantics",
                "version": version,
            },
        },
        "components": components,
    }
    json.dump(doc, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
