"""Unit tests for async execution parity (SPEC 11.7, FR8)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from flowsemantics import (
    AsyncOnlyContractError,
    ExecutionStatus,
    FinallyContext,
    Flow,
    StructureError,
)


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


# -- async-only classification ---------------------------------------------------------


def test_async_action_makes_contract_async_only() -> None:
    async def act(_i: Any) -> Any:
        return "async-value"

    contract = Flow().when(lambda i: True, then=act, id="r1").compile()
    assert contract.async_only is True


def test_async_condition_makes_contract_async_only() -> None:
    async def cond(_i: Any) -> bool:
        return True

    contract = Flow().when(cond, then=lambda i: 1, id="r1").compile()
    assert contract.async_only is True


def test_async_finalizer_makes_contract_async_only() -> None:
    async def fin(_c: FinallyContext) -> None:
        return None

    contract = Flow().when(lambda i: True, then=lambda i: 1, id="r1").finally_async(fin).compile()
    assert contract.async_only is True


def test_sync_contract_not_async_only() -> None:
    contract = Flow().when(lambda i: True, then=lambda i: 1, id="r1").compile()
    assert contract.async_only is False


def test_mixed_finalizers_rejected() -> None:
    async def afin(_c: FinallyContext) -> None:
        return None

    def sfin(_c: FinallyContext) -> None:
        return None

    flow = Flow().when(lambda i: True, then=lambda i: 1, id="r1").finally_(sfin).finally_async(afin)
    with pytest.raises(StructureError):
        flow.compile()


# -- execute() on async-only contract -----------------------------------------------------


def test_execute_raises_on_async_only() -> None:
    async def act(_i: Any) -> Any:
        return 1

    contract = Flow().when(lambda i: True, then=act, id="r1").compile()
    with pytest.raises(AsyncOnlyContractError):
        contract.execute(None)
    with pytest.raises(AsyncOnlyContractError):
        contract.try_execute(None)


# -- async execution ---------------------------------------------------------------------


def test_execute_async_basic() -> None:
    async def act(_i: Any) -> Any:
        await asyncio.sleep(0)
        return "done"

    contract = Flow().when(lambda i: True, then=act, id="r1").compile()
    outcome = _run(contract.execute_async(None))
    assert outcome.value == "done"
    assert outcome.execution_status is ExecutionStatus.COMPLETED


def test_try_execute_async_returns_outcome() -> None:
    async def cond(_i: Any) -> bool:
        return True

    contract = Flow().when(cond, then=lambda i: "v", id="r1").compile()
    outcome = _run(contract.try_execute_async(None))
    assert outcome.value == "v"


def test_async_condition_awaited() -> None:
    called = False

    async def cond(_i: Any) -> bool:
        nonlocal called
        called = True
        return True

    contract = Flow().when(cond, then=lambda i: 1, id="r1").compile()
    _run(contract.execute_async(None))
    assert called is True


def test_async_parity_same_outcome() -> None:
    # Same contract shape, sync vs async callables -> identical outcomes.
    sync_contract = (
        Flow()
        .when(lambda o: o["x"] > 0, then=lambda o: "pos", id="p")
        .when_not(lambda o: o["x"] > 0, then=lambda o: "neg", id="n")
        .compile()
    )

    async def acond(o: Any) -> bool:
        return o["x"] > 0

    async def apos(_o: Any) -> Any:
        return "pos"

    async def aneg(_o: Any) -> Any:
        return "neg"

    async_contract = (
        Flow().when(acond, then=apos, id="p").when_not(acond, then=aneg, id="n").compile()
    )
    for order in ({"x": 5}, {"x": -1}):
        sync_out = sync_contract.try_execute(order)
        async_out = _run(async_contract.try_execute_async(order))
        assert sync_out.value == async_out.value
        assert sync_out.decision_status == async_out.decision_status


def test_async_catch_handler() -> None:
    async def boom(_i: Any) -> Any:
        raise ValueError("async-boom")

    async def handler(_i: Any, _e: Exception) -> Any:
        return "recovered"

    contract = Flow().when(lambda i: True, then=boom, id="r1").catch(ValueError, handler).compile()
    outcome = _run(contract.execute_async(None))
    assert outcome.value == "recovered"
    assert outcome.recovery is not None


def test_async_hook() -> None:
    seen: list[str] = []

    async def hook(_i: Any, rid: str, _v: Any) -> None:
        seen.append(rid)

    contract = Flow().when(lambda i: True, then=lambda i: 1, id="r1").on_match(hook).compile()
    _run(contract.execute_async(None))
    assert seen == ["r1"]


def test_async_finalizer_runs() -> None:
    cleaned: list[str] = []

    async def fin(_c: FinallyContext) -> None:
        cleaned.append("done")

    contract = Flow().when(lambda i: True, then=lambda i: 1, id="r1").finally_async(fin).compile()
    outcome = _run(contract.execute_async(None))
    assert cleaned == ["done"]
    assert outcome.finalization is not None
    assert outcome.finalization.is_clean is True


def test_async_finalizer_failure_isolated() -> None:
    async def bad(_c: FinallyContext) -> None:
        raise RuntimeError("cleanup-fail")

    contract = Flow().when(lambda i: True, then=lambda i: 1, id="r1").finally_async(bad).compile()
    outcome = _run(contract.try_execute_async(None))
    assert outcome.finalization is not None
    assert outcome.finalization.is_clean is False
    assert len(outcome.secondary_exceptions) == 1


def test_async_trace_events() -> None:
    async def act(_i: Any) -> Any:
        return 1

    contract = Flow().with_trace().when(lambda i: True, then=act, id="r1").compile()
    outcome = _run(contract.try_execute_async(None))
    assert outcome.trace is not None
    types = {e.type for e in outcome.trace.events}
    assert "condition_evaluated" in types
    assert "action_executed" in types


def test_async_cancellation() -> None:
    async def act(_i: Any) -> Any:
        raise asyncio.CancelledError()

    contract = Flow().when(lambda i: True, then=act, id="r1").compile()
    outcome = _run(contract.try_execute_async(None))
    assert outcome.execution_status is ExecutionStatus.CANCELLED
    assert outcome.interruption is not None
    assert outcome.interruption.kind == "cancelled"


def test_sync_path_rejects_awaitable_result() -> None:
    # A non-coroutinefunction callable returning an awaitable must not be
    # silently skipped on the sync path (SPEC 11.7).
    def sneaky(_i: Any) -> Any:
        async def inner() -> int:
            return 1

        return inner()

    contract = Flow().when(lambda i: True, then=sneaky, id="r1").compile()
    # sneaky is not detected as async at compile time (returns coroutine
    # but isn't a coroutine function), so contract is sync-classified;
    # the sync path must reject the awaitable at runtime. The rejection
    # surfaces as the primary exception on the FAILED outcome.
    outcome = contract.try_execute(None)
    assert outcome.primary_exception is not None
    assert isinstance(outcome.primary_exception, AsyncOnlyContractError)
    with pytest.raises(AsyncOnlyContractError):
        contract.execute(None)
