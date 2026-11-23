"""Conformance tests: one test per SPEC.md section (Phase 0.5+).

Layer:      Tests
Module:     tests.conformance
Since:      0.0.0
Implements: n/a (test package marker)
Depends on: n/a
Used by:    pytest discovery; conformance.yml
See also:   conformance/runner-protocol.md, spec/vector.schema.json

Notes:
  - Conformance tests verify normative SPEC.md claims via language-agnostic vectors.
  - Each test file names the SPEC section it proves (test_spec_retry, test_spec_circuit, etc.).
  - Populated in Phase 0.5 onward; empty in Phase 0.0.
"""

from __future__ import annotations

__all__: list[str] = []

