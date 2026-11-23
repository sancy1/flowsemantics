"""flowsemantics.execution.trace - ExecutionTrace, TraceEvent, TraceRecorder.

Layer:      Domain
Module:     flowsemantics.execution.trace
Since:      0.3.0
Implements: SPEC.md sections 3.8, 12.1, 12.3
Depends on: stdlib only
Used by:    FlowContract.try_execute (when tracing enabled), explain()
See also:   SPEC.md sections 3.8, 12.1-12.4

Notes:
  - The event-type vocabulary is closed (SPEC 12.1): exactly the 22 types
    listed there. TraceRecorder.emit validates against it.
  - reason values are a closed enumeration (SPEC 12.1.1).
  - Tracing is zero-cost when disabled: no recorder is created and no
    clock reads happen (SPEC 12.3).
  - Trace events MUST NOT contain input values, secrets, or exception
    messages (SPEC 12.2).
"""

from __future__ import annotations

import datetime
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# Canonical event vocabulary (SPEC 12.1) - closed set, no others.
EVENT_TYPES: frozenset[str] = frozenset(
    {
        "condition_evaluated",
        "condition_raised",
        "guard_evaluated",
        "action_executed",
        "action_raised",
        "catch_matched",
        "catch_predicate_evaluated",
        "catch_predicate_raised",
        "catch_handled",
        "catch_declined",
        "rethrow_reached",
        "hook_invoked",
        "hook_raised",
        "effect_proposed",
        "skipped_by_short_circuit",
        "skipped_by_mode",
        "finally_started",
        "finally_completed",
        "finally_raised",
        "cancelled_observed",
        "timed_out_observed",
        "rule_skipped",
    }
)

# Closed reason enumeration (SPEC 12.1.1).
REASONS: frozenset[str] = frozenset(
    {
        "condition_false",
        "guard_blocked",
        "not_effective",
        "earlier_match",
        "mode_excluded",
    }
)


@dataclass(frozen=True)
class TraceEvent:
    """A single trace event (SPEC 3.8)."""

    type: str
    rule_id: str | None = None
    timestamp: datetime.datetime | None = None
    reason: str | None = None
    contract_version: str | None = None
    diagnostics: dict[str, Any] | None = None


@dataclass(frozen=True)
class ExecutionTrace:
    """Ordered trace events plus contract version (SPEC 3.8)."""

    contract_version: str
    events: tuple[TraceEvent, ...] = field(default_factory=tuple)


class TraceRecorder:
    """Collects trace events during one execution (SPEC 12.1, 12.3).

    Created only when tracing is enabled; when disabled, no recorder
    exists and evaluation pays zero tracing cost.
    """

    __slots__ = ("_contract_version", "_diagnostic_hook", "_events")

    def __init__(
        self,
        contract_version: str,
        diagnostic_hook: Callable[[TraceEvent], dict[str, Any] | None] | None = None,
    ) -> None:
        """Create an empty recorder for the given contract version.

        diagnostic_hook is the application-supplied redaction-aware hook
        (SPEC 12.2): it receives each event and may return a dict of
        additional diagnostic fields. The library defers entirely to the
        application's policy; absent a hook, no diagnostic data is added.
        """
        self._contract_version = contract_version
        self._diagnostic_hook = diagnostic_hook
        self._events: list[TraceEvent] = []

    def emit(
        self,
        event_type: str,
        *,
        rule_id: str | None = None,
        timestamp: datetime.datetime | None = None,
        reason: str | None = None,
    ) -> None:
        """Append an event. Validates type and reason against the closed sets."""
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unknown trace event type: {event_type!r}")
        if reason is not None and reason not in REASONS:
            raise ValueError(f"unknown trace reason: {reason!r}")
        event = TraceEvent(
            type=event_type,
            rule_id=rule_id,
            timestamp=timestamp,
            reason=reason,
            contract_version=self._contract_version,
        )
        if self._diagnostic_hook is not None:
            extra = self._diagnostic_hook(event)
            if extra:
                event = TraceEvent(
                    type=event.type,
                    rule_id=event.rule_id,
                    timestamp=event.timestamp,
                    reason=event.reason,
                    contract_version=event.contract_version,
                    diagnostics=dict(extra),
                )
        self._events.append(event)

    def build(self) -> ExecutionTrace:
        """Produce the immutable ExecutionTrace."""
        return ExecutionTrace(
            contract_version=self._contract_version,
            events=tuple(self._events),
        )


__all__: list[str] = [
    "EVENT_TYPES",
    "REASONS",
    "ExecutionTrace",
    "TraceEvent",
    "TraceRecorder",
]
