"""flowsemantics.testing.conformance - Language-agnostic conformance runner.

Layer:      Tests
Module:     flowsemantics.testing.conformance
Since:      0.1.0
Implements: conformance/runner-protocol.md, spec/fixtures.md,
            spec/vector.schema.json
Depends on: flowsemantics (public API), stdlib only
Used by:    python -m flowsemantics.testing.conformance.runner
See also:   SPEC.md section 14.3, 14.4

Notes:
  - This subpackage is exempt from the zero-third-party audit rule
    (ALLOWLISTED_SOURCE_DIRS includes "testing"), but it uses stdlib only
    anyway.
  - The runner executes vectors through the real public API. It never
    reaches into private modules.
"""

from __future__ import annotations

__all__: list[str] = []
