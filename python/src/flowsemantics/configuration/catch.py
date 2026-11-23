"""flowsemantics.configuration.catch - CatchRule (SPEC.md sections 11.1-11.4).

Layer:      Composition
Module:     flowsemantics.configuration.catch
Since:      0.2.0
Implements: SPEC.md sections 11.1 (catch), 11.2 (catch_when),
            11.3 (catch_any), 11.4 (rethrow)
Depends on: stdlib only
Used by:    Flow builder, FlowContract, exception router
See also:   SPEC.md section 11, section 7.3.1

Notes:
  - Catch evaluation is ordered: the first matching catch wins.
  - catch_any MUST be registered after all typed catch/catch_when rules;
    compile() enforces this (SPEC 11.3, 4.3).
  - rethrow stops catch evaluation and propagates the current exception.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

CatchKind = Literal["typed", "when", "any", "rethrow"]

ExceptionPredicate = Callable[[Any, BaseException], bool]
ExceptionHandler = Callable[[Any, BaseException], Any]


@dataclass(frozen=True)
class CatchRule:
    """One exception handler in the catch chain (SPEC 11.1-11.4).

    Attributes:
        kind: "typed" (isinstance match), "when" (isinstance + predicate),
            "any" (matches any Exception), or "rethrow" (always propagates).
        exc_type: Declared exception type for typed/when kinds.
        predicate: Optional predicate for "when" kind; receives
            (input, exception) and must return bool.
        handler: Receives (input, exception), returns the outcome value.
            Absent for "rethrow".
        id: Optional stable identifier recorded in RecoveryInfo.
    """

    kind: CatchKind
    exc_type: type[Exception] | None = None
    predicate: ExceptionPredicate | None = None
    handler: ExceptionHandler | None = None
    id: str | None = None


__all__: list[str] = [
    "CatchKind",
    "CatchRule",
    "ExceptionHandler",
    "ExceptionPredicate",
]
