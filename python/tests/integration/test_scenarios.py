"""Integration tests: end-to-end scenarios combining Phase 1 features.

Covers: order-approval flow (when/when_not/otherwise/then), merge
composition, decision tables, evaluation modes, determinism (SPEC 6.1),
execution isolation (SPEC 4.1.3), and execute/try_execute contract (D13).
"""

from __future__ import annotations

from typing import Any

from flowsemantics import (
    DecisionStatus,
    DecisionTable,
    DecisionTableRow,
    EvaluationMode,
    ExecutionStatus,
    FakeClock,
    Flow,
)

# -- scenario: order approval -------------------------------------------------


def _total_above_100(order: Any) -> bool:
    return order["total"] > 100


def _approve(order: Any) -> str:
    return "approved:" + str(order["total"])


def _reject(order: Any) -> str:
    return "rejected"


def _needs_review(order: Any) -> str:
    return "review:" + str(order["total"])


def _double_tax(_input: Any, previous: Any) -> float:
    return previous * 1.2


def test_order_approval_scenario() -> None:
    flow = (
        Flow()
        .when(_total_above_100, then=_approve, id="large-order")
        .when_not(_total_above_100, then=_reject, id="small-order")
        .otherwise(_needs_review)
    )
    contract = flow.compile()

    big = contract.try_execute({"total": 250})
    assert big.execution_status is ExecutionStatus.COMPLETED
    assert big.decision_status is DecisionStatus.APPROVED
    assert big.value == "approved:250"

    small = contract.try_execute({"total": 40})
    assert small.value == "rejected"


def test_order_with_then_stage() -> None:
    flow = (
        Flow()
        .when(lambda o: o["total"] > 0, then=lambda o: float(o["total"]), id="has-total")
        .then(_double_tax, id="tax")
    )
    outcome = flow.compile().try_execute({"total": 100})
    assert outcome.value == 120.0


def test_order_zero_total_no_match() -> None:
    flow = (
        Flow()
        .when(lambda o: o["total"] > 0, then=lambda o: "positive", id="pos")
        .default_if_no_match("zero-or-negative")
    )
    outcome = flow.compile().try_execute({"total": 0})
    assert outcome.decision_status is DecisionStatus.NO_MATCH
    assert outcome.value == "zero-or-negative"


# -- scenario: composed flows via merge ----------------------------------------


def test_merged_flows_evaluate_in_order() -> None:
    fraud = Flow().when(lambda o: o.get("fraud"), then=lambda o: "fraud", id="fraud-check")
    limits = Flow().when(lambda o: o["total"] > 1000, then=lambda o: "over-limit", id="limit-check")
    flow = Flow().merge(fraud).merge(limits)
    contract = flow.compile()

    assert contract.try_execute({"total": 50, "fraud": True}).value == "fraud"
    assert contract.try_execute({"total": 2000}).value == "over-limit"
    assert contract.try_execute({"total": 50}).decision_status is DecisionStatus.NO_MATCH


def test_merge_with_table_flow() -> None:
    table = DecisionTable(
        rows=(
            DecisionTableRow(
                id="vip",
                conditions=(lambda o: o.get("vip"),),
                action=lambda o: "vip",
            ),
        ),
        hit_policy="FIRST",
    )
    table_flow = Flow.from_table(table)
    extra = Flow().when(lambda o: o["total"] > 500, then=lambda o: "whale", id="whale")
    contract = Flow().merge(table_flow).merge(extra).compile()

    assert contract.try_execute({"total": 10, "vip": True}).value == "vip"
    assert contract.try_execute({"total": 600}).value == "whale"


# -- scenario: decision table ---------------------------------------------------


def test_decision_table_discount() -> None:
    table = DecisionTable(
        rows=(
            DecisionTableRow(
                id="member-10",
                conditions=(lambda o: o.get("member"),),
                action=lambda o: o["total"] * 0.9,
            ),
            DecisionTableRow(
                id="big-5",
                conditions=(lambda o: o["total"] > 100,),
                action=lambda o: o["total"] * 0.95,
            ),
        ),
        hit_policy="FIRST",
    )
    contract = Flow.from_table(table).compile()
    assert contract.try_execute({"total": 200, "member": True}).value == 180.0
    assert contract.try_execute({"total": 200}).value == 190.0
    assert contract.try_execute({"total": 50}).decision_status is DecisionStatus.NO_MATCH


