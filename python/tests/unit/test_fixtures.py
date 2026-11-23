"""Unit tests for the conformance fixture vocabulary (spec/fixtures.md)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from flowsemantics.testing.conformance.fixtures import (
    FixtureAnyError,
    FixtureContext,
    exception_for_kind,
    kind_of_exception,
    list_fixture_names,
    resolve_fixture,
)


def _ref(name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    ref: dict[str, Any] = {"fixture": name}
    if params is not None:
        ref["params"] = params
    return ref


# -- resolution basics --------------------------------------------------------


def test_resolve_cond_true() -> None:
    fn = resolve_fixture(_ref("cond.true"))
    assert fn(None) is True


def test_resolve_cond_false() -> None:
    fn = resolve_fixture(_ref("cond.false"))
    assert fn(None) is False


def test_resolve_cond_returns() -> None:
    fn = resolve_fixture(_ref("cond.returns", {"value": True}))
    assert fn(None) is True


def test_resolve_action_const() -> None:
    fn = resolve_fixture(_ref("action.const", {"v": 42}))
    assert fn(None) == 42


def test_resolve_action_const_accepts_value_alias() -> None:
    fn = resolve_fixture(_ref("action.const", {"value": "x"}))
    assert fn(None) == "x"


def test_resolve_input_fixtures() -> None:
    assert resolve_fixture(_ref("input.empty")) == {}
    assert resolve_fixture(_ref("input.order_50")) == {"total": 50}
    assert resolve_fixture(_ref("input.order_0")) == {"total": 0}
    assert resolve_fixture(_ref("input.order_large")) == {"total": 10000}


def test_unknown_fixture_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        resolve_fixture(_ref("cond.nonexistent"))


def test_missing_required_param_raises() -> None:
    with pytest.raises(KeyError):
        resolve_fixture(_ref("action.const"))


def test_non_dict_params_rejected() -> None:
    with pytest.raises(ValueError):
        resolve_fixture({"fixture": "cond.true", "params": "bad"})


def test_missing_fixture_name_rejected() -> None:
    with pytest.raises(ValueError):
        resolve_fixture({"params": {}})


# -- error kinds ---------------------------------------------------------------


def test_exception_for_kind_mapping() -> None:
    assert isinstance(exception_for_kind("Kind.Timeout"), TimeoutError)
    assert isinstance(exception_for_kind("Kind.Cancelled"), asyncio.CancelledError)
    assert isinstance(exception_for_kind("Kind.ValueError"), ValueError)
    assert isinstance(exception_for_kind("Kind.Any"), FixtureAnyError)


def test_unknown_kind_raises() -> None:
    with pytest.raises(KeyError):
        exception_for_kind("Kind.Bogus")


def test_kind_of_exception_reverse_mapping() -> None:
    assert kind_of_exception(ValueError("x")) == "Kind.ValueError"
    assert kind_of_exception(TimeoutError("x")) == "Kind.Timeout"
    assert kind_of_exception(FixtureAnyError("x")) == "Kind.Any"
    assert kind_of_exception(RuntimeError("x")) == "Kind.Any"


def test_cond_throws_raises_mapped_kind() -> None:
    fn = resolve_fixture(_ref("cond.throws", {"kind": "Kind.ValueError"}))
    with pytest.raises(ValueError):
        fn(None)


def test_action_throws_raises_mapped_kind() -> None:
    fn = resolve_fixture(_ref("action.throws", {"kind": "Kind.Timeout"}))
    with pytest.raises(TimeoutError):
        fn(None)


# -- stateful fixtures ---------------------------------------------------------


def test_cond_returns_per_call_sequence() -> None:
    fn = resolve_fixture(_ref("cond.returns_per_call", {"values": [True, False]}))
    assert fn(None) is True
    assert fn(None) is False
    assert fn(None) is False  # repeats last


def test_hook_records_appends_to_context() -> None:
    ctx = FixtureContext()
    hook = resolve_fixture(_ref("hook.records"), ctx)
    hook(None, "rule-1", "value-1")
    assert ctx.records == [{"rule_id": "rule-1", "value": "value-1"}]


def test_action_returns_delegates_to_nested_fixture() -> None:
    ctx = FixtureContext()
    fn = resolve_fixture(_ref("action.returns", {"ref": _ref("action.const", {"v": 7})}), ctx)
    assert fn(None) == 7


def test_fixture_context_isolation() -> None:
    ctx1 = FixtureContext()
    ctx2 = FixtureContext()
    hook1 = resolve_fixture(_ref("hook.records"), ctx1)
    hook2 = resolve_fixture(_ref("hook.records"), ctx2)
    hook1(None, "r", "v")
    hook2(None, "r2", "v2")
    assert ctx1.records == [{"rule_id": "r", "value": "v"}]
    assert ctx2.records == [{"rule_id": "r2", "value": "v2"}]


# -- registry -------------------------------------------------------------------


def test_list_fixture_names_covers_vocabulary() -> None:
    names = list_fixture_names()
    for required in (
        "cond.true",
        "cond.false",
        "cond.returns",
        "cond.throws",
        "cond.returns_per_call",
        "action.const",
        "action.throws",
        "action.returns",
        "guard.true",
        "guard.false",
        "catch.handles",
        "catch.throws",
        "hook.records",
        "hook.throws",
        "cleanup.succeeds",
        "cleanup.throws",
        "cleanup.cooperative",
        "cleanup.ignores_token",
        "cleanup.delays",
        "enrichment.delayed",
        "input.empty",
        "input.order_50",
        "input.order_0",
        "input.order_large",
    ):
        assert required in names, f"missing fixture: {required}"
