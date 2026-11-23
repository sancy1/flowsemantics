"""flowsemantics.trust.replay - Replay records and four replay operations.

Layer:      Trust
Module:     flowsemantics.trust.replay
Since:      0.3.0
Implements: SPEC.md sections 12.6, 12.10, 9.5
Depends on: flowsemantics.configuration.flow, flowsemantics.execution.*,
            stdlib (hmac, hashlib, json, datetime)
Used by:    audit, regression testing, decision forensics
See also:   SPEC.md sections 12.6, 9.5, 12.10

Notes:
  - Four distinct operations, never conflated (SPEC 12.6):
    SIMULATION (re-evaluate, no effects), HISTORICAL (return recorded
    data), DECISION (re-evaluate + semantic comparison), EFFECTS
    (apply recorded effects via authorized executor; never default).
  - Replay guarantee is SEMANTIC equivalence, not bit-for-bit (A5).
  - Fail closed on spec_version or contract_version mismatch (9.5).
  - Integrity: HMAC-SHA256 over a canonical JSON payload. An unkeyed
    hash alone is NOT sufficient (12.6); integrity is optional on the
    record but verified whenever present.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from flowsemantics._spec import SPEC_VERSION
from flowsemantics.configuration.flow import FlowContract
from flowsemantics.errors import FlowSemanticsError
from flowsemantics.execution.clock import FakeClock
from flowsemantics.execution.outcome import FlowOutcome
from flowsemantics.execution.trace import ExecutionTrace


class ReplayError(FlowSemanticsError):
    """Raised when a replay record cannot be safely replayed."""


class ReplayMode(StrEnum):
    """The four replay operations (SPEC 12.6)."""

    SIMULATION = "simulation"
    HISTORICAL = "historical"
    DECISION = "decision"
    EFFECTS = "effects"


@dataclass(frozen=True)
class ReplayRecord:
    """A recorded decision tuple (SPEC 12.6, 12.10).

    Attributes:
        spec_version: SPEC.md version that produced the record.
        contract_version: Structural hash of the FlowContract.
        input: The recorded input (application data; handle per 12.2).
        clock_wall: Recorded wall-clock value.
        clock_monotonic: Recorded monotonic value.
        outcome: The recorded FlowOutcome.
        trace: The recorded trace, if collected.
        effects: Recorded proposed effects.
        integrity: Optional HMAC-SHA256 hex digest (see sign()).
    """

    spec_version: str
    contract_version: str
    input: Any
    clock_wall: datetime.datetime
    clock_monotonic: float
    outcome: FlowOutcome
    trace: ExecutionTrace | None = None
    effects: tuple[Any, ...] = ()
    integrity: str | None = None


@dataclass(frozen=True)
class ReplayResult:
    """Result of a replay operation."""

    mode: ReplayMode
    outcome: FlowOutcome | None = None
    equivalent: bool | None = None
    effects_applied: int = 0


def _canonical_payload(record: ReplayRecord) -> str:
    """Canonical JSON for integrity signing (input via repr fallback)."""
    payload = {
        "spec_version": record.spec_version,
        "contract_version": record.contract_version,
        "input": record.input,
        "clock_wall": record.clock_wall.isoformat(),
        "clock_monotonic": record.clock_monotonic,
        "outcome": {
            "execution_status": str(record.outcome.execution_status),
            "decision_status": (
                str(record.outcome.decision_status)
                if record.outcome.decision_status is not None
                else None
            ),
            "value": record.outcome.value,
            "has_recovery": record.outcome.recovery is not None,
            "interruption_kind": (
                record.outcome.interruption.kind
                if record.outcome.interruption is not None
                else None
            ),
        },
        "effects": [repr(e) for e in record.effects],
    }
    return json.dumps(payload, sort_keys=True, default=repr)


def sign(record: ReplayRecord, key: bytes) -> ReplayRecord:
    """Return a copy of the record with an HMAC-SHA256 integrity tag."""
    digest = hmac.new(key, _canonical_payload(record).encode("utf-8"), hashlib.sha256).hexdigest()
    return ReplayRecord(
        spec_version=record.spec_version,
        contract_version=record.contract_version,
        input=record.input,
        clock_wall=record.clock_wall,
        clock_monotonic=record.clock_monotonic,
        outcome=record.outcome,
        trace=record.trace,
        effects=record.effects,
        integrity=digest,
    )


def record(contract: FlowContract, input: Any, *, clock: Any | None = None) -> ReplayRecord:
    """Execute with tracing and capture a ReplayRecord (SPEC 12.6)."""
    clk = clock if clock is not None else contract.clock
    outcome = contract.try_execute(input, clock=clk, trace=True)
    return ReplayRecord(
        spec_version=SPEC_VERSION,
        contract_version=contract.contract_version,
        input=input,
        clock_wall=clk.wall(),
        clock_monotonic=clk.monotonic(),
        outcome=outcome,
        trace=outcome.trace,
        effects=outcome.effects,
    )


def _verify_integrity(record: ReplayRecord, key: bytes | None) -> None:
    if record.integrity is None:
        return
    if key is None:
        raise ReplayError("record carries an integrity tag; an integrity_key is required")
    expected = hmac.new(key, _canonical_payload(record).encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, record.integrity):
        raise ReplayError("replay record integrity check failed")


def _check_versions(record: ReplayRecord, contract: FlowContract) -> None:
    if record.spec_version != SPEC_VERSION:
        raise ReplayError(
            f"record spec_version {record.spec_version!r} does not match "
            f"current {SPEC_VERSION!r}; replay fails closed (SPEC 9.5)"
        )
    if record.contract_version != contract.contract_version:
        raise ReplayError(
            "record contract_version does not match the current contract; "
            "replay fails closed (SPEC 12.6)"
        )


def _reconstruct_clock(record: ReplayRecord) -> FakeClock:
    clock = FakeClock()
    clock.set_wall(record.clock_wall)
    clock.advance(record.clock_monotonic)
    return clock


def _semantically_equivalent(a: FlowOutcome, b: FlowOutcome) -> bool:
    """Semantic equivalence per SPEC 12.6 (A5).

    Compares status, decision, value, recovery presence, interruption kind.
    """
    if a.execution_status is not b.execution_status:
        return False
    if a.decision_status is not b.decision_status:
        return False
    if a.value != b.value:
        return False
    if (a.recovery is None) != (b.recovery is None):
        return False
    if (
        a.recovery is not None
        and b.recovery is not None
        and a.recovery.handler_rule_id != b.recovery.handler_rule_id
    ):
        return False
    a_kind = a.interruption.kind if a.interruption else None
    b_kind = b.interruption.kind if b.interruption else None
    return a_kind == b_kind


def replay(
    record: ReplayRecord,
    contract: FlowContract,
    *,
    mode: ReplayMode = ReplayMode.SIMULATION,
    integrity_key: bytes | None = None,
    effect_executor: Any | None = None,
    authorize_effects: bool = False,
) -> ReplayResult:
    """Replay a recorded decision (SPEC 12.6).

    Args:
        record: The recorded tuple.
        contract: The current FlowContract to replay against.
        mode: One of the four replay operations.
        integrity_key: HMAC key when the record is integrity-tagged.
        effect_executor: Callable(Effect) for EFFECTS mode only.
        authorize_effects: Must be True for EFFECTS mode; never default.
    """
    _verify_integrity(record, integrity_key)
    _check_versions(record, contract)

    if mode is ReplayMode.HISTORICAL:
        return ReplayResult(mode=mode, outcome=record.outcome)

    if mode in (ReplayMode.SIMULATION, ReplayMode.DECISION):
        clock = _reconstruct_clock(record)
        outcome = contract.simulate(record.input, clock=clock)
        equivalent = _semantically_equivalent(outcome, record.outcome)
        return ReplayResult(mode=mode, outcome=outcome, equivalent=equivalent)

    if mode is ReplayMode.EFFECTS:
        if not authorize_effects:
            raise ReplayError(
                "effect re-execution requires explicit authorization (authorize_effects=True)"
            )
        if effect_executor is None:
            raise ReplayError("EFFECTS mode requires an effect_executor")
        applied = 0
        for effect in record.effects:
            effect_executor(effect)
            applied += 1
        return ReplayResult(mode=mode, effects_applied=applied)

    raise ReplayError(f"unknown replay mode: {mode!r}")


__all__: list[str] = [
    "ReplayError",
    "ReplayMode",
    "ReplayRecord",
    "ReplayResult",
    "record",
    "replay",
    "sign",
]
