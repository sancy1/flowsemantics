"""flowsemantics.trust.shadow - Shadow evaluation (SPEC 12.7).

Layer:      Trust
Module:     flowsemantics.trust.shadow
Since:      0.3.0
Implements: SPEC.md section 12.7
Depends on: flowsemantics.configuration.flow, flowsemantics.execution.outcome
Used by:    pre-deployment candidate comparison
See also:   SPEC.md section 12.7

Notes:
  - Shadow evaluation NEVER applies effects: both flows run via
    simulate(), so hooks and finalizers are suppressed (12.5).
  - Deterministic: same inputs + contracts + clock -> same report.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from flowsemantics.configuration.flow import FlowContract
from flowsemantics.execution.clock import Clock
from flowsemantics.execution.outcome import FlowOutcome


@dataclass(frozen=True)
class ShadowEntry:
    """One input's current-vs-candidate comparison."""

    index: int
    input: Any
    current: FlowOutcome
    candidate: FlowOutcome
    differs: bool
    differing_fields: tuple[str, ...]


@dataclass(frozen=True)
class ShadowReport:
    """Aggregate shadow comparison report (SPEC 12.7)."""

    entries: tuple[ShadowEntry, ...]
    total: int
    differences: int


def _diff_fields(a: FlowOutcome, b: FlowOutcome) -> tuple[str, ...]:
    fields: list[str] = []
    if a.execution_status is not b.execution_status:
        fields.append("execution_status")
    if a.decision_status is not b.decision_status:
        fields.append("decision_status")
    if a.value != b.value:
        fields.append("value")
    if (a.recovery is None) != (b.recovery is None):
        fields.append("recovery")
    a_kind = a.interruption.kind if a.interruption else None
    b_kind = b.interruption.kind if b.interruption else None
    if a_kind != b_kind:
        fields.append("interruption")
    return tuple(fields)


def shadow(
    current: FlowContract,
    candidate: FlowContract,
    inputs: Iterable[Any],
    *,
    clock: Clock | None = None,
) -> ShadowReport:
    """Compare a candidate flow against the current flow (SPEC 12.7).

    Both flows are simulated (no effects, no hooks, no finalizers).
    """
    entries: list[ShadowEntry] = []
    for index, inp in enumerate(inputs):
        current_outcome = current.simulate(inp, clock=clock)
        candidate_outcome = candidate.simulate(inp, clock=clock)
        fields = _diff_fields(current_outcome, candidate_outcome)
        entries.append(
            ShadowEntry(
                index=index,
                input=inp,
                current=current_outcome,
                candidate=candidate_outcome,
                differs=bool(fields),
                differing_fields=fields,
            )
        )
    return ShadowReport(
        entries=tuple(entries),
        total=len(entries),
        differences=sum(1 for e in entries if e.differs),
    )


__all__: list[str] = [
    "ShadowEntry",
    "ShadowReport",
    "shadow",
]
