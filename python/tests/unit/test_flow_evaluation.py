"""Unit tests for flow evaluation semantics (SPEC.md sections 7, 10)."""

from __future__ import annotations

from typing import Any

import pytest

from flowsemantics import (
    DecisionStatus,
    EvaluationMode,
    ExecutionStatus,
    Flow,
    StructureError,
)


def _const(value: Any) -> Any:
    return lambda _input: value


def _true(_input: Any) -> bool:
    return True


def _false(_input: Any) -> bool:
    return False


def _boom(_input: Any) -> bool:
    raise ValueError("condition exploded")


def _boom_action(_input: Any) -> Any:
    raise RuntimeError("action exploded")


# -- basic match / no-match -------------------------------------------------


def test_when_match_completed_approved() -> None:
    contract = Flow().when(_true, then=_const("yes"), id="r1").compile()
    outcome = contract.try_execute(None)
    assert outcome.execution_status is ExecutionStatus.COMPLETED
    assert outcome.decision_status is DecisionStatus.APPROVED
    assert outcome.value == "yes"


def test_when_no_match_no_fallback() -> None:
    contract = Flow().when(_false, then=_const("yes"), id="r1").compile()
    outcome = contract.try_execute(None)
    assert outcome.decision_status is DecisionStatus.NO_MATCH
    assert outcome.value is None


def test_when_not_inverts() -> None:
    contract = Flow().when_not(_false, then=_const("neg"), id="r1").compile()
    assert contract.try_execute(None).value == "neg"
    contract2 = Flow().when_not(_true, then=_const("neg"), id="r1").compile()
    assert contract2.try_execute(None).decision_status is DecisionStatus.NO_MATCH


def test_condition_receives_input() -> None:
    seen: list[Any] = []

    def cond(inp: Any) -> bool:
        seen.append(inp)
        return True

    contract = Flow().when(cond, then=_const("ok"), id="r1").compile()
    contract.try_execute({"k": 1})
    assert seen == [{"k": 1}]


def test_action_receives_input() -> None:
    contract = Flow().when(_true, then=lambda i: i * 2, id="r1").compile()
    assert contract.try_execute(21).value == 42


# -- guard ------------------------------------------------------------------


def test_guard_true_allows_match() -> None:
    contract = Flow().when(_true, then=_const("g"), id="r1", guard=_true).compile()
    assert contract.try_execute(None).value == "g"


def test_guard_false_blocks_match() -> None:
    contract = Flow().when(_true, then=_const("g"), id="r1", guard=_false).compile()
    assert contract.try_execute(None).decision_status is DecisionStatus.NO_MATCH


def test_guard_not_evaluated_when_condition_false() -> None:
    calls: list[str] = []

    def guard(_i: Any) -> bool:
        calls.append("guard")
        return True

    contract = Flow().when(_false, then=_const(1), id="r1", guard=guard).compile()
    contract.try_execute(None)
    assert calls == []


# -- first match / short circuit --------------------------------------------


def test_first_match_stops_after_first() -> None:
    contract = (
        Flow()
        .when(_true, then=_const("first"), id="r1")
        .when(_true, then=_const("second"), id="r2")
        .compile()
    )
    assert contract.try_execute(None).value == "first"


def test_first_match_skips_throwing_later_condition() -> None:
    contract = (
        Flow()
        .when(_true, then=_const("ok"), id="r1")
        .when(_boom, then=_const("never"), id="r2")
        .compile()
    )
    outcome = contract.try_execute(None)
    assert outcome.execution_status is ExecutionStatus.COMPLETED
    assert outcome.value == "ok"


def test_first_match_continues_past_non_matching() -> None:
    contract = (
        Flow()
        .when(_false, then=_const("no"), id="r1")
        .when(_true, then=_const("yes"), id="r2")
        .compile()
    )
    assert contract.try_execute(None).value == "yes"


# -- then chains ------------------------------------------------------------


