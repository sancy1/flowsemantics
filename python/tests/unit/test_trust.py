"""Unit tests for trust layer: simulate, explain, validate, contract version."""

from __future__ import annotations

from typing import Any

from flowsemantics import (
    EvaluationMode,
    ExecutionStatus,
    FakeClock,
    Flow,
    FlowContract,
    FlowPortability,
    Rule,
    RuleId,
    SystemClock,
)


def _true(_input: Any) -> bool:
    return True


def _false(_input: Any) -> bool:
    return False


def _const(value: Any) -> Any:
    return lambda _input: value


def _raise(exc: Exception) -> Any:
    def _fn(_input: Any) -> Any:
        raise exc

    return _fn


# -- contract version (12.9) ---------------------------------------------------------


def test_contract_version_is_deterministic() -> None:
    def build() -> Any:
        return Flow().when(_true, then=_const(1), id="r1").compile()

    assert build().contract_version == build().contract_version


def test_contract_version_changes_with_structure() -> None:
    c1 = Flow().when(_true, then=_const(1), id="r1").compile()
    c2 = Flow().when(_true, then=_const(1), id="r2").compile()
    c3 = Flow().when(_true, then=_const(1), id="r1").with_mode("AllMatch").compile()
    assert c1.contract_version != c2.contract_version
    assert c1.contract_version != c3.contract_version


def test_contract_version_stable_across_rebuild_same_structure() -> None:
    c1 = Flow().when(_true, then=_const(1), id="r1").compile()
    c2 = Flow().when(_true, then=_const(2), id="r1").compile()
    # Same structure (id/kind/priority) -> same version even though the
    # action callable differs (callables are identity-free in the hash).
    assert c1.contract_version == c2.contract_version


# -- simulate (12.5) -------------------------------------------------------------------


def test_simulate_matches_real_decision() -> None:
    contract = (
        Flow()
        .when(lambda o: o["total"] > 100, then=lambda o: "big", id="big")
        .when_not(lambda o: o["total"] > 100, then=lambda o: "small", id="small")
        .compile()
    )
    for order in ({"total": 50}, {"total": 500}):
        real = contract.try_execute(order)
        sim = contract.simulate(order)
        assert sim.execution_status == real.execution_status
        assert sim.decision_status == real.decision_status
        assert sim.value == real.value


def test_simulate_suppresses_hooks() -> None:
    calls: list[str] = []

    def hook(_i: Any, rid: str, _v: Any) -> None:
        calls.append(rid)

    contract = Flow().when(_true, then=_const("v"), id="r1").on_match(hook).compile()
    contract.simulate(None)
    assert calls == []
    contract.try_execute(None)
    assert calls == ["r1"]


def test_simulate_skips_finalizers() -> None:
    ran: list[str] = []

    def cleanup(_ctx: Any) -> None:
        ran.append("cleanup")

    contract = Flow().when(_true, then=_const("ok"), id="r1").finally_(cleanup).compile()
    sim = contract.simulate(None)
    assert ran == []
    assert sim.finalization is None
    contract.try_execute(None)
    assert ran == ["cleanup"]


def test_simulate_uses_injected_clock() -> None:
    clock = FakeClock()
    contract = Flow().with_clock(clock).when(_true, then=_const(1), id="r1").compile()
    sim = contract.simulate(None)
    assert sim.execution_status is ExecutionStatus.COMPLETED


# -- explain (12.4) ----------------------------------------------------------------------


def test_explain_renders_events() -> None:
    contract = Flow().with_trace().when(_true, then=_const("v"), id="approve-rule").compile()
    outcome = contract.try_execute(None)
    assert outcome.trace is not None
    text = contract.explain(outcome.trace)
    assert "approve-rule" in text
    assert "condition_evaluated" in text
    assert "action_executed" in text


def test_explain_includes_skip_reasons() -> None:
    contract = Flow().with_trace().when(_false, then=_const(1), id="r1").compile()
    outcome = contract.try_execute(None)
    assert outcome.trace is not None
    text = contract.explain(outcome.trace)
    assert "condition_false" in text


def test_explain_does_not_invent_reasons() -> None:
    contract = Flow().with_trace().when(_true, then=_const("v"), id="r1").compile()
    outcome = contract.try_execute(None)
    assert outcome.trace is not None
    text = contract.explain(outcome.trace)
    # No invented rationale like "because total was high"
    assert "because" not in text


# -- validate (12.8) ---------------------------------------------------------------------


def test_validate_clean_contract() -> None:
    contract = Flow().when(_true, then=_const(1), id="r1").compile()
    issues = contract.validate()
    assert all(i.severity != "error" for i in issues)


def test_validate_detects_duplicate_ids_defensively() -> None:
    # compile() rejects duplicates, so construct a contract manually
    # to exercise validate()'s defensive check.
    rule = Rule(
        id=RuleId("dup"),
        kind="when",
        condition=_true,
        guard=None,
        action=_const(1),
    )
    contract = FlowContract(
        rules=(rule, rule),
        fallback=None,
        mode=EvaluationMode.FIRST_MATCH,
        clock=SystemClock(),
        spec_version="0.1.0",
        portability=FlowPortability.NATIVE,
    )
    issues = contract.validate()
    assert any(i.code == "duplicate_rule_id" for i in issues)
