"""flowsemantics.configuration.rule - RuleId and Rule (SPEC.md sections 2.1, 10.1).

Layer:      Composition
Module:     flowsemantics.configuration.rule
Since:      0.1.0
Implements: SPEC.md section 10.1 (rule is a 4-tuple plus identity)
Depends on: stdlib only
Used by:    Flow builder, FlowContract, conformance runner
See also:   SPEC.md section 10

Notes:
  - RuleId is readonly and has implicit string conversion via __str__.
  - A Rule is immutable once registered: the builder stores it in a tuple
    inside the compiled FlowContract.
"""

from __future__ import annotations

import datetime
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from flowsemantics.execution.outcome import Effect

RuleKind = Literal["when", "when_not", "then"]

ConditionFn = Callable[[Any], bool | Awaitable[bool]]
GuardFn = Callable[[Any], bool | Awaitable[bool]]
ActionFn = Callable[..., Any]


@dataclass(frozen=True)
class RuleId:
    """Stable, readonly rule identity with implicit string conversion.

    Feature 8 of the v5 baseline. The value is validated non-empty at
    construction; compile() additionally enforces uniqueness (SPEC 4.3).
    """

    value: str

    def __post_init__(self) -> None:
        """Validate the RuleId value is non-empty."""
        if not self.value:
            raise ValueError("RuleId must be non-empty")

    def __str__(self) -> str:
        """Return the underlying string value (implicit string conversion)."""
        return self.value


@dataclass(frozen=True)
class Rule:
    """One rule in a flow: identity, kind, condition, guard, action.

    kind is "when" (match on true), "when_not" (match on false), or
    "then" (sequential stage; condition is None and action receives
    (input, previous_output)).
    """

    id: RuleId
    kind: RuleKind
    condition: ConditionFn | None
    guard: GuardFn | None
    action: ActionFn
    priority: int = 0
    effective_from: datetime.datetime | None = None
    effective_until: datetime.datetime | None = None
    effects: tuple[Effect, ...] = ()


__all__: list[str] = [
    "ActionFn",
    "ConditionFn",
    "Effect",
    "GuardFn",
    "Rule",
    "RuleId",
    "RuleKind",
]
