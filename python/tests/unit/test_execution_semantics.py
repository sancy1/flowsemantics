"""Unit tests for hooks, interruption, and finalization (SPEC 11.5-11.8)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from flowsemantics import (
    ExecutionStatus,
    FakeClock,
    FinallyFailurePolicy,
    Flow,
    StructureError,
)


def _true(_input: Any) -> bool:
    return True


def _false(_input: Any) -> bool:
    return False


def _const(value: Any):
    return lambda _input: value


def _raise(exc: Exception):
    def _fn(_input: Any) -> Any:
        raise exc

    return _fn


# -- on_match hooks (11.5) ---------------------------------------------------------


def test_hook_receives_input_rule_id_value() -> None:
    seen: list[tuple[Any, str, Any]] = []

    def hook(inp: Any, rule_id: str, value: Any) -> None:
        seen.append((inp, rule_id, value))

    contract = (
        Flow()
        .when(_true, then=_const("v"), id="my-rule")
        .on_match(hook)
        .compile()
    )
    contract.try_execute({"in": 1})
    assert seen == [({"in": 1}, "my-rule", "v")]


def test_hook_failure_isolated_to_secondary() -> None:
    def bad_hook(_i: Any, _r: str, _v: Any) -> None:
        raise RuntimeError("hook exploded")

    contract = (
        Flow()
        .when(_true, then=_const("ok"), id="r1")
        .on_match(bad_hook)
        .compile()
    )
    outcome = contract.try_execute(None)
    assert outcome.execution_status is ExecutionStatus.COMPLETED
    assert outcome.value == "ok"
    assert len(outcome.secondary_exceptions) == 1
    assert isinstance(outcome.secondary_exceptions[0], RuntimeError)


def test_hook_failure_does_not_trigger_catch() -> None:
    def bad_hook(_i: Any, _r: str, _v: Any) -> None:
        raise ValueError("hook")

    contract = (
        Flow()
        .when(_true, then=_const("ok"), id="r1")
        .on_match(bad_hook)
        .catch(ValueError, lambda i, e: "caught")
        .compile()
    )
    outcome = contract.try_execute(None)
    assert outcome.value == "ok"  # not "caught"


def test_hooks_run_per_match_in_all_match() -> None:
    calls: list[str] = []

    def hook(_i: Any, rule_id: str, _v: Any) -> None:
        calls.append(rule_id)

    contract = (
        Flow()
        .with_mode("AllMatch")
        .when(_true, then=_const(1), id="r1")
        .when(_true, then=_const(2), id="r2")
        .on_match(hook)
        .compile()
    )
    contract.try_execute(None)
    assert calls == ["r1", "r2"]


def test_no_hook_no_behavior_change() -> None:
    contract = Flow().when(_true, then=_const("x"), id="r1").compile()
    outcome = contract.try_execute(None)
    assert outcome.secondary_exceptions == ()


# -- interruption recognition (11.6) -------------------------------------------------


def test_cancelled_error_yields_cancelled() -> None:
    def cancel(_i: Any) -> Any:
        raise asyncio.CancelledError()

    contract = Flow().when(_true, then=cancel, id="r1").compile()
    outcome = contract.try_execute(None)
    assert outcome.execution_status is ExecutionStatus.CANCELLED
    assert outcome.interruption is not None
    assert outcome.interruption.kind == "cancelled"
    assert outcome.recovery is None  # B5: interruption never under recovery


def test_cancelled_bypasses_catch_rules() -> None:
    def cancel(_i: Any) -> Any:
        raise asyncio.CancelledError()

    contract = (
        Flow()
        .when(_true, then=cancel, id="r1")
        .catch(Exception, lambda i, e: "caught")
        .compile()
    )
    outcome = contract.try_execute(None)
    assert outcome.execution_status is ExecutionStatus.CANCELLED


def test_timeout_error_yields_timed_out() -> None:
    def timeout(_i: Any) -> Any:
        raise TimeoutError("external deadline")

    contract = Flow().when(_true, then=timeout, id="r1").compile()
    outcome = contract.try_execute(None)
    assert outcome.execution_status is ExecutionStatus.TIMED_OUT
    assert outcome.interruption is not None
    assert outcome.interruption.kind == "timed_out"


def test_timeout_bypasses_catch_rules() -> None:
    def timeout(_i: Any) -> Any:
        raise TimeoutError("deadline")

    contract = (
        Flow()
        .when(_true, then=timeout, id="r1")
        .catch(TimeoutError, lambda i, e: "caught-timeout")
        .compile()
    )
    outcome = contract.try_execute(None)
    assert outcome.execution_status is ExecutionStatus.TIMED_OUT


def test_interruption_timestamp_uses_injected_clock() -> None:
    clock = FakeClock()
    def cancel(_i: Any) -> Any:
        raise asyncio.CancelledError()

    contract = Flow().with_clock(clock).when(_true, then=cancel, id="r1").compile()
    outcome = contract.try_execute(None)
    assert outcome.interruption is not None
    assert outcome.interruption.timestamp == clock.wall()


# -- finalization (11.8, 16.4) ---------------------------------------------------------


def test_finalizer_runs_on_success() -> None:
    seen: list[str] = []

    def cleanup(ctx: Any) -> None:
        seen.append(ctx.status.name)

    contract = (
        Flow()
        .when(_true, then=_const("ok"), id="r1")
        .finally_(cleanup)
        .compile()
    )
    outcome = contract.try_execute(None)
    assert seen == ["COMPLETED"]
    assert outcome.finalization is not None
    assert outcome.finalization.is_clean is True


def test_finalizer_runs_on_failure() -> None:
    seen: list[str] = []

    def cleanup(ctx: Any) -> None:
        seen.append(ctx.status.name)

    contract = (
        Flow()
        .when(_true, then=_raise(ValueError("x")), id="r1")
        .finally_(cleanup)
        .compile()
    )
    outcome = contract.try_execute(None)
    assert seen == ["FAILED"]
    assert outcome.finalization is not None
    assert outcome.finalization.is_clean is True


def test_finalizer_receives_context_fields() -> None:
    captured: list[Any] = []

    def cleanup(ctx: Any) -> None:
        captured.append((ctx.value, ctx.context, ctx.cancellation_token))

    contract = (
        Flow()
        .when(_true, then=_const(42), id="r1")
        .finally_(cleanup)
        .compile()
    )
    contract.try_execute({"input": True})
    value, context, token = captured[0]
    assert value == 42
    assert context == {"input": True}
    assert token.cancelled is False


def test_finalizer_lifo_order() -> None:
    order: list[str] = []

    def first(_ctx: Any) -> None:
        order.append("first-registered")

    def second(_ctx: Any) -> None:
        order.append("second-registered")

    contract = (
        Flow()
        .when(_true, then=_const(1), id="r1")
        .finally_(first)
        .finally_(second)
        .compile()
    )
    contract.try_execute(None)
    assert order == ["second-registered", "first-registered"]


def test_finalizer_failure_isolated() -> None:
    ran: list[str] = []

    def bad(_ctx: Any) -> None:
        raise RuntimeError("cleanup failed")

    def good(_ctx: Any) -> None:
        ran.append("good-ran")

    contract = (
        Flow()
        .when(_true, then=_const("ok"), id="r1")
        .finally_(good)
        .finally_(bad)
        .compile()
    )
    outcome = contract.try_execute(None)
    assert ran == ["good-ran"]  # bad ran first (LIFO), good still ran
    assert outcome.execution_status is ExecutionStatus.COMPLETED
    assert outcome.value == "ok"
    assert outcome.finalization is not None
    assert outcome.finalization.is_clean is False
    assert len(outcome.finalization.cleanup_exceptions) == 1
    assert len(outcome.secondary_exceptions) == 1


def test_preserve_primary_default() -> None:
    def bad(_ctx: Any) -> None:
        raise RuntimeError("cleanup")

    contract = (
        Flow()
        .when(_true, then=_const("ok"), id="r1")
        .finally_(bad)
        .compile()
    )
    outcome = contract.try_execute(None)
    assert outcome.execution_status is ExecutionStatus.COMPLETED
    assert outcome.value == "ok"


def test_replace_primary_on_failed() -> None:
    original = ValueError("original")

    def bad_cleanup(_ctx: Any) -> None:
        raise RuntimeError("cleanup-fail")

    contract = (
        Flow()
        .when(_true, then=_raise(original), id="r1")
        .finally_(bad_cleanup)
        .with_finally_policy(FinallyFailurePolicy.REPLACE_PRIMARY)
        .compile()
    )
    outcome = contract.try_execute(None)
    assert outcome.execution_status is ExecutionStatus.FAILED
    assert isinstance(outcome.primary_exception, RuntimeError)
    assert original in outcome.secondary_exceptions


def test_replace_primary_preserves_completed() -> None:
    def bad_cleanup(_ctx: Any) -> None:
        raise RuntimeError("cleanup")

    contract = (
        Flow()
        .when(_true, then=_const("ok"), id="r1")
        .finally_(bad_cleanup)
        .with_finally_policy(FinallyFailurePolicy.REPLACE_PRIMARY)
        .compile()
    )
    outcome = contract.try_execute(None)
    assert outcome.execution_status is ExecutionStatus.COMPLETED  # B3-a
    assert outcome.value == "ok"


def test_replace_primary_preserves_cancelled() -> None:
    def cancel(_i: Any) -> Any:
        raise asyncio.CancelledError()

    def bad_cleanup(_ctx: Any) -> None:
        raise RuntimeError("cleanup")

    contract = (
        Flow()
        .when(_true, then=cancel, id="r1")
        .finally_(bad_cleanup)
        .with_finally_policy(FinallyFailurePolicy.REPLACE_PRIMARY)
        .compile()
    )
    outcome = contract.try_execute(None)
    assert outcome.execution_status is ExecutionStatus.CANCELLED  # B3-a
    assert outcome.interruption is not None


def test_finalizer_runs_on_cancelled() -> None:
    seen: list[str] = []

    def cancel(_i: Any) -> Any:
        raise asyncio.CancelledError()

    def cleanup(ctx: Any) -> None:
        seen.append(ctx.status.name)

    contract = (
        Flow()
        .when(_true, then=cancel, id="r1")
        .finally_(cleanup)
        .compile()
    )
    contract.try_execute(None)
    assert seen == ["CANCELLED"]


def test_finalizer_never_triggers_catch() -> None:
    def bad_cleanup(_ctx: Any) -> None:
        raise ValueError("cleanup")

    contract = (
        Flow()
        .when(_true, then=_const("ok"), id="r1")
        .finally_(bad_cleanup)
        .catch(ValueError, lambda i, e: "caught-cleanup")
        .compile()
    )
    outcome = contract.try_execute(None)
    assert outcome.value == "ok"  # FR3: no re-entry


def test_finally_timeout_budget() -> None:
    clock = FakeClock()

    def slow_cleanup(_ctx: Any) -> None:
        clock.advance(0.2)  # 200ms > 100ms budget

    contract = (
        Flow()
        .with_clock(clock)
        .when(_true, then=_const("ok"), id="r1")
        .finally_(slow_cleanup)
        .with_finally_timeout(100)
        .compile()
    )
    outcome = contract.try_execute(None)
    assert outcome.finalization is not None
    assert outcome.finalization.cleanup_budget_exceeded is True
    assert outcome.finalization.is_clean is False


def test_finally_timeout_validation() -> None:
    with pytest.raises(StructureError):
        Flow().with_finally_timeout(0)


def test_no_finalizers_no_finalization_info() -> None:
    contract = Flow().when(_true, then=_const("ok"), id="r1").compile()
    outcome = contract.try_execute(None)
    assert outcome.finalization is None


def test_merge_finalizers_lifo_inner_first() -> None:
    order: list[str] = []

    inner = Flow().finally_(lambda _c: order.append("inner"))
    outer = Flow().when(_true, then=_const(1), id="r1").finally_(
        lambda _c: order.append("outer")
    ).merge(inner)
    outer.compile().try_execute(None)
    assert order == ["inner", "outer"]