def test_decision_table_collect() -> None:
    table = DecisionTable(
        rows=(
            DecisionTableRow(id="a", conditions=(lambda o: True,), action=lambda o: "A"),
            DecisionTableRow(id="b", conditions=(lambda o: True,), action=lambda o: "B"),
        ),
        hit_policy="COLLECT",
    )
    outcome = Flow.from_table(table).compile().try_execute({})
    assert outcome.value == "B"


# -- scenario: evaluation modes ---------------------------------------------------


def test_all_match_collects_multiple() -> None:
    contract = (
        Flow()
        .with_mode(EvaluationMode.ALL_MATCH)
        .when(lambda o: o["total"] > 0, then=lambda o: "positive", id="pos")
        .when(lambda o: o["total"] < 1000, then=lambda o: "small", id="small")
        .compile()
    )
    outcome = contract.try_execute({"total": 50})
    assert outcome.value == "small"  # last match wins


def test_priority_mode_business_rules() -> None:
    contract = (
        Flow()
        .with_mode(EvaluationMode.PRIORITY)
        .when(lambda o: True, then=lambda o: "default", id="default", priority=0)
        .when(lambda o: o.get("vip"), then=lambda o: "vip", id="vip", priority=100)
        .compile()
    )
    assert contract.try_execute({"vip": True}).value == "vip"
    assert contract.try_execute({}).value == "default"


# -- determinism (SPEC 6.1) ---------------------------------------------------------


def test_deterministic_repeated_execution() -> None:
    contract = (
        Flow()
        .when(lambda o: o["total"] > 100, then=lambda o: "big", id="big")
        .when_not(lambda o: o["total"] > 100, then=lambda o: "small", id="small")
        .compile()
    )
    clock = FakeClock()
    first = contract.try_execute({"total": 250}, clock=clock)
    second = contract.try_execute({"total": 250}, clock=clock)
    assert first == second


def test_deterministic_across_contract_rebuild() -> None:
    def build() -> Any:
        return Flow().when(lambda o: o["x"] > 0, then=lambda o: o["x"] * 2, id="double").compile()

    assert build().try_execute({"x": 5}).value == build().try_execute({"x": 5}).value


# -- isolation (SPEC 4.1.3) ---------------------------------------------------------


def test_executions_do_not_share_state() -> None:
    calls: list[int] = []

    def counting(_i: Any) -> int:
        calls.append(1)
        return len(calls)

    contract = Flow().when(lambda i: True, then=counting, id="count").compile()
    first = contract.try_execute(None)
    second = contract.try_execute(None)
    # Each execution is independent; the counter is user state, not engine state.
    assert first.value == 1
    assert second.value == 2


def test_contract_reusable_across_threads_inputs() -> None:
    contract = Flow().when(lambda o: o % 2 == 0, then=lambda o: "even", id="e").compile()
    results = [contract.try_execute(i).value for i in range(6)]
    assert results == ["even", None, "even", None, "even", None]


# -- execute vs try_execute (D13) -----------------------------------------------------


def test_execute_raises_but_try_execute_returns() -> None:
    def bad(_i: Any) -> Any:
        raise KeyError("missing")

    contract = Flow().when(lambda i: True, then=bad, id="bad").compile()
    outcome = contract.try_execute(None)
    assert outcome.execution_status is ExecutionStatus.FAILED
    try:
        contract.execute(None)
    except KeyError:
        pass
    else:  # pragma: no cover
        raise AssertionError("execute() should have raised")


def test_failed_outcome_has_no_decision_status() -> None:
    def bad(_i: Any) -> Any:
        raise ValueError("x")

    contract = Flow().when(lambda i: True, then=bad, id="bad").compile()
    outcome = contract.try_execute(None)
    assert outcome.decision_status is None
    assert outcome.value is None


# -- catch rules end-to-end -------------------------------------------------------


def test_payment_flow_with_typed_catch() -> None:
    def charge(order: Any) -> str:
        if order["card"] == "declined":
            raise ValueError("card declined")
        if order["card"] == "gateway":
            raise ConnectionError("gateway unreachable")
        return "charged:" + str(order["total"])

    contract = (
        Flow()
        .when(lambda o: o["total"] > 0, then=charge, id="charge")
        .catch(ValueError, lambda i, e: "payment-declined")
        .catch(ConnectionError, lambda i, e: "payment-gateway")
        .compile()
    )

    assert contract.try_execute({"total": 50, "card": "ok"}).value == "charged:50"
    assert contract.try_execute({"total": 50, "card": "declined"}).value == "payment-declined"
    assert contract.try_execute({"total": 50, "card": "gateway"}).value == "payment-gateway"


