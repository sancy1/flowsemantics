"""flowsemantics.testing - Shipped pytest plugin and assertion helpers (Phase 1.8).

Layer:      Tests
Module:     flowsemantics.testing
Since:      0.0.0
Implements: n/a (subpackage marker)
Depends on: n/a (empty in Phase 0.0; pytest in Phase 1.8)
Used by:    consumers who want the FlowSemantics pytest plugin
See also:   docs/getting-started.md (Phase 1), pytest.ini markers

Notes:
  - __all__ is empty in Phase 0.0. It grows in Phase 1.8 when the plugin
    and assertion helpers are implemented.
  - The plugin registers markers (conformance, flowsemantics_scenario,
    slow, fuzz) and provides fixtures for downstream tests.
  - pytest is a development dependency of the *test suite*, not of this
    subpackage. This subpackage itself has no runtime dependency.
"""

from __future__ import annotations

__all__: list[str] = []

