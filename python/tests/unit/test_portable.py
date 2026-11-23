"""Unit tests for the Portable IR and expression subset (SPEC 14.2)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from flowsemantics import (
    Effect,
    Flow,
    FlowPortability,
    PortabilityError,
    PortableFlow,
    StructureError,
    eval_expr,
    pand,
    pconst,
    peq,
    pfield,
    pge,
    pgt,
    pin,
    pis_not_null,
    pis_null,
    ple,
    plt,
    pne,
    pnot,
    pnot_in,
    por,
)

# -- expression subset -----------------------------------------------------------------


def test_field_access() -> None:
    assert eval_expr(pfield("total"), {"total": 42}) == 42


def test_field_access_missing_is_none() -> None:
    assert eval_expr(pfield("missing"), {"a": 1}) is None


def test_field_access_requires_mapping() -> None:
    with pytest.raises(StructureError):
        eval_expr(pfield("x"), 42)


def test_all_comparisons() -> None:
    inp = {"a": 5, "b": 5}
    assert eval_expr(peq(pfield("a"), pfield("b")), inp) is True
    assert eval_expr(pne(pfield("a"), pconst(4)), inp) is True
    assert eval_expr(plt(pfield("a"), pconst(6)), inp) is True
    assert eval_expr(ple(pfield("a"), pconst(5)), inp) is True
    assert eval_expr(pgt(pfield("a"), pconst(4)), inp) is True
    assert eval_expr(pge(pfield("a"), pconst(5)), inp) is True


def test_boolean_composition() -> None:
    inp = {"a": 5, "b": 10}
    expr = pand(pgt(pfield("a"), pconst(0)), plt(pfield("b"), pconst(20)))
    assert eval_expr(expr, inp) is True
    expr_or = por(pgt(pfield("a"), pconst(100)), plt(pfield("b"), pconst(20)))
    assert eval_expr(expr_or, inp) is True
    assert eval_expr(pnot(pgt(pfield("a"), pconst(100))), inp) is True


def test_null_checks() -> None:
    inp = {"a": None, "b": 1}
    assert eval_expr(pis_null(pfield("a")), inp) is True
    assert eval_expr(pis_not_null(pfield("b")), inp) is True
    assert eval_expr(pis_not_null(pfield("a")), inp) is False


def test_membership() -> None:
    inp = {"status": "active"}
    assert eval_expr(pin(pfield("status"), ["active", "pending"]), inp) is True
    assert eval_expr(pnot_in(pfield("status"), ["closed"]), inp) is True
    assert eval_expr(pin(pfield("status"), ["closed"]), inp) is False


# -- portable flow execution ---------------------------------------------------------------


def test_when_expr_executes() -> None:
    contract = (
        Flow()
        .with_flow_id("pricing")
        .when_expr(
            pgt(pfield("total"), pconst(100)),
            then=pconst("bulk"),
            id="bulk-rule",
        )
        .when_expr(
            ple(pfield("total"), pconst(100)),
            then=pconst("standard"),
            id="std-rule",
        )
        .compile()
    )
    assert contract.portability is FlowPortability.PORTABLE
    assert contract.try_execute({"total": 150}).value == "bulk"
    assert contract.try_execute({"total": 50}).value == "standard"


def test_when_not_expr() -> None:
    contract = (
        Flow()
        .when_not_expr(
            pin(pfield("status"), ["banned"]),
            then=pconst("allowed"),
            id="allow",
        )
        .compile()
    )
    assert contract.try_execute({"status": "ok"}).value == "allowed"
    assert contract.try_execute({"status": "banned"}).value is None


def test_portable_guard() -> None:
    contract = (
        Flow()
        .when_expr(
            pgt(pfield("total"), pconst(0)),
            then=pconst("positive"),
            id="pos",
            guard=pis_not_null(pfield("region")),
        )
        .compile()
    )
    assert contract.try_execute({"total": 5, "region": "EU"}).value == "positive"
    assert contract.try_execute({"total": 5}).value is None


def test_portable_fallback_in_ir() -> None:
    contract = (
        Flow()
        .when_expr(pgt(pfield("x"), pconst(0)), then=pconst("pos"), id="r1")
        .default("none")
        .compile()
    )
    assert contract.try_execute({"x": -1}).value == "none"
    ir = contract.to_ir()
    assert ir.fallback == {"kind": "default_if_no_match", "value": "none"}


def test_mixed_portable_native_rejected() -> None:
    flow = Flow().when_expr(pconst(True), then=pconst(1), id="p1")
    flow.when(lambda i: True, then=lambda i: 2, id="n1")
    with pytest.raises(StructureError):
        flow.compile()


def test_native_contract_to_ir_raises() -> None:
    contract = Flow().when(lambda i: True, then=lambda i: 1, id="r1").compile()
    with pytest.raises(PortabilityError):
        contract.to_ir()


# -- IR round-trip -------------------------------------------------------------------------


def _sample_portable() -> Any:
    return (
        Flow()
        .with_flow_id("order-routing")
        .when_expr(
            pand(
                pgt(pfield("total"), pconst(100)),
                pin(pfield("region"), ["EU", "US"]),
            ),
            then=pconst("express"),
            id="express",
            guard=pis_not_null(pfield("account")),
        )
        .when_not_expr(
            pin(pfield("status"), ["fraud"]),
            then=pconst("standard"),
            id="std",
        )
        .default("review")
        .compile()
    )


def test_portable_effects_in_ir() -> None:
    contract = (
        Flow()
        .with_flow_id("fx")
        .when_expr(
            pgt(pfield("amount"), pconst(100)),
            then=pconst("review"),
            id="big",
            effects=[Effect("flag-review", {"tier": "high"})],
        )
        .default("ok")
        .compile()
    )
    outcome = contract.try_execute({"amount": 500})
    assert outcome.value == "review"
    assert [e.name for e in outcome.effects] == ["flag-review"]
    assert outcome.effects[0].payload == {"tier": "high"}

    # IR round-trip preserves effects
    rebuilt = Flow.from_ir(contract.to_ir_json()).compile()
    outcome2 = rebuilt.try_execute({"amount": 500})
    assert [e.name for e in outcome2.effects] == ["flag-review"]
    assert outcome2.effects[0].payload == {"tier": "high"}


def test_portable_effect_payload_must_be_json_safe() -> None:
    flow = Flow().when_expr(
        pconst(True),
        then=pconst(1),
        id="r1",
        effects=[Effect("bad", payload=object())],
    )
    with pytest.raises(StructureError):
        flow.compile()


def test_portable_with_catch_is_native() -> None:
    # Catches are not representable in the IR (SPEC 14.2); their presence
    # makes the contract NATIVE rather than silently dropping them (4.4).
    contract = (
        Flow()
        .with_flow_id("fx")
        .when_expr(pconst(True), then=pconst(1), id="r1")
        .catch(ValueError, lambda i, e: "caught")
        .compile()
    )
    assert contract.portability is FlowPortability.NATIVE
    with pytest.raises(PortabilityError):
        contract.to_ir()


def test_portable_with_hook_is_native() -> None:
    contract = (
        Flow()
        .when_expr(pconst(True), then=pconst(1), id="r1")
        .on_match(lambda i, rid, v: None)
        .compile()
    )
    assert contract.portability is FlowPortability.NATIVE


def test_ir_rejects_excessive_depth() -> None:
    # Nest 'not' 150 deep — exceeds MAX_EXPR_DEPTH (SPEC 9.2).
    expr: dict[str, Any] = {"op": "const", "value": True}
    for _ in range(150):
        expr = {"op": "not", "args": [expr]}
    data = {
        "spec_version": "0.1.0",
        "flow_id": "f",
        "portability": "PORTABLE",
        "mode": "FirstMatch",
        "rules": [
            {
                "rule_id": "r1",
                "kind": "when",
                "condition": expr,
                "transform": {"op": "const", "value": 1},
            }
        ],
    }
    with pytest.raises(StructureError):
        PortableFlow.from_dict(data)


def test_ir_rejects_oversized_json() -> None:
    from flowsemantics.configuration.portable import MAX_IR_BYTES

    big = " " * (MAX_IR_BYTES + 1)
    with pytest.raises(StructureError):
        PortableFlow.from_json(big)


def test_ir_rejects_too_many_rules() -> None:
    from flowsemantics.configuration.portable import MAX_RULES

    rules = [
        {
            "rule_id": f"r{i}",
            "kind": "when",
            "condition": {"op": "const", "value": True},
            "transform": {"op": "const", "value": i},
        }
        for i in range(MAX_RULES + 1)
    ]
    data = {
        "spec_version": "0.1.0",
        "flow_id": "f",
        "portability": "PORTABLE",
        "mode": "FirstMatch",
        "rules": rules,
    }
    with pytest.raises(StructureError):
        PortableFlow.from_dict(data)


def test_ir_rejects_duplicate_rule_ids() -> None:
    rule = {
        "rule_id": "dup",
        "kind": "when",
        "condition": {"op": "const", "value": True},
        "transform": {"op": "const", "value": 1},
    }
    data = {
        "spec_version": "0.1.0",
        "flow_id": "f",
        "portability": "PORTABLE",
        "mode": "FirstMatch",
        "rules": [rule, dict(rule)],
    }
    with pytest.raises(StructureError):
        PortableFlow.from_dict(data)


def test_ir_round_trip_json() -> None:
    contract = _sample_portable()
    ir = contract.to_ir()
    text = ir.to_json()
    ir2 = PortableFlow.from_json(text)
    assert ir2.to_dict() == ir.to_dict()


def test_from_ir_rebuilds_executable_flow() -> None:
    contract = _sample_portable()
    ir_json = contract.to_ir_json()
    rebuilt = Flow.from_ir(ir_json).compile()
    for order in (
        {"total": 200, "region": "EU", "account": "a1", "status": "ok"},
        {"total": 50, "region": "EU", "status": "ok"},
        {"total": 200, "region": "EU", "status": "fraud"},
        {"total": 200, "region": "APAC", "status": "ok"},
    ):
        assert rebuilt.try_execute(order).value == contract.try_execute(order).value


def test_from_ir_preserves_flow_id_and_mode() -> None:
    contract = _sample_portable()
    rebuilt = Flow.from_ir(contract.to_ir_json())
    assert rebuilt._flow_id == "order-routing"


def test_ir_contains_no_lambdas() -> None:
    contract = _sample_portable()
    text = contract.to_ir_json()
    data = json.loads(text)
    # Every rule node must be declarative: op/value/args only.
    for rule in data["rules"]:
        for key in ("condition", "guard", "transform"):
            node = rule.get(key)
            if node is not None:
                assert set(node.keys()) <= {"op", "args", "value"}


def test_ir_spec_version_and_contract_version() -> None:
    contract = _sample_portable()
    ir = contract.to_ir()
    assert ir.spec_version == "0.1.0"
    assert ir.contract_version == contract.contract_version
    assert ir.portability == "PORTABLE"
    assert ir.flow_id == "order-routing"
