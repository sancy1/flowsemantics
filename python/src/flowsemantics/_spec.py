"""Specification version constant.

SPEC.md is versioned independently of the package version (VERSION file).
Vectors declare the spec_version they target; the conformance runner uses
this constant to decide compatibility (runner-protocol.md).
"""

from __future__ import annotations

SPEC_VERSION = "0.1.0"

__all__: list[str] = ["SPEC_VERSION"]
