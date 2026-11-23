"""flowsemantics.execution.outcome - Canonical outcome model (SPEC.md section 3).

Layer:      Domain
Module:     flowsemantics.execution.outcome
Since:      0.1.0
Implements: SPEC.md sections 3.1-3.8 (corrected v5 outcome model)
Depends on: stdlib only (dataclasses, enum, datetime)
Used by:    execution engine, trace, simulation, conformance runner
See also:   SPEC.md section 3, section 7

Notes:
  - The v5 corrections are encoded here: interruption is separate from
    recovery (B5), is_clean is finalization metadata not a status (B6),
    secondary_exceptions includes cleanup exceptions even when the primary
    succeeded (B7).
  - All dataclasses are frozen: a FlowOutcome MUST be immutable after
    construction (SPEC.md section 3.6).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from flowsemantics.execution.trace import ExecutionTrace


class ExecutionStatus(StrEnum):
    """What happened while running. Exactly four members (SPEC 3.1)."""

    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class DecisionStatus(StrEnum):
    """What the flow concluded. Exactly three members (SPEC 3.2)."""

    APPROVED = "approved"
    REJECTED = "rejected"
    NO_MATCH = "no_match"


@dataclass(frozen=True)
class InterruptionInfo:
    """Cancellation/timeout metadata. Never an exception (SPEC 3.3, B5)."""

    kind: Literal["cancelled", "timed_out"]
    source: str
    timestamp: datetime.datetime
    deadline: datetime.datetime | None = None


@dataclass(frozen=True)
class RecoveryInfo:
    """Exception-recovery metadata only (SPEC 3.4, O1)."""

    original_exception: BaseException
    handler_rule_id: str
    recovered_at: datetime.datetime


@dataclass(frozen=True)
class FinalizationInfo:
    """Finalization metadata including is_clean (SPEC 3.5, B6, B8)."""

    is_clean: bool
    cleanup_exceptions: tuple[BaseException, ...] = ()
    cleanup_budget_used: datetime.timedelta = datetime.timedelta(0)
    cleanup_budget_exceeded: bool = False


@dataclass(frozen=True)
class Effect:
    """A proposed side effect. Data, not code (SPEC 3.7)."""

    name: str
    payload: Any = None


@dataclass(frozen=True)
class FlowOutcome:
    """The structured result of one execution (SPEC 3.6).

    Invariants enforced by construction in the engine:
      - decision_status is absent unless execution_status is COMPLETED.
      - primary_exception is absent unless execution_status is FAILED.
      - interruption is populated only for CANCELLED and TIMED_OUT.
      - recovery is populated only when an exception was recovered.
      - secondary_exceptions includes cleanup exceptions even when the
        primary execution succeeded (B7).
    """

    execution_status: ExecutionStatus
    decision_status: DecisionStatus | None = None
    value: Any = None
    recovery: RecoveryInfo | None = None
    interruption: InterruptionInfo | None = None
    finalization: FinalizationInfo | None = None
    primary_exception: BaseException | None = None
    secondary_exceptions: tuple[BaseException, ...] = ()
    effects: tuple[Effect, ...] = ()
    trace: ExecutionTrace | None = field(default=None, compare=False)


__all__: list[str] = [
    "DecisionStatus",
    "Effect",
    "ExecutionStatus",
    "FinalizationInfo",
    "FlowOutcome",
    "InterruptionInfo",
    "RecoveryInfo",
]