def test_payment_timeout_is_interruption_not_catch() -> None:
    def charge(order: Any) -> str:
        if order["card"] == "timeout":
            raise TimeoutError("gateway timeout")
        return "charged:" + str(order["total"])

    contract = (
        Flow()
        .when(lambda o: o["total"] > 0, then=charge, id="charge")
        .catch(TimeoutError, lambda i, e: "payment-timeout")
        .compile()
    )
    outcome = contract.try_execute({"total": 50, "card": "timeout"})
    # SPEC 11.6.2-11.6.3: externally-imposed timeout is an interruption,
    # not a catchable exception.
    assert outcome.execution_status is ExecutionStatus.TIMED_OUT
    assert outcome.interruption is not None


def test_catch_any_as_safety_net() -> None:
    def risky(_i: Any) -> Any:
        raise RuntimeError("unexpected")

    contract = (
        Flow()
        .when(lambda i: True, then=risky, id="risky")
        .catch(ValueError, lambda i, e: "typed-only")
        .catch_any(lambda i, e: "safety-net")
        .compile()
    )
    outcome = contract.try_execute(None)
    assert outcome.value == "safety-net"
    assert outcome.recovery is not None


def test_unrecovered_exception_still_fails() -> None:
    def bad(_i: Any) -> Any:
        raise ValueError("unhandled")

    contract = (
        Flow()
        .when(lambda i: True, then=bad, id="bad")
        .catch(KeyError, lambda i, e: "wrong-type")
        .compile()
    )
    outcome = contract.try_execute(None)
    assert outcome.execution_status is ExecutionStatus.FAILED
    assert isinstance(outcome.primary_exception, ValueError)


def test_catch_with_merge_composition() -> None:
    def boom(_o: Any) -> Any:
        raise ValueError("boom")

    resilience = Flow().catch(ValueError, lambda i, e: "resilient-fallback")
    business = Flow().when(lambda o: o["total"] > 0, then=boom, id="charge")
    contract = business.merge(resilience).compile()
    outcome = contract.try_execute({"total": 10})
    assert outcome.value == "resilient-fallback"


# -- portable IR end-to-end ---------------------------------------------------------


def test_portable_flow_end_to_end() -> None:
    from flowsemantics import (
        FlowPortability,
        pand,
        pconst,
        pfield,
        pgt,
        pin,
    )

    contract = (
        Flow()
        .with_flow_id("shipping-tier")
        .when_expr(
            pand(
                pgt(pfield("weight"), pconst(20)),
                pin(pfield("region"), ["remote", "intl"]),
            ),
            then=pconst("freight"),
            id="heavy-remote",
        )
        .when_expr(
            pgt(pfield("weight"), pconst(20)),
            then=pconst("heavy-local"),
            id="heavy-local",
        )
        .default("standard")
        .compile()
    )
    assert contract.portability is FlowPortability.PORTABLE

    assert contract.try_execute({"weight": 30, "region": "remote"}).value == "freight"
    assert contract.try_execute({"weight": 30, "region": "urban"}).value == "heavy-local"
    assert contract.try_execute({"weight": 5, "region": "remote"}).value == "standard"

    # IR export -> reimport -> identical decisions
    rebuilt = Flow.from_ir(contract.to_ir_json()).compile()
    for order in (
        {"weight": 30, "region": "remote"},
        {"weight": 30, "region": "urban"},
        {"weight": 5, "region": "remote"},
    ):
        assert rebuilt.try_execute(order).value == contract.try_execute(order).value


def test_portable_flow_with_trace_and_replay() -> None:
    from flowsemantics import ReplayMode, pconst, pfield, pgt, record, replay

    contract = (
        Flow()
        .with_flow_id("simple")
        .with_trace()
        .when_expr(pgt(pfield("x"), pconst(0)), then=pconst("pos"), id="pos")
        .compile()
    )
    outcome = contract.try_execute({"x": 5})
    assert outcome.trace is not None
    assert outcome.value == "pos"

    rec = record(contract, {"x": 5})
    result = replay(rec, contract, mode=ReplayMode.DECISION)
    assert result.equivalent is True
