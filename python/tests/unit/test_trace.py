"""Unit tests for execution tracing (SPEC 3.8, 12.1-12.3)."""

from __future__ import annotations

from typing import Any

from flowsemantics import (
    EVENT_TYPES,
    ExecutionStatus,
    FakeClock,
    Flow,
    TraceRecorder,
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


def _types(outcome: Any) -> list[str]:
    assert outcome.trace is not None
    return [e.type for e in outcome.trace.events]


# -- vocabulary -----------------------------------------------------------------


def test_event_vocabulary_is_closed_22() -> None:
    assert len(EVENT_TYPES) == 22


def test_recorder_rejects_unknown_type() -> None:
    rec = TraceRecorder("1")
    try:
        rec.emit("bogus_event")
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_recorder_rejects_unknown_reason() -> None:
    rec = TraceRecorder("1")
    try:
        rec.emit("rule_skipped", reason="bogus")
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


# -- opt-in behavior ---------------------------------------------------------------


def test_trace_disabled_by_default() -> None:
    contract = Flow().when(_true, then=_const(1), id="r1").compile()
    outcome = contract.try_execute(None)
    assert outcome.trace is None


def test_with_trace_enables() -> None:
    contract = Flow().with_trace().when(_true, then=_const(1), id="r1").compile()
    outcome = contract.try_execute(None)
    assert outcome.trace is not None
    assert outcome.trace.contract_version == contract.contract_version
    assert len(contract.contract_version) == 32


def test_per_call_trace_override() -> None:
    contract = Flow().when(_true, then=_const(1), id="r1").compile()
    outcome = contract.try_execute(None, trace=True)
    assert outcome.trace is not None


def test_trace_events_have_timestamps() -> None:
    clock = FakeClock()
    contract = Flow().with_clock(clock).with_trace().when(_true, then=_const(1), id="r1").compile()
    outcome = contract.try_execute(None)
    assert outcome.trace is not None
    for event in outcome.trace.events:
        assert event.timestamp == clock.wall()
        assert event.contract_version == contract.contract_version


# -- event emission ------------------------------------------------------------------


def test_condition_and_action_events() -> None:
    contract = Flow().with_trace().when(_true, then=_const("v"), id="r1").compile()
    outcome = contract.try_execute(None)
    assert _types(outcome) == ["condition_evaluated", "action_executed"]


def test_rule_skipped_condition_false() -> None:
    contract = Flow().with_trace().when(_false, then=_const(1), id="r1").compile()
    outcome = contract.try_execute(None)
    events = outcome.trace.events  # type: ignore[union-attr]
    skipped = [e for e in events if e.type == "rule_skipped"]
    assert len(skipped) == 1
    assert skipped[0].reason == "condition_false"
    assert skipped[0].rule_id == "r1"


def test_rule_skipped_guard_blocked() -> None:
    contract = Flow().with_trace().when(_true, then=_const(1), id="r1", guard=_false).compile()
    outcome = contract.try_execute(None)
    events = outcome.trace.events  # type: ignore[union-attr]
    skipped = [e for e in events if e.type == "rule_skipped"]
    assert skipped[0].reason == "guard_blocked"


def test_guard_evaluated_event() -> None:
    contract = Flow().with_trace().when(_true, then=_const(1), id="r1", guard=_true).compile()
    outcome = contract.try_execute(None)
    assert "guard_evaluated" in _types(outcome)


def test_short_circuit_events() -> None:
    contract = (
        Flow()
        .with_trace()
        .when(_true, then=_const(1), id="r1")
        .when(_true, then=_const(2), id="r2")
        .when(_true, then=_const(3), id="r3")
        .compile()
    )
    outcome = contract.try_execute(None)
    types = _types(outcome)
    assert types.count("skipped_by_short_circuit") == 2
    skipped_ids = [
        e.rule_id
        for e in outcome.trace.events  # type: ignore[union-attr]
        if e.type == "skipped_by_short_circuit"
    ]
    assert skipped_ids == ["r2", "r3"]


def test_condition_raised_event() -> None:
    def bad_cond(_i: Any) -> bool:
        raise ValueError("cond")

    contract = Flow().with_trace().when(bad_cond, then=_const(1), id="r1").compile()
    outcome = contract.try_execute(None)
    assert outcome.execution_status is ExecutionStatus.FAILED
    assert "condition_raised" in _types(outcome)
    assert "action_raised" not in _types(outcome)


def test_action_raised_event() -> None:
    contract = Flow().with_trace().when(_true, then=_raise(RuntimeError("act")), id="r1").compile()
    outcome = contract.try_execute(None)
    types = _types(outcome)
    assert "action_executed" not in types
    assert "action_raised" in types


def test_catch_events() -> None:
    contract = (
        Flow()
        .with_trace()
        .when(_true, then=_raise(ValueError("v")), id="r1")
        .catch(ValueError, lambda i, e: "ok")
        .compile()
    )
    outcome = contract.try_execute(None)
    types = _types(outcome)
    assert "action_raised" in types
    assert "catch_matched" in types
    assert "catch_handled" in types


def test_catch_declined_event() -> None:
    contract = (
        Flow()
        .with_trace()
        .when(_true, then=_raise(ValueError("v")), id="r1")
        .catch_when(ValueError, lambda i, e: False, lambda i, e: "no")
        .catch_any(lambda i, e: "any")
        .compile()
    )
    outcome = contract.try_execute(None)
    types = _types(outcome)
    assert "catch_predicate_evaluated" in types
    assert "catch_declined" in types
    assert "catch_handled" in types


def test_rethrow_event() -> None:
    contract = (
        Flow().with_trace().when(_true, then=_raise(ValueError("v")), id="r1").rethrow().compile()
    )
    outcome = contract.try_execute(None)
    assert "rethrow_reached" in _types(outcome)


def test_hook_events() -> None:
    def bad_hook(_i: Any, _r: str, _v: Any) -> None:
        raise RuntimeError("hook")

    contract = (
        Flow().with_trace().when(_true, then=_const("v"), id="r1").on_match(bad_hook).compile()
    )
    outcome = contract.try_execute(None)
    types = _types(outcome)
    assert "hook_invoked" in types
    assert "hook_raised" in types


def test_finally_events() -> None:
    def bad_cleanup(_ctx: Any) -> None:
        raise RuntimeError("cleanup")

    contract = (
        Flow().with_trace().when(_true, then=_const("ok"), id="r1").finally_(bad_cleanup).compile()
    )
    outcome = contract.try_execute(None)
    types = _types(outcome)
    assert "finally_started" in types
    assert "finally_raised" in types
    assert "finally_completed" not in types


def test_cancelled_observed_event() -> None:
    import asyncio

    def cancel(_i: Any) -> Any:
        raise asyncio.CancelledError()

    contract = Flow().with_trace().when(_true, then=cancel, id="r1").compile()
    outcome = contract.try_execute(None)
    assert "cancelled_observed" in _types(outcome)


def test_timed_out_observed_event() -> None:
    def timeout(_i: Any) -> Any:
        raise TimeoutError("deadline")

    contract = Flow().with_trace().when(_true, then=timeout, id="r1").compile()
    outcome = contract.try_execute(None)
    assert "timed_out_observed" in _types(outcome)


def test_diagnostic_hook_adds_opt_in_data() -> None:
    def hook(event: Any) -> dict[str, Any] | None:
        if event.type == "action_executed":
            return {"duration_ms": 3}
        return None

    contract = Flow().with_trace(hook).when(_true, then=_const("v"), id="r1").compile()
    outcome = contract.try_execute(None)
    assert outcome.trace is not None
    action_events = [e for e in outcome.trace.events if e.type == "action_executed"]
    assert action_events[0].diagnostics == {"duration_ms": 3}
    cond_events = [e for e in outcome.trace.events if e.type == "condition_evaluated"]
    assert cond_events[0].diagnostics is None


def test_no_hook_no_diagnostics() -> None:
    contract = Flow().with_trace().when(_true, then=_const("v"), id="r1").compile()
    outcome = contract.try_execute(None)
    assert outcome.trace is not None
    for event in outcome.trace.events:
        assert event.diagnostics is None


def test_per_call_diagnostic_hook_override() -> None:
    contract = Flow().with_trace().when(_true, then=_const("v"), id="r1").compile()
    outcome = contract.try_execute(None, diagnostic_hook=lambda e: {"tag": "x"})
    assert outcome.trace is not None
    assert outcome.trace.events[0].diagnostics == {"tag": "x"}


def test_trace_contains_no_input_values() -> None:
    secret = "SUPER-SECRET-INPUT"
    contract = Flow().with_trace().when(lambda i: True, then=_const("out"), id="r1").compile()
    outcome = contract.try_execute(secret)
    assert outcome.trace is not None
    for event in outcome.trace.events:
        for field_value in vars(event).values():
            assert secret not in str(field_value)
