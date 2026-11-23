"""Unit tests for advanced FlowContract features (SPEC 4.4, 10.7, 12.5, 12.8, 12.9, 11.6)."""

import datetime

import pytest

from flowsemantics import EvaluationMode, FakeClock
from flowsemantics.configuration.flow import Flow
from flowsemantics.configuration.portable import pconst
from flowsemantics.errors import StructureError
from flowsemantics.execution.outcome import DecisionStatus, ExecutionStatus


def test_cancel_check_produces_cancelled() -> None:
    cancelled = False

    def check() -> bool:
        return cancelled

    contract = (
        Flow().with_cancel_check(check).when(lambda i: True, then=lambda i: "v", id="r1").compile()
    )
    cancelled = True
    outcome = contract.try_execute(None)
    assert outcome.execution_status is ExecutionStatus.CANCELLED
    assert outcome.interruption is not None
    assert outcome.interruption.kind == "cancelled"


def test_cancel_check_bypasses_catch() -> None:
    cancelled = False

    def check() -> bool:
        return cancelled

    contract = (
        Flow()
        .with_cancel_check(check)
        .when(lambda i: True, then=lambda i: "v", id="r1")
        .catch_any(lambda i, e: "recovered")
        .compile()
    )
    cancelled = True
    outcome = contract.try_execute(None)
    assert outcome.execution_status is ExecutionStatus.CANCELLED
    assert outcome.recovery is None


def test_simulate_batch_distribution() -> None:
    contract = (
        Flow()
        .when(lambda i: i.get("ok"), then=lambda i: "yes", id="r1")
        .default_if_no_match("no")
        .compile()
    )
    report = contract.simulate_batch([{"ok": True}, {"ok": False}, {"ok": True}])
    assert report["total"] == 3
    assert report["by_decision"]["approved"] == 2
    assert report["by_decision"]["no_match"] == 1
    assert len(report["outcomes"]) == 3


def test_portability_report_native_and_portable() -> None:
    native = Flow().when(lambda i: True, then=lambda i: "v", id="r1").compile()
    rep = native.portability_report()
    assert rep["classification"] == "NATIVE"
    assert "native rules" in rep["offenders"]

    portable = Flow().when_expr(pconst(True), then=pconst("v"), id="p1").compile()
    rep2 = portable.portability_report()
    assert rep2["classification"] == "PORTABLE"
    assert rep2["offenders"] == []


def test_validate_effective_window_error() -> None:
    frm = datetime.datetime(2025, 1, 1)
    to = datetime.datetime(2024, 1, 1)
    with pytest.raises(StructureError):
        (
            Flow()
            .when(
                lambda i: True,
                then=lambda i: "v",
                id="r1",
                effective_from=frm,
                effective_until=to,
            )
            .compile()
        )


def test_validate_gap_warning() -> None:
    contract = Flow().when(lambda i: True, then=lambda i: "v", id="r1").compile()
    codes = {i.code for i in contract.validate()}
    assert "possible_gap" in codes


def test_validate_unreachable_and_overlap_portable() -> None:
    contract = (
        Flow()
        .when_expr(pconst(True), then=pconst("a"), id="p1")
        .when_expr(pconst(True), then=pconst("b"), id="p2")
        .compile()
    )
    issues = contract.validate()
    codes = {i.code for i in issues}
    assert "unreachable_rule" in codes
    assert "overlapping_rules" in codes


def test_merge_splices_rules() -> None:
    inner = (
        Flow()
        .when(lambda i: False, then=lambda i: "inner", id="inner1")
        .default_if_no_match("inner-fb")
    )
    outer = (
        Flow()
        .when(lambda i: True, then=lambda i: "outer", id="outer1")
        .default_if_no_match("outer-fb")
    )
    outer.merge(inner)
    contract = outer.compile()
    assert contract.try_execute(None).value == "outer"

    no_match = Flow().merge(inner).compile()
    assert no_match.try_execute(None).value == "inner-fb"


def test_merge_rejects_mode_mismatch() -> None:
    a = Flow()
    b = Flow().with_mode(EvaluationMode.ALL_MATCH)
    with pytest.raises(StructureError):
        a.merge(b)


def test_merge_rejects_duplicate_rule_ids() -> None:
    a = Flow().when(lambda i: True, then=lambda i: 1, id="dup")
    b = Flow().when(lambda i: True, then=lambda i: 2, id="dup")
    with pytest.raises(StructureError):
        a.merge(b)


def test_effective_dates_gate_firing() -> None:
    f = datetime.datetime(2024, 1, 1)
    u = datetime.datetime(2026, 1, 1)
    contract = (
        Flow()
        .when(
            lambda i: True,
            then=lambda i: "v",
            id="r1",
            effective_from=f,
            effective_until=u,
        )
        .compile()
    )
    before = contract.try_execute(None, clock=FakeClock(wall=datetime.datetime(2023, 1, 1)))
    assert before.decision_status is DecisionStatus.NO_MATCH
    inside = contract.try_execute(None, clock=FakeClock(wall=datetime.datetime(2025, 6, 1)))
    assert inside.value == "v"
    after = contract.try_execute(None, clock=FakeClock(wall=datetime.datetime(2027, 1, 1)))
    assert after.decision_status is DecisionStatus.NO_MATCH
