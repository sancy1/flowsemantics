"""Unit tests for catch rules (SPEC.md sections 11.1-11.4, 7.3.1)."""

from __future__ import annotations

from typing import Any

import pytest

from flowsemantics import (
    ExecutionStatus,
    Flow,
    StructureError,
)


def _true(_input: Any) -> bool:
    return True


def _const(value: Any):
    return lambda _input: value


def _raise(exc: Exception):
    def _fn(_input: Any) -> Any:
        raise exc

    return _fn


def _raise_handler(exc: Exception):
    def _fn(_input: Any, _exc: BaseException) -> Any:
        raise exc

    return _fn


# -- typed catch (11.1) ---------------------------------------------------------


def test_typed_catch_recovers_valueerror() -> None:
    contract = (
        Flow()
        .when(_true, then=_raise(ValueError("bad")), id="r1")
        .catch(ValueError, lambda i, e: "recovered", id="c1")
        .compile()
    )
    outcome = contract.try_execute(None)
    assert outcome.execution_status is ExecutionStatus.COMPLETED
    assert outcome.value == "recovered"
    assert outcome.recovery is not None
    assert isinstance(outcome.recovery.original_exception, ValueError)
    assert outcome.recovery.handler_rule_id == "c1"


def test_typed_catch_receives_input_and_exception() -> None:
    seen: list[Any] = []

    def handler(inp: Any, exc: BaseException) -> str:
        seen.append((inp, type(exc).__name__))
        return "ok"

    contract = (
        Flow().when(_true, then=_raise(KeyError("k")), id="r1").catch(KeyError, handler).compile()
    )
    contract.try_execute({"ctx": 1})
    assert seen == [({"ctx": 1}, "KeyError")]


def test_typed_catch_inheritance_match() -> None:
    class CustomError(ValueError):
        pass

    contract = (
        Flow()
        .when(_true, then=_raise(CustomError("x")), id="r1")
        .catch(ValueError, lambda i, e: "base-caught")
        .compile()
    )
    assert contract.try_execute(None).value == "base-caught"


def test_typed_catch_no_match_falls_through() -> None:
    contract = (
        Flow()
        .when(_true, then=_raise(ValueError("v")), id="r1")
        .catch(KeyError, lambda i, e: "wrong-type")
        .compile()
    )
    outcome = contract.try_execute(None)
    assert outcome.execution_status is ExecutionStatus.FAILED
    assert isinstance(outcome.primary_exception, ValueError)


def test_catch_does_not_catch_baseexception() -> None:
    contract = (
        Flow()
        .when(_true, then=_raise(SystemExit("bye")), id="r1")  # type: ignore[arg-type]
        .catch(Exception, lambda i, e: "caught")
        .compile()
    )
    outcome = contract.try_execute(None)
    # SystemExit is BaseException, not Exception: bypasses catch, FAILED.
    assert outcome.execution_status is ExecutionStatus.FAILED
    assert isinstance(outcome.primary_exception, SystemExit)


# -- catch_when (11.2) ------------------------------------------------------------


def test_catch_when_predicate_true_handles() -> None:
    contract = (
        Flow()
        .when(_true, then=_raise(ValueError("v")), id="r1")
        .catch_when(ValueError, lambda i, e: "v" in str(e), lambda i, e: "pred-ok")
        .compile()
    )
    assert contract.try_execute(None).value == "pred-ok"


def test_catch_when_predicate_false_declines() -> None:
    contract = (
        Flow()
        .when(_true, then=_raise(ValueError("v")), id="r1")
        .catch_when(ValueError, lambda i, e: False, lambda i, e: "no")
        .catch_any(lambda i, e: "any-fallback")
        .compile()
    )
    assert contract.try_execute(None).value == "any-fallback"


def test_catch_when_type_check_before_predicate() -> None:
    calls: list[str] = []

    def pred(_i: Any, _e: BaseException) -> bool:
        calls.append("pred")
        return True

    contract = (
        Flow()
        .when(_true, then=_raise(ValueError("v")), id="r1")
        .catch_when(KeyError, pred, lambda i, e: "no")
        .compile()
    )
    contract.try_execute(None)
    assert calls == []  # predicate never evaluated for wrong type


def test_catch_when_predicate_failure_becomes_primary() -> None:
    def bad_pred(_i: Any, _e: BaseException) -> bool:
        raise RuntimeError("pred exploded")

    contract = (
        Flow()
        .when(_true, then=_raise(ValueError("orig")), id="r1")
        .catch_when(ValueError, bad_pred, lambda i, e: "no")
        .compile()
    )
    outcome = contract.try_execute(None)
    assert outcome.execution_status is ExecutionStatus.FAILED
    assert isinstance(outcome.primary_exception, RuntimeError)


# -- catch_any (11.3) --------------------------------------------------------------


def test_catch_any_handles_untyped() -> None:
    contract = (
        Flow()
        .when(_true, then=_raise(RuntimeError("r")), id="r1")
        .catch_any(lambda i, e: "any")
        .compile()
    )
    outcome = contract.try_execute(None)
    assert outcome.value == "any"
    assert outcome.recovery is not None