def test_then_receives_previous_output() -> None:
    contract = (
        Flow()
        .when(_true, then=_const(10), id="r1")
        .then(lambda i, prev: prev + 5, id="t1")
        .then(lambda i, prev: prev * 2, id="t2")
        .compile()
    )
    assert contract.try_execute(None).value == 30


def test_then_skipped_when_no_match() -> None:
    contract = (
        Flow()
        .when(_false, then=_const(1), id="r1")
        .then(lambda i, prev: prev + 1, id="t1")
        .compile()
    )
    outcome = contract.try_execute(None)
    assert outcome.decision_status is DecisionStatus.NO_MATCH
    assert outcome.value is None


def test_then_after_second_rule_only_runs_for_that_rule() -> None:
    contract = (
        Flow()
        .when(_false, then=_const("a"), id="r1")
        .when(_true, then=_const(1), id="r2")
        .then(lambda i, prev: prev + 1, id="t1")
        .compile()
    )
    assert contract.try_execute(None).value == 2


# -- evaluation modes --------------------------------------------------------


def test_all_match_evaluates_all_rules() -> None:
    seen: list[str] = []

    def cond_a(_i: Any) -> bool:
        seen.append("a")
        return True

    def cond_b(_i: Any) -> bool:
        seen.append("b")
        return True

    contract = (
        Flow()
        .with_mode(EvaluationMode.ALL_MATCH)
        .when(cond_a, then=_const("A"), id="r1")
        .when(cond_b, then=_const("B"), id="r2")
        .compile()
    )
    outcome = contract.try_execute(None)
    assert seen == ["a", "b"]
    assert outcome.value == "B"


def test_all_match_no_match_when_none_match() -> None:
    contract = (
        Flow()
        .with_mode(EvaluationMode.ALL_MATCH)
        .when(_false, then=_const(1), id="r1")
        .when(_false, then=_const(2), id="r2")
        .compile()
    )
    assert contract.try_execute(None).decision_status is DecisionStatus.NO_MATCH


def test_priority_orders_by_priority_desc() -> None:
    contract = (
        Flow()
        .with_mode(EvaluationMode.PRIORITY)
        .when(_true, then=_const("low"), id="low", priority=1)
        .when(_true, then=_const("high"), id="high", priority=10)
        .compile()
    )
    assert contract.try_execute(None).value == "high"


def test_priority_ties_keep_registration_order() -> None:
    contract = (
        Flow()
        .with_mode(EvaluationMode.PRIORITY)
        .when(_true, then=_const("first"), id="r1", priority=5)
        .when(_true, then=_const("second"), id="r2", priority=5)
        .compile()
    )
    assert contract.try_execute(None).value == "first"


def test_priority_falls_through_to_lower() -> None:
    contract = (
        Flow()
        .with_mode(EvaluationMode.PRIORITY)
        .when(_false, then=_const("high"), id="high", priority=10)
        .when(_true, then=_const("low"), id="low", priority=1)
        .compile()
    )
    assert contract.try_execute(None).value == "low"


# -- fallbacks ---------------------------------------------------------------


def test_otherwise_runs_on_no_match() -> None:
    contract = (
        Flow()
        .when(_false, then=_const("rule"), id="r1")
        .otherwise(lambda i: "fb:" + str(i))
        .compile()
    )
    outcome = contract.try_execute(7)
    assert outcome.decision_status is DecisionStatus.NO_MATCH
    assert outcome.value == "fb:7"


def test_default_if_no_match_constant() -> None:
    contract = Flow().when(_false, then=_const(1), id="r1").default_if_no_match(42).compile()
    assert contract.try_execute(None).value == 42


def test_default_alias() -> None:
    contract = Flow().when(_false, then=_const(1), id="r1").default(9).compile()
    assert contract.try_execute(None).value == 9


