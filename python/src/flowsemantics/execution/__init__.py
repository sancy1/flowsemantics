"""flowsemantics.execution - Outcome model, context, clocks, executor.

Layer:      Domain
Module:     flowsemantics.execution
Since:      0.0.0
Implements: SPEC.md sections 3, 4.1.3, 6.2, 7
Depends on: flowsemantics.execution.{clock,context,outcome}
Used by:    parent package; populated from Phase 1.0
See also:   SPEC.md sections 3, 6, 7

Notes:
  - __all__ grows as features are implemented. Currently exports the
    canonical outcome types (SPEC.md section 3) and the clock/context
    primitives (sections 4.1.3, 6.2).
"""

from __future__ import annotations

from flowsemantics.execution.clock import Clock, FakeClock, SystemClock
from flowsemantics.execution.context import FlowContext
from flowsemantics.execution.outcome import (
    DecisionStatus,
    Effect,
    ExecutionStatus,
    FinalizationInfo,
    FlowOutcome,
    InterruptionInfo,
    RecoveryInfo,
)
from flowsemantics.execution.trace import (
    EVENT_TYPES,
    REASONS,
    ExecutionTrace,
    TraceEvent,
    TraceRecorder,
)

__all__: list[str] = [
    "EVENT_TYPES",
    "REASONS",
    "Clock",
    "DecisionStatus",
    "Effect",
    "ExecutionStatus",
    "ExecutionTrace",
    "FakeClock",
    "FinalizationInfo",
    "FlowContext",
    "FlowOutcome",
    "InterruptionInfo",
    "RecoveryInfo",
    "SystemClock",
    "TraceEvent",
    "TraceRecorder",
]