def test_catch_any_after_typed_preferred() -> None:
    contract = (
        Flow()
        .when(_true, then=_raise(ValueError("v")), id="r1")
        .catch(ValueError, lambda i, e: "typed")
        .catch_any(lambda i, e: "any")
        .compile()
    )
    assert contract.try_execute(None).value == "typed"


def test_catch_any_before_typed_is_compile_error() -> None:
    flow = (
        Flow()
        .when(_true, then=_raise(ValueError("v")), id="r1")
        .catch_any(lambda i, e: "any")
        .catch(ValueError, lambda i, e: "typed")
    )
    with pytest.raises(StructureError):
        flow.compile()


def test_multiple_catch_any_first_wins() -> None:
    contract = (
        Flow()
        .when(_true, then=_raise(ValueError("v")), id="r1")
        .catch_any(lambda i, e: "first")
        .catch_any(lambda i, e: "second")
        .compile()
    )
    assert contract.try_execute(None).value == "first"


# -- rethrow (11.4) -----------------------------------------------------------------


def test_rethrow_propagates_original() -> None:
    original = ValueError("original")
    contract = (
        Flow()
        .when(_true, then=_raise(original), id="r1")
        .catch(KeyError, lambda i, e: "wrong-type")
        .rethrow()
        .compile()
    )
    outcome = contract.try_execute(None)
    assert outcome.execution_status is ExecutionStatus.FAILED
    assert outcome.primary_exception is original
    assert outcome.recovery is None


def test_rethrow_before_catch_still_fails() -> None:
    contract = (
        Flow()
        .when(_true, then=_raise(ValueError("v")), id="r1")
        .rethrow()
        .catch(ValueError, lambda i, e: "never")
        .compile()
    )
    outcome = contract.try_execute(None)
    assert outcome.execution_status is ExecutionStatus.FAILED


# -- handler failure propagation -----------------------------------------------------


def test_handler_raise_propagates_new_exception() -> None:
    contract = (
        Flow()
        .when(_true, then=_raise(ValueError("orig")), id="r1")
        .catch(ValueError, _raise_handler(KeyError("handler-fail")))
        .compile()
    )
    outcome = contract.try_execute(None)
    assert outcome.execution_status is ExecutionStatus.FAILED
    assert isinstance(outcome.primary_exception, KeyError)


def test_handler_raise_routes_to_remaining_catches() -> None:
    contract = (
        Flow()
        .when(_true, then=_raise(ValueError("orig")), id="r1")
        .catch(ValueError, _raise_handler(KeyError("second")))
        .catch(KeyError, lambda i, e: "caught-second")
        .compile()
    )
    outcome = contract.try_execute(None)
    assert outcome.value == "caught-second"
    assert outcome.recovery is not None
    assert isinstance(outcome.recovery.original_exception, KeyError)


# -- recovery outcome shape -----------------------------------------------------------


def test_recovery_outcome_completed_with_value() -> None:
    contract = (
        Flow()
        .when(_true, then=_raise(ValueError("v")), id="r1")
        .catch(ValueError, lambda i, e: "recovered-value")
        .compile()
    )
    outcome = contract.try_execute(None)
    assert outcome.execution_status is ExecutionStatus.COMPLETED
    assert outcome.value == "recovered-value"
    assert outcome.recovery is not None
    assert outcome.primary_exception is None


def test_execute_raises_when_no_catch_matches() -> None:
    contract = Flow().when(_true, then=_raise(ValueError("v")), id="r1").compile()
    with pytest.raises(ValueError):
        contract.execute(None)


def test_execute_returns_recovered_outcome() -> None:
    contract = (
        Flow()
        .when(_true, then=_raise(ValueError("v")), id="r1")
        .catch(ValueError, lambda i, e: "ok")
        .compile()
    )
    outcome = contract.execute(None)
    assert outcome.value == "ok"
    assert outcome.recovery is not None


# -- catch in conditions (not just actions) ---------------------------------------------


def test_condition_exception_is_caught() -> None:
    contract = (
        Flow()
        .when(_raise(ValueError("cond")), then=_const(1), id="r1")
        .catch(ValueError, lambda i, e: "cond-recovered")
        .compile()
    )
    assert contract.try_execute(None).value == "cond-recovered"


def test_fallback_exception_is_caught() -> None:
    contract = (
        Flow()
        .when(lambda i: False, then=_const(1), id="r1")
        .otherwise(_raise(RuntimeError("fb")))
        .catch(RuntimeError, lambda i, e: "fb-recovered")
        .compile()
    )
    assert contract.try_execute(None).value == "fb-recovered"


# -- merge carries catches ---------------------------------------------------------------


def test_merge_carries_catches() -> None:
    inner = Flow().catch(ValueError, lambda i, e: "inner-catch")
    outer = Flow().when(_true, then=_raise(ValueError("v")), id="r1").merge(inner)
    outcome = outer.compile().try_execute(None)
    assert outcome.value == "inner-catch"