def test_fallback_not_used_on_match() -> None:
    contract = Flow().when(_true, then=_const("rule"), id="r1").default_if_no_match(99).compile()
    outcome = contract.try_execute(None)
    assert outcome.decision_status is DecisionStatus.APPROVED
    assert outcome.value == "rule"


def test_second_fallback_rejected() -> None:
    flow = Flow().default(1)
    with pytest.raises(StructureError):
        flow.otherwise(lambda i: 2)


# -- exceptions ---------------------------------------------------------------


def test_condition_exception_yields_failed() -> None:
    contract = Flow().when(_boom, then=_const(1), id="r1").compile()
    outcome = contract.try_execute(None)
    assert outcome.execution_status is ExecutionStatus.FAILED
    assert isinstance(outcome.primary_exception, ValueError)
    assert outcome.decision_status is None


def test_action_exception_yields_failed() -> None:
    contract = Flow().when(_true, then=_boom_action, id="r1").compile()
    outcome = contract.try_execute(None)
    assert outcome.execution_status is ExecutionStatus.FAILED
    assert isinstance(outcome.primary_exception, RuntimeError)


def test_execute_raises_unrecovered_exception() -> None:
    contract = Flow().when(_boom, then=_const(1), id="r1").compile()
    with pytest.raises(ValueError):
        contract.execute(None)


def test_execute_returns_outcome_on_success() -> None:
    contract = Flow().when(_true, then=_const("ok"), id="r1").compile()
    outcome = contract.execute(None)
    assert outcome.value == "ok"


def test_execute_raises_on_failed_action() -> None:
    contract = Flow().when(_true, then=_boom_action, id="r1").compile()
    with pytest.raises(RuntimeError):
        contract.execute(None)


# -- compile validation --------------------------------------------------------


def test_compile_rejects_duplicate_ids() -> None:
    flow = Flow().when(_true, then=_const(1), id="x").when(_true, then=_const(2), id="x")
    with pytest.raises(StructureError):
        flow.compile()


def test_compile_rejects_empty_flow() -> None:
    with pytest.raises(StructureError):
        Flow().compile()


def test_compile_rejects_then_first() -> None:
    with pytest.raises(StructureError):
        Flow().then(lambda i, p: p, id="t0").compile()


def test_compile_allows_then_chain() -> None:
    contract = (
        Flow()
        .when(_true, then=_const(1), id="r1")
        .then(lambda i, p: p, id="t1")
        .then(lambda i, p: p, id="t2")
        .compile()
    )
    assert len(contract.rules) == 3


def test_compile_idempotent() -> None:
    flow = Flow().when(_true, then=_const(1), id="r1")
    assert flow.compile().rules == flow.compile().rules


def test_contract_is_immutable_snapshot() -> None:
    flow = Flow().when(_true, then=_const(1), id="r1")
    c1 = flow.compile()
    flow.when(_true, then=_const(2), id="r2")
    c2 = flow.compile()
    assert len(c1.rules) == 1
    assert len(c2.rules) == 2


def test_contract_records_spec_version_and_portability() -> None:
    contract = Flow().when(_true, then=_const(1), id="r1").compile()
    assert contract.spec_version == "0.1.0"
    assert contract.portability.name == "NATIVE"
    # contract_version is a structural SHA-256 hash (SPEC 12.9), not "1".
    assert len(contract.contract_version) == 32
    int(contract.contract_version, 16)  # valid hex


def test_with_clock_injected() -> None:
    from flowsemantics import FakeClock

    clock = FakeClock()
    contract = Flow().with_clock(clock).when(_true, then=_const(1), id="r1").compile()
    assert contract.clock is clock


def test_execute_clock_parameter_overrides() -> None:
    from flowsemantics import FakeClock

    contract = Flow().when(_true, then=_const(1), id="r1").compile()
    clock = FakeClock()
    contract.try_execute(None, clock=clock)
    # No exception; clock accepted. Determinism proof lives in integration tests.
