"""flowsemantics.configuration.finalization - FinallyContext and policies.

Layer:      Composition
Module:     flowsemantics.configuration.finalization
Since:      0.2.0
Implements: SPEC.md sections 11.8, 16.4, 16.7
Depends on: flowsemantics.execution.outcome, stdlib only
Used by:    Flow.finally_, FlowContract, finalization engine
See also:   SPEC.md sections 11.8, 16.4, 16.7

Notes:
  - Exactly three failure policies exist (SPEC 11.8.3): PreservePrimary
    (default), Attach, ReplacePrimary. No others.
  - is_clean is orthogonal to policy: false iff any finalizer raised,
    was cancelled, or exceeded its budget (SPEC 11.8.3, 3.5).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from flowsemantics.execution.outcome import ExecutionStatus, FlowOutcome


class FinallyFailurePolicy(StrEnum):
    """What happens to the primary outcome when cleanup fails (SPEC 16.4)."""

    PRESERVE_PRIMARY = "PreservePrimary"
    ATTACH = "Attach"
    REPLACE_PRIMARY = "ReplacePrimary"


@dataclass(frozen=True)
class FinallyCancellationToken:
    """Fresh per-finalizer cancellation token (SPEC 11.8.1, 11.8.5).

    Bounded by WithFinallyTimeout where configured. One finalizer
    cancelling its token MUST NOT cancel the tokens of the others.
    """

    cancelled: bool = False


@dataclass(frozen=True)
class FinallyContext:
    """Context passed to each finalizer (SPEC 11.8.1).

    Attributes:
        result: The sealed primary outcome.
        status: The ExecutionStatus of the primary outcome.
        value: The outcome value, read-only. Finally MUST NOT change it.
        exception: The primary exception, if any.
        context: The typed input from the flow.
        cancellation_token: A fresh token for this finalizer.
    """

    result: FlowOutcome
    status: ExecutionStatus
    value: Any
    exception: BaseException | None
    context: Any
    cancellation_token: FinallyCancellationToken


__all__: list[str] = [
    "FinallyCancellationToken",
    "FinallyContext",
    "FinallyFailurePolicy",
]
