"""Unit tests for the Phase 1 decision layer: merge, table, compile.

Layer:      Tests
Module:     tests.unit.test_decision_layer
Since:      0.1.0
Implements: SPEC.md sections 4.3, 10.7, 10.8, 10.9
Depends on: pytest, flowsemantics
Used by:    pytest; CI ci.yml
See also:   SPEC.md sections 10.7-10.9

Notes:
  - Merge and DecisionTable vector coverage is deferred: the conformance
    vector schema cannot yet express composed pipelines or tables
    (recorded in conformance/coverage.md).
"""

from __future__ import annotations

from typing import Any

import pytest

from flowsemantics import (
    DecisionTable,
    DecisionTableRow,
    EvaluationMode,
    Flow,
    StructureError,
)


def _const(value: object) -> Any:
    return lambda _input: value


def _true(_input: object) -> bool:
    return True


def _false(_input: object) -> bool:
    return False


# -- merge (SPEC 10.7) ------------------------------------------------------


def test_merge_splices_rules_in_order() -> None:
    inner = Flow().when(_true, then=_const("inner"), id="inner-1")
    outer = Flow().when(_false, then=_const("outer"), id="outer-1").merge(inner)
    outcome = outer.compile().try_execute(None)
    assert outcome.value == "inner"


def test_merge_rejects_mode_mismatch() -> None:
    inner = Flow().with_mode(EvaluationMode.ALL_MATCH)
    outer = Flow()
    with pytest.raises(StructureError):
        outer.merge(inner)


def test_merge_rejects_duplicate_rule_ids() -> None:
    inner = Flow().when(_true, then=_const(1), id="dup")
    outer = Flow().when(_true, then=_const(2), id="dup")
    with pytest.raises(StructureError):
        outer.merge(inner)


def test_merge_outer_fallback_wins() -> None:
    inner = Flow().default_if_no_match("inner-fb")
    outer = Flow().default_if_no_match("outer-fb").merge(inner)
    outcome = outer.compile().try_execute(None)
    assert outcome.value == "outer-fb"


def test_merge_adopts_inner_fallback_when_outer_has_none() -> None:
    inner = Flow().default_if_no_match("inner-fb")
    outer = Flow().merge(inner)
    outcome = outer.compile().try_execute(None)
    assert outcome.value == "inner-fb"


def test_merge_accepts_compiled_contract() -> None:
    contract = Flow().when(_true, then=_const("from-contract"), id="c1").compile()
    outer = Flow().merge(contract)
    outcome = outer.compile().try_execute(None)
    assert outcome.value == "from-contract"


# -- decision table (SPEC 10.8) ----------------------------------------------


def test_table_first_hit_policy() -> None:
    table = DecisionTable(
        rows=(
            DecisionTableRow(id="r1", conditions=(_true,), action=_const("row1")),
            DecisionTableRow(id="r2", conditions=(_true,), action=_const("row2")),
        ),
        hit_policy="FIRST",
    )
    outcome = Flow.from_table(table).compile().try_execute(None)
    assert outcome.value == "row1"


def test_table_collect_maps_to_all_match() -> None:
    table = DecisionTable(
        rows=(
            DecisionTableRow(id="r1", conditions=(_true,), action=_const("row1")),
            DecisionTableRow(id="r2", conditions=(_true,), action=_const("row2")),
        ),
        hit_policy="COLLECT",
    )
    outcome = Flow.from_table(table).compile().try_execute(None)
    assert outcome.value == "row2"


def test_table_priority_orders_by_priority() -> None:
    table = DecisionTable(
        rows=(
            DecisionTableRow(id="r-low", conditions=(_true,), action=_const("low"), priority=1),
            DecisionTableRow(id="r-high", conditions=(_true,), action=_const("high"), priority=9),
        ),
        hit_policy="PRIORITY",
    )
    outcome = Flow.from_table(table).compile().try_execute(None)
    assert outcome.value == "high"


def test_table_conditions_conjoin() -> None:
    table = DecisionTable(
        rows=(
            DecisionTableRow(
                id="r1",
                conditions=(_true, _false),
                action=_const("never"),
            ),
        ),
        hit_policy="FIRST",
    )
    outcome = Flow.from_table(table).compile().try_execute(None)
    assert outcome.decision_status is not None
    assert outcome.decision_status.value == "no_match"


def test_table_rejects_unknown_hit_policy() -> None:
    with pytest.raises(ValueError):
        DecisionTable(rows=(), hit_policy="BOGUS")


# -- compile validation (SPEC 4.3) -------------------------------------------


def test_compile_rejects_duplicate_rule_ids() -> None:
    flow = Flow().when(_true, then=_const(1), id="x").when(_true, then=_const(2), id="x")
    with pytest.raises(StructureError):
        flow.compile()


def test_compile_rejects_empty_flow() -> None:
    with pytest.raises(StructureError):
        Flow().compile()


def test_compile_rejects_then_first() -> None:
    flow = Flow().then(lambda i, p: p, id="t0")
    with pytest.raises(StructureError):
        flow.compile()


def test_compile_is_idempotent() -> None:
    flow = Flow().when(_true, then=_const("v"), id="r1")
    c1 = flow.compile()
    c2 = flow.compile()
    assert c1.rules == c2.rules
    assert c1.mode == c2.mode


def test_builder_usable_after_compile() -> None:
    flow = Flow().when(_true, then=_const("v1"), id="r1")
    first = flow.compile()
    flow.when(_false, then=_const("v2"), id="r2")
    second = flow.compile()
    assert len(first.rules) == 1
    assert len(second.rules) == 2
