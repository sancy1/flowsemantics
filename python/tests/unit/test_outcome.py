"""Unit tests for the canonical outcome model (SPEC.md section 3)."""

from __future__ import annotations

import datetime
from dataclasses import FrozenInstanceError

import pytest

from flowsemantics import (
    DecisionStatus,
    Effect,
    ExecutionStatus,
    FinalizationInfo,
    FlowOutcome,
    InterruptionInfo,
    RecoveryInfo,
)


def test_execution_status_members() -> None:
    assert {m.name for m in ExecutionStatus} == {
        "COMPLETED",
        "FAILED",
        "CANCELLED",
        "TIMED_OUT",
    }


def test_decision_status_members() -> None:
    assert {m.name for m in DecisionStatus} == {"APPROVED", "REJECTED", "NO_MATCH"}


def test_status_values_are_spec_strings() -> None:
    assert ExecutionStatus.COMPLETED.value == "completed"
    assert DecisionStatus.NO_MATCH.value == "no_match"


def test_flow_outcome_is_frozen() -> None:
    outcome = FlowOutcome(execution_status=ExecutionStatus.COMPLETED)
    with pytest.raises(FrozenInstanceError):
        outcome.value = 1  # type: ignore[misc]


def test_interruption_info_fields() -> None:
    ts = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    info = InterruptionInfo(kind="cancelled", source="user", timestamp=ts)
    assert info.kind == "cancelled"
    assert info.deadline is None


def test_recovery_info_fields() -> None:
    ts = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    info = RecoveryInfo(
        original_exception=ValueError("x"),
        handler_rule_id="catch-1",
        recovered_at=ts,
    )
    assert info.handler_rule_id == "catch-1"


def test_finalization_info_defaults() -> None:
    info = FinalizationInfo(is_clean=True)
    assert info.cleanup_exceptions == ()
    assert info.cleanup_budget_exceeded is False


def test_effect_is_data() -> None:
    effect = Effect(name="notify", payload={"to": "ops"})
    assert effect.name == "notify"
    assert effect.payload == {"to": "ops"}


def test_outcome_defaults() -> None:
    outcome = FlowOutcome(execution_status=ExecutionStatus.COMPLETED)
    assert outcome.decision_status is None
    assert outcome.value is None
    assert outcome.recovery is None
    assert outcome.interruption is None
    assert outcome.finalization is None
    assert outcome.primary_exception is None
    assert outcome.secondary_exceptions == ()
    assert outcome.effects == ()
    assert outcome.trace is None
