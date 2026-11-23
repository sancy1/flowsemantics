"""Adversarial and fuzz tests for the Portable IR deserializer (SPEC 9.4).

Seeded, deterministic fuzzing — no third-party property library
(zero-dependency policy, SPEC 15.1). Every malformed input must either
parse into a valid PortableFlow or raise a documented error type; it
must never hang, crash the interpreter, or execute code.
"""

from __future__ import annotations

import json
import random
from typing import Any

import pytest

from flowsemantics.configuration.portable import (
    MAX_EXPR_DEPTH,
    MAX_IR_BYTES,
    MAX_RULES,
    PortableFlow,
    expr_from_dict,
)
from flowsemantics.errors import StructureError

_ALLOWED_ERRORS = (StructureError, KeyError, TypeError, ValueError, RecursionError)


def _valid_ir() -> dict[str, Any]:
    return {
        "spec_version": "0.1.0",
        "flow_id": "fuzz",
        "portability": "PORTABLE",
        "mode": "FirstMatch",
        "rules": [
            {
                "rule_id": "r1",
                "kind": "when",
                "condition": {
                    "op": "gt",
                    "args": [
                        {"op": "field", "value": "x"},
                        {"op": "const", "value": 0},
                    ],
                },
                "transform": {"op": "const", "value": 1},
            }
        ],
        "fallback": {"kind": "default_if_no_match", "value": 0},
    }


# -- malformed JSON ------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        "",
        "not json",
        "{",
        "[]",
        '"just a string"',
        "null",
        "42",
        '{"rules": [}',
    ],
)
def test_malformed_json_rejected(payload: str) -> None:
    with pytest.raises(_ALLOWED_ERRORS):
        PortableFlow.from_json(payload)


def test_deeply_nested_json_array_rejected() -> None:
    # 5000-deep nested arrays exceed CPython's JSON recursion limit.
    payload = "[" * 5000 + "]" * 5000
    with pytest.raises(_ALLOWED_ERRORS):
        PortableFlow.from_json(payload)


def test_oversized_json_rejected() -> None:
    payload = json.dumps(_valid_ir()) + " " * MAX_IR_BYTES
    with pytest.raises(StructureError):
        PortableFlow.from_json(payload)


def test_duplicate_keys_last_wins() -> None:
    # JSON spec: duplicate keys are last-wins. The IR does not rely on
    # key uniqueness for security (documented in threat-model.md).
    text = (
        '{"spec_version":"0.1.0","spec_version":"0.1.0",'
        '"flow_id":"f","portability":"PORTABLE","mode":"FirstMatch",'
        '"rules":[]}'
    )
    ir = PortableFlow.from_json(text)
    assert ir.flow_id == "f"


# -- structural mutations -------------------------------------------------------


def _mutate_expr(expr: dict[str, Any], rng: random.Random, depth: int = 0) -> dict[str, Any]:
    """Randomly mutate an expression dict into adversarial shapes."""
    if depth > 6:
        return expr
    choice = rng.randrange(6)
    if choice == 0:
        return {"op": "bogus_op", "args": []}
    if choice == 1:
        return {"op": rng.choice(["eq", "not", "and"]), "args": "not-a-list"}
    if choice == 2:
        return {"op": "eq", "args": [{"op": "field"}, {"op": "const"}]}
    if choice == 3:
        return {"op": "field", "value": 12345}  # non-string field name
    if choice == 4:
        return {"op": "const", "value": {"nested": [1, 2, {"x": None}]}}
    # recurse into args
    out = dict(expr)
    if "args" in out and isinstance(out["args"], list):
        out["args"] = [_mutate_expr(a, rng, depth + 1) for a in out["args"]]
    return out


def test_fuzz_ir_mutations_never_crash() -> None:
    """500 seeded mutations: valid PortableFlow or documented error only."""
    rng = random.Random(20261122)
    for _ in range(500):
        data = _valid_ir()
        data["rules"][0]["condition"] = _mutate_expr(data["rules"][0]["condition"], rng)
        # Randomly corrupt top-level fields too.
        if rng.random() < 0.3:
            data["rules"][0]["kind"] = rng.choice(["bogus", "then", ""])
        if rng.random() < 0.2:
            data["portability"] = "NATIVE"
        try:
            ir = PortableFlow.from_dict(data)
        except _ALLOWED_ERRORS:
            continue
        # If it parsed, it must be a well-formed PortableFlow.
        assert ir.portability in ("PORTABLE", "NATIVE")
        assert all(r.rule_id for r in ir.rules)


def test_fuzz_expr_from_dict_never_crash() -> None:
    rng = random.Random(7)
    for _ in range(300):
        expr = _mutate_expr(
            {"op": "eq", "args": [{"op": "field", "value": "x"}, {"op": "const", "value": 1}]},
            rng,
        )
        try:
            expr_from_dict(expr)
        except _ALLOWED_ERRORS:
            continue


# -- boundary conditions ---------------------------------------------------------


def test_depth_boundary_accepted() -> None:
    # Depth exactly MAX_EXPR_DEPTH must be accepted (SPEC 9.2: >100 rejected).
    expr: dict[str, Any] = {"op": "const", "value": True}
    for _ in range(MAX_EXPR_DEPTH - 1):
        expr = {"op": "not", "args": [expr]}
    # Sanity: this nests to exactly the limit.
    expr_from_dict(expr)


def test_depth_boundary_plus_one_rejected() -> None:
    # MAX_EXPR_DEPTH+1 'not' wrappers puts the innermost node at depth
    # MAX_EXPR_DEPTH+1, which exceeds the limit.
    expr: dict[str, Any] = {"op": "const", "value": True}
    for _ in range(MAX_EXPR_DEPTH + 1):
        expr = {"op": "not", "args": [expr]}
    with pytest.raises(StructureError):
        expr_from_dict(expr)


def test_rule_count_boundary() -> None:
    rules = [
        {
            "rule_id": f"r{i}",
            "kind": "when",
            "condition": {"op": "const", "value": True},
            "transform": {"op": "const", "value": i},
        }
        for i in range(MAX_RULES)
    ]
    data = {
        "spec_version": "0.1.0",
        "flow_id": "f",
        "portability": "PORTABLE",
        "mode": "FirstMatch",
        "rules": rules,
    }
    # Exactly at the limit: accepted (may be slow but must not raise).
    ir = PortableFlow.from_dict(data)
    assert len(ir.rules) == MAX_RULES


# -- transition-table property test (SPEC 9.4, Section 7) ------------------------


def test_outcome_status_always_valid() -> None:
    """Property: every execution yields a status in the closed enum and
    consistent secondary/finalization invariants (SPEC 7 transition table)."""
    from flowsemantics import ExecutionStatus, Flow

    rng = random.Random(99)
    for _ in range(200):
        flow = Flow()
        n = rng.randrange(1, 4)
        for i in range(n):
            flow.when(
                lambda inp, i=i: inp % 2 == i,
                then=lambda inp, i=i: i * 10,
                id=f"r{i}",
            )
        if rng.random() < 0.5:
            flow.default(-1)
        contract = flow.compile()
        outcome = contract.try_execute(rng.randrange(0, 4))
        assert outcome.execution_status in set(ExecutionStatus)
        # Invariant: COMPLETED outcomes never carry a primary exception.
        if outcome.execution_status is ExecutionStatus.COMPLETED:
            assert outcome.primary_exception is None
        # Invariant: secondary_exceptions is always a tuple.
        assert isinstance(outcome.secondary_exceptions, tuple)
