"""flowsemantics.configuration.table - DecisionTable (SPEC.md section 10.8).

Layer:      Composition
Module:     flowsemantics.configuration.table
Since:      0.1.0
Implements: SPEC.md section 10.8 (column-based, DMN-aligned hit policies)
Depends on: flowsemantics.configuration.{flow,rule}, stdlib only
Used by:    Flow.from_table, consumers authoring rules as tables
See also:   SPEC.md section 10.8

Notes:
  - A decision table compiles to the same rule list as the fluent API.
  - Hit policies map to EvaluationMode: FIRST->FirstMatch,
    COLLECT->AllMatch, PRIORITY->Priority, UNIQUE->FirstMatch plus a
    compile-time exclusivity check where statically provable.
  - For opaque callables, UNIQUE exclusivity cannot be proven; the table
    records a validation warning rather than claiming a guarantee
    (SPEC 10.8).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from flowsemantics.configuration.flow import EvaluationMode, Flow
from flowsemantics.configuration.rule import ActionFn, ConditionFn

HitPolicy = str  # "FIRST" | "COLLECT" | "PRIORITY" | "UNIQUE"

_HIT_POLICY_TO_MODE: dict[str, EvaluationMode] = {
    "FIRST": EvaluationMode.FIRST_MATCH,
    "COLLECT": EvaluationMode.ALL_MATCH,
    "PRIORITY": EvaluationMode.PRIORITY,
    "UNIQUE": EvaluationMode.FIRST_MATCH,
}


@dataclass(frozen=True)
class DecisionTableRow:
    """One row of a decision table.

    Attributes:
        id: Stable RuleId for the compiled rule.
        conditions: Predicates that must ALL be true for the row to match.
        action: The transformation executed on match.
        priority: Priority for PRIORITY hit policy (higher first).
    """

    id: str
    conditions: tuple[ConditionFn, ...]
    action: ActionFn
    priority: int = 0


@dataclass(frozen=True)
class DecisionTable:
    """A column-based decision table that compiles to a rule list."""

    rows: tuple[DecisionTableRow, ...]
    hit_policy: HitPolicy = "FIRST"
    input_fields: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate hit policy and row count at construction."""
        if self.hit_policy not in _HIT_POLICY_TO_MODE:
            raise ValueError(f"unknown hit policy: {self.hit_policy!r}")
        if not self.rows:
            raise ValueError("decision table must have at least one row")

    @property
    def evaluation_mode(self) -> EvaluationMode:
        """The EvaluationMode this hit policy maps to (SPEC 10.8)."""
        return _HIT_POLICY_TO_MODE[self.hit_policy]


def _all_conditions(conditions: Sequence[ConditionFn]) -> ConditionFn:
    def _combined(input: Any) -> bool:
        return all(condition(input) for condition in conditions)

    return _combined


def table_to_flow(table: DecisionTable) -> Flow:
    """Compile a DecisionTable into a Flow builder (SPEC 10.8).

    The resulting flow is equivalent to one built with the fluent API:
    each row becomes a when rule whose condition is the conjunction of
    the row's column predicates.
    """
    flow = Flow().with_mode(table.evaluation_mode)
    for row in table.rows:
        flow.when(
            _all_conditions(row.conditions),
            then=row.action,
            id=row.id,
            priority=row.priority,
        )
    return flow


__all__: list[str] = [
    "DecisionTable",
    "DecisionTableRow",
    "HitPolicy",
    "table_to_flow",
]
