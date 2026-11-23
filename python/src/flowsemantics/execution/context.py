"""flowsemantics.execution.context - Per-invocation execution context.

Layer:      Domain
Module:     flowsemantics.execution.context
Since:      0.1.0
Implements: SPEC.md section 4.1.3 (isolated execution context), section 6.2
Depends on: flowsemantics.execution.clock
Used by:    FlowContract.execute / execute_async
See also:   SPEC.md section 4.2 (qualified thread safety)

Notes:
  - A fresh FlowContext is created per invocation. No mutable state is shared
    between invocations of the same contract (SPEC.md section 4.1.3).
  - The context carries the input, the injected clock, and (from Phase 2.3)
    the cancellation token. User callbacks receive the input, not the whole
    context, so they cannot accidentally mutate shared state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from flowsemantics.execution.clock import Clock, SystemClock


@dataclass
class FlowContext:
    """Isolated per-invocation state for one flow execution.

    Attributes:
        input: The input value passed to execute().
        clock: The injected clock. Defaults to SystemClock when the caller
            does not supply one; deterministic replay MUST inject FakeClock.
        state: Per-invocation mutable state for engine bookkeeping. Never
            shared between invocations.
    """

    input: Any
    clock: Clock = field(default_factory=SystemClock)
    state: dict[str, Any] = field(default_factory=dict)


__all__: list[str] = [
    "FlowContext",
]
