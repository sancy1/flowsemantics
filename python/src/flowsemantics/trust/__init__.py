"""flowsemantics.trust - Trust layer: replay, shadow, explain helpers.

Layer:      Trust
Module:     flowsemantics.trust
Since:      0.3.0
Implements: SPEC.md section 12
Depends on: flowsemantics.configuration, flowsemantics.execution
Used by:    consumers needing replay/shadow/audit capabilities
See also:   SPEC.md sections 12.5-12.7, 9.5
"""

from __future__ import annotations

from flowsemantics.trust.replay import (
    ReplayError,
    ReplayMode,
    ReplayRecord,
    ReplayResult,
    record,
    replay,
    sign,
)
from flowsemantics.trust.shadow import ShadowEntry, ShadowReport, shadow

__all__: list[str] = [
    "ReplayError",
    "ReplayMode",
    "ReplayRecord",
    "ReplayResult",
    "ShadowEntry",
    "ShadowReport",
    "record",
    "replay",
    "shadow",
    "sign",
]
