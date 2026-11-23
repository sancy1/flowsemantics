"""Python implementations of the fixture vocabulary (spec/fixtures.md).

Each fixture name resolves to a factory that produces the host-language
callable or value the conformance runner binds into a Flow pipeline.

Callable signatures used by the engine:
  - condition / guard : (input) -> bool
  - action            : (input) -> value
  - then stage        : (input, previous_output) -> value
  - catch handler     : (input, exception) -> value
  - hook              : (input, rule_id, value) -> None
  - cleanup           : (FinallyContext) -> None   (Phase 2.5)

Abstract error kinds (fixtures.md) map to concrete Python exceptions:
  Kind.Timeout   -> TimeoutError
  Kind.Cancelled -> asyncio.CancelledError
  Kind.ValueError-> ValueError
  Kind.Any       -> FixtureAnyError (a plain Exception subclass)
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any


class FixtureAnyError(Exception):
    """Concrete mapping for the abstract kind Kind.Any."""


KIND_MAP: dict[str, type[BaseException]] = {
    "Kind.Timeout": TimeoutError,
    "Kind.Cancelled": asyncio.CancelledError,
    "Kind.ValueError": ValueError,
    "Kind.Any": FixtureAnyError,
}


def exception_for_kind(kind: str) -> BaseException:
    """Instantiate the concrete exception for an abstract error kind."""
    exc_type = KIND_MAP.get(kind)
    if exc_type is None:
        raise KeyError(f"unknown abstract error kind: {kind!r}")
    return exc_type(f"fixture error: {kind}")


def kind_of_exception(exc: BaseException) -> str:
    """Reverse-map a concrete exception to its abstract kind."""
    if isinstance(exc, TimeoutError):
        return "Kind.Timeout"
    if isinstance(exc, asyncio.CancelledError):
        return "Kind.Cancelled"
    if isinstance(exc, ValueError):
        return "Kind.ValueError"
    if isinstance(exc, FixtureAnyError):
        return "Kind.Any"
    return "Kind.Any"


def _param(params: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in params:
            return params[name]
    return default


def _require_param(params: dict[str, Any], *names: str) -> Any:
    value = _param(params, *names, default=_MISSING)
    if value is _MISSING:
        raise KeyError(f"missing required fixture parameter: {names[0]!r}")
    return value


_MISSING = object()


# -- condition fixtures ----------------------------------------------------


def _cond_true(_input: Any) -> bool:
    return True


def _cond_false(_input: Any) -> bool:
    return False


def _make_cond_returns(value: bool) -> Callable[[Any], bool]:
    def _cond(_input: Any) -> bool:
        return value

    return _cond


def _make_cond_throws(kind: str) -> Callable[[Any], bool]:
    def _cond(_input: Any) -> bool:
        raise exception_for_kind(kind)

    return _cond


def _make_cond_returns_per_call(values: list[bool]) -> Callable[[Any], bool]:
    state = {"index": 0}

    def _cond(_input: Any) -> bool:
        index = state["index"]
        state["index"] = index + 1
        if index >= len(values):
            return values[-1]
        return values[index]

    return _cond


# -- action fixtures -------------------------------------------------------


def _make_action_const(value: Any) -> Callable[..., Any]:
    def _action(_input: Any, *_args: Any) -> Any:
        return value

    return _action


def _make_action_throws(kind: str) -> Callable[..., Any]:
    def _action(_input: Any, *_args: Any) -> Any:
        raise exception_for_kind(kind)

    return _action


def _make_action_prev() -> Callable[..., Any]:
    def _action(_input: Any, previous: Any = None, *_args: Any) -> Any:
        return previous

    return _action


# -- guard fixtures --------------------------------------------------------


def _guard_true(_input: Any) -> bool:
    return True


def _guard_false(_input: Any) -> bool:
    return False


# -- catch fixtures --------------------------------------------------------


def _make_catch_handles(value: Any) -> Callable[[Any, BaseException], Any]:
    def _handler(_input: Any, _exc: BaseException) -> Any:
        return value

    return _handler


def _make_catch_throws(kind: str) -> Callable[[Any, BaseException], Any]:
    def _handler(_input: Any, _exc: BaseException) -> Any:
        raise exception_for_kind(kind)

    return _handler


# -- hook fixtures ---------------------------------------------------------


def _make_hook_records(records: list[dict[str, Any]]) -> Callable[[Any, str, Any], None]:
    def _hook(_input: Any, rule_id: str, value: Any) -> None:
        records.append({"rule_id": rule_id, "value": value})

    return _hook


def _make_hook_throws(kind: str) -> Callable[[Any, str, Any], None]:
    def _hook(_input: Any, _rule_id: str, _value: Any) -> None:
        raise exception_for_kind(kind)

    return _hook


# -- cleanup fixtures ------------------------------------------------------


def _cleanup_succeeds(_ctx: Any) -> None:
    return None


def _make_cleanup_throws(kind: str) -> Callable[[Any], None]:
    def _cleanup(_ctx: Any) -> None:
        raise exception_for_kind(kind)

    return _cleanup


def _cleanup_cooperative(ctx: Any) -> None:
    token = getattr(ctx, "cancellation_token", None)
    if token is not None and getattr(token, "cancelled", False):
        return
    return None


def _cleanup_ignores_token(_ctx: Any) -> None:
    return None


def _make_cleanup_delays(ms: int) -> Callable[[Any], None]:
    def _cleanup(_ctx: Any) -> None:
        time.sleep(ms / 1000.0)

    return _cleanup


# -- enrichment fixtures ---------------------------------------------------


def _make_enrichment_delayed(ms: int) -> Callable[[Any], Any]:
    def _enrichment(_input: Any) -> Any:
        time.sleep(ms / 1000.0)
        return {"delayed_ms": ms}

    return _enrichment


# -- input fixtures --------------------------------------------------------

_INPUTS: dict[str, Any] = {
    "input.empty": {},
    "input.order_50": {"total": 50},
    "input.order_0": {"total": 0},
    "input.order_large": {"total": 10000},
}


# -- registry --------------------------------------------------------------


class FixtureContext:
    """Per-vector resolution context shared by fixtures in one vector."""

    def __init__(self) -> None:
        """Create an empty per-vector fixture context."""
        self.records: list[dict[str, Any]] = []
        self.hooks: list[Callable[..., Any]] = []


FixtureFactory = Callable[[dict[str, Any], FixtureContext], Any]


def _resolve_action_returns(params: dict[str, Any], ctx: FixtureContext) -> Any:
    ref = _require_param(params, "ref", "fixture_ref")
    return resolve_fixture(ref, ctx)


def _build_registry(ctx: FixtureContext) -> dict[str, FixtureFactory]:
    return {
        "cond.true": lambda p, c: _cond_true,
        "cond.false": lambda p, c: _cond_false,
        "cond.returns": lambda p, c: _make_cond_returns(bool(_require_param(p, "value", "v"))),
        "cond.throws": lambda p, c: _make_cond_throws(str(_require_param(p, "kind"))),
        "cond.returns_per_call": lambda p, c: _make_cond_returns_per_call(
            list(_require_param(p, "values"))
        ),
        "action.const": lambda p, c: _make_action_const(_require_param(p, "v", "value")),
        "action.throws": lambda p, c: _make_action_throws(str(_require_param(p, "kind"))),
        "action.returns": _resolve_action_returns,
        "action.prev": lambda p, c: _make_action_prev(),
        "guard.true": lambda p, c: _guard_true,
        "guard.false": lambda p, c: _guard_false,
        "catch.handles": lambda p, c: _make_catch_handles(_param(p, "v", "value", default=None)),
        "catch.throws": lambda p, c: _make_catch_throws(str(_require_param(p, "kind"))),
        "hook.records": lambda p, c: _make_hook_records(ctx.records),
        "hook.throws": lambda p, c: _make_hook_throws(str(_require_param(p, "kind"))),
        "cleanup.succeeds": lambda p, c: _cleanup_succeeds,
        "cleanup.throws": lambda p, c: _make_cleanup_throws(str(_require_param(p, "kind"))),
        "cleanup.cooperative": lambda p, c: _cleanup_cooperative,
        "cleanup.ignores_token": lambda p, c: _cleanup_ignores_token,
        "cleanup.delays": lambda p, c: _make_cleanup_delays(int(_require_param(p, "ms"))),
        "enrichment.delayed": lambda p, c: _make_enrichment_delayed(int(_require_param(p, "ms"))),
    }


def resolve_fixture(ref: dict[str, Any], ctx: FixtureContext | None = None) -> Any:
    """Resolve a FixtureRef ({fixture, params}) to a callable or value.

    Raises:
        KeyError: unknown fixture name or missing required parameter.
        ValueError: invalid parameter type or value.
    """
    if ctx is None:
        ctx = FixtureContext()
    name = ref.get("fixture")
    if not isinstance(name, str):
        raise ValueError("fixture reference must have a string 'fixture' name")
    params = ref.get("params") or {}
    if not isinstance(params, dict):
        raise ValueError("fixture 'params' must be an object")

    if name in _INPUTS:
        return _INPUTS[name]

    registry = _build_registry(ctx)
    factory = registry.get(name)
    if factory is None:
        raise KeyError(f"unknown fixture: {name!r}")
    return factory(params, ctx)


def list_fixture_names() -> list[str]:
    """Return all known fixture names (for coverage and diagnostics)."""
    ctx = FixtureContext()
    names = sorted(_build_registry(ctx).keys())
    names.extend(sorted(_INPUTS.keys()))
    return names


__all__: list[str] = [
    "KIND_MAP",
    "FixtureAnyError",
    "FixtureContext",
    "exception_for_kind",
    "kind_of_exception",
    "list_fixture_names",
    "resolve_fixture",
]
