"""Unit tests for RuleId and Rule (SPEC.md sections 2.1, 10.1)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from flowsemantics import Rule, RuleId


def test_rule_id_str_conversion() -> None:
    rid = RuleId("approve-large")
    assert str(rid) == "approve-large"
    assert f"{rid}" == "approve-large"


def test_rule_id_rejects_empty() -> None:
    with pytest.raises(ValueError):
        RuleId("")


def test_rule_id_is_frozen() -> None:
    rid = RuleId("x")
    with pytest.raises(FrozenInstanceError):
        rid.value = "y"  # type: ignore[misc]


def test_rule_is_frozen() -> None:
    rule = Rule(
        id=RuleId("r1"),
        kind="when",
        condition=lambda i: True,
        guard=None,
        action=lambda i: 1,
    )
    with pytest.raises(FrozenInstanceError):
        rule.priority = 5  # type: ignore[misc]


def test_rule_accepts_string_id_via_coercion_in_flow() -> None:
    # Flow._coerce_id accepts plain strings; Rule itself requires RuleId.
    from flowsemantics import Flow

    flow = Flow().when(lambda i: True, then=lambda i: 1, id="plain-string")
    contract = flow.compile()
    assert str(contract.rules[0].id) == "plain-string"
