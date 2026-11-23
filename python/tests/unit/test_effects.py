"""Unit tests for proposed effects (SPEC 5, 6.4, 3.7)."""

from __future__ import annotations

import asyncio
from typing import Any

from flowsemantics import Effect, Flow


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def test_effects_proposed_on_match() -> None:
    contract = (
        Flow()
        .when(
            lambda i: i["ok"],
            then=lambda i: "done",
            id="r1",
            effects=[Effect("notify", {"user": "u1"}), Effect("audit")],
        )
        .compile()
    )
    outcome = contract.try_execute({"ok": True})
    assert outcome.value == "done"
    assert [e.name for e in outcome.effects] == ["notify", "audit"]
    assert outcome.effects[0].payload == {"user": "u1"}


def test_no_effects_when_rule_does_not_match() -> None:
    contract = (
        Flow()
        .when(
            lambda i: False,
            then=lambda i: 1,
            id="r1",
            effects=[Effect("notify")],
        )
        .default("fallback")
        .compile()
    )
    outcome = contract.try_execute({})
    assert outcome.value == "fallback"
    assert outcome.effects == ()


def test_effect_order_is_deterministic() -> None:
    contract = (
        Flow()
        .with_mode("AllMatch")
        .when(lambda i: True, then=lambda i: 1, id="a", effects=[Effect("e1")])
        .when(lambda i: True, then=lambda i: 2, id="b", effects=[Effect("e2"), Effect("e3")])
        .compile()
    )
    first = contract.try_execute({})
    second = contract.try_execute({})
    assert [e.name for e in first.effects] == ["e1", "e2", "e3"]
    assert [e.name for e in first.effects] == [e.name for e in second.effects]


def test_then_stage_effects_follow_rule_effects() -> None:
    contract = (
        Flow()
        .when(
            lambda i: True,
            then=lambda i: 1,
            id="r1",
            effects=[Effect("rule-effect")],
        )
        .then(lambda i, v: v + 1, id="s1", effects=[Effect("stage-effect")])
        .compile()
    )
    outcome = contract.try_execute({})
    assert outcome.value == 2
    assert [e.name for e in outcome.effects] == ["rule-effect", "stage-effect"]


def test_effects_not_applied_by_library() -> None:
    # The library proposes; it never executes. An EffectExecutor is
    # application-owned (SPEC 5.5).
    applied: list[str] = []

    def executor(effect: Effect) -> None:
        applied.append(effect.name)

    contract = (
        Flow().when(lambda i: True, then=lambda i: 1, id="r1", effects=[Effect("charge")]).compile()
    )
    outcome = contract.try_execute({})
    assert applied == []  # library did not apply
    for effect in outcome.effects:
        executor(effect)
    assert applied == ["charge"]


def test_effect_proposed_trace_event() -> None:
    contract = (
        Flow()
        .with_trace()
        .when(lambda i: True, then=lambda i: 1, id="r1", effects=[Effect("e")])
        .compile()
    )
    outcome = contract.try_execute({})
    assert outcome.trace is not None
    types = [e.type for e in outcome.trace.events]
    assert "effect_proposed" in types


def test_async_effects_parity() -> None:
    async def act(_i: Any) -> Any:
        return "v"

    contract = Flow().when(lambda i: True, then=act, id="r1", effects=[Effect("e1")]).compile()
    outcome = _run(contract.try_execute_async({}))
    assert [e.name for e in outcome.effects] == ["e1"]


def test_failed_rule_proposes_no_effects() -> None:
    def boom(_i: Any) -> Any:
        raise ValueError("x")

    contract = (
        Flow()
        .when(lambda i: True, then=boom, id="r1", effects=[Effect("e")])
        .catch(ValueError, lambda i, e: "recovered")
        .compile()
    )
    outcome = contract.try_execute({})
    assert outcome.value == "recovered"
    # The action raised before effects were proposed.
    assert outcome.effects == ()
