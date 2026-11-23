"""flowsemantics.errors - Exception hierarchy for FlowSemantics.

Layer:      Contracts
Module:     flowsemantics.errors
Since:      0.1.0
Implements: SPEC.md section 5.2 naming (StructureError, PortabilityError,
            EvaluationError, FinalizationBudgetExceeded)
Depends on: stdlib only
Used by:    configuration, execution, finalization, portable
See also:   SPEC.md sections 4.3, 10.9, 11.4, 16.7

Notes:
  - All library-raised exceptions derive from FlowSemanticsError so callers
    can distinguish library contract violations from application exceptions.
  - These are NOT outcome exceptions. An exception raised inside a user
    condition or action is an application exception and is handled by the
    Section 11 catch rules, never by this hierarchy.
"""

from __future__ import annotations


class FlowSemanticsError(Exception):
    """Base class for every exception raised by the FlowSemantics library."""


class StructureError(FlowSemanticsError):
    """Raised by compile() when the flow structure is invalid (SPEC 4.3)."""


class PortabilityError(FlowSemanticsError):
    """Raised by export_portable() on a NATIVE contract (SPEC 4.4)."""


class EvaluationError(FlowSemanticsError):
    """Raised for an evaluation-time failure not otherwise classified."""


class FinalizationBudgetExceeded(FlowSemanticsError):  # noqa: N818 - name locked by SPEC.md section 5.2
    """Recorded when cleanup exceeds its WithFinallyTimeout budget (SPEC 16.7)."""


class AsyncOnlyContractError(FlowSemanticsError):
    """Raised when execute() is called on an async-only contract (SPEC 11.7)."""


__all__: list[str] = [
    "AsyncOnlyContractError",
    "EvaluationError",
    "FinalizationBudgetExceeded",
    "FlowSemanticsError",
    "PortabilityError",
    "StructureError",
]
