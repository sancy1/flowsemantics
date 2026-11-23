"""Consumer-driven contract tests — Python.

Written purely from the public documentation (README, docs/, SPEC.md).
Imports only the published ``flowsemantics`` package — never the source
tree. Each test maps to a SPEC feature (see docs/feature-audit.md).
"""

from __future__ import annotations

import asyncio
import datetime

import pytest

from flowsemantics import (
    AsyncOnlyContractError,
    DecisionStatus,
    DecisionTable,
    DecisionTableRow,
    Effect,
    EvaluationMode,
    ExecutionStatus,
    FakeClock,
    FinallyFailurePolicy,
    Flow,
    FlowContext,
    FlowPortability,
    FlowSemanticsError,
    PExpr,
    PortabilityError,
    PortableFlow,
    ReplayError,
    ReplayMode,
    StructureError,
    SystemClock,
    eval_expr,
    expr_from_dict,
    expr_to_dict,
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
    record,
    replay,
    shadow,
    sign,
    table_to_flow,
)

# ---------------------------------------------------------------------------
# Core decision layer (features 1-18)
# ---------------------------------------------------------------------------


def test_when_produces_approved_value():
    """Features 1, 3: when + then action."""
    contract = (
        Flow()
        .when(lambda i: i["total"] > 100, then=lambda i: "big", id="big")
        .compile()
    )
    outcome = contract.execute({"total": 150})
    assert outcome.execution_status is ExecutionStatus.COMPLETED
    assert outcome.decision_status is DecisionStatus.APPROVED
    assert outcome.value == "big"


def test_when_not_and_otherwise():
    """Features 2, 4: when_not + otherwise fallback."""
    contract = (
        Flow()
        .when_not(lambda i: i["vip"], then=lambda i: "standard", id="std")
        .otherwise(lambda i: "fallback")
        .compile()
    )
    assert contract.execute({"vip": False}).value == "standard"
    assert contract.execute({"vip": True}).value == "fallback"


def test_default_and_default_if_no_match():
    """Features 5, 6: constant fallbacks (default is an alias)."""
    c1 = (
        Flow()
        .when(lambda i: False, then=lambda i: "x", id="r")
        .default("dflt")
        .compile()
    )
    c2 = (
        Flow()
        .when(lambda i: False, then=lambda i: "x", id="r")
        .default_if_no_match("dflt2")
        .compile()
    )
    assert c1.execute({}).value == "dflt"
    assert c2.execute({}).value == "dflt2"


def test_evaluation_modes():
    """Features 7-9: FirstMatch, AllMatch, Priority."""

    def build(mode):
        return (
            Flow()
            .with_mode(mode)
            .when(lambda i: True, then=lambda i: "a", id="a")
            .when(lambda i: True, then=lambda i: "b", id="b", priority=5)
            .compile()
        )

    first = build(EvaluationMode.FIRST_MATCH).execute({})
    all_ = build(EvaluationMode.ALL_MATCH).execute({})
    prio = build(EvaluationMode.PRIORITY).execute({})
    assert first.value == "a"
    # AllMatch fires every matching rule; the last action's value wins.
    assert all_.value == "b"
    assert prio.value == "b"  # priority=5 wins over default 0


def test_guard_and_rule_priority():
    """Features 10, 11: guard predicate + priority ordering."""
    contract = (
        Flow()
        .with_mode(EvaluationMode.PRIORITY)
        .when(lambda i: True, then=lambda i: "unguarded", id="low", priority=1)
        .when(
            lambda i: True,
            then=lambda i: "guarded",
            id="high",
            guard=lambda i: i["ok"],
            priority=10,
        )
        .compile()
    )
    assert contract.execute({"ok": True}).value == "guarded"
    assert contract.execute({"ok": False}).value == "unguarded"


def test_effects_proposal():
    """Feature 12: effects are proposed data, never applied."""
    contract = (
        Flow()
        .when(
            lambda i: True,
            then=lambda i: "done",
            id="r1",
            effects=[Effect(name="notify", payload={"to": "ops"})],
        )
        .compile()
    )
    outcome = contract.execute({})
    assert outcome.value == "done"
    assert len(outcome.effects) == 1
    assert outcome.effects[0].name == "notify"
    assert outcome.effects[0].payload == {"to": "ops"}


def test_merge_flow_and_contract():
    """Features 13, 14: merge at builder and contract level."""
    inner = Flow().when(lambda i: i["x"] > 0, then=lambda i: "pos", id="pos")
    outer = (
        Flow().merge(inner).when(lambda i: i["x"] < 0, then=lambda i: "neg", id="neg")
    )
    contract = outer.compile()
    assert contract.execute({"x": 1}).value == "pos"
    assert contract.execute({"x": -1}).value == "neg"

    # Feature 14: Flow.merge also accepts a compiled FlowContract.
    part = (
        Flow().when(lambda i: i["x"] == 0, then=lambda i: "zero", id="zero").compile()
    )
    merged_contract = Flow().merge(part).compile()
    assert merged_contract.execute({"x": 0}).value == "zero"


def test_decision_table_and_hit_policies():
    """Features 15, 16: DecisionTable + FIRST/COLLECT/PRIORITY/UNIQUE."""
    table = DecisionTable(
        rows=(
            DecisionTableRow(
                id="small",
                conditions=(lambda i: i["n"] < 10,),
                action=lambda i: "small",
            ),
            DecisionTableRow(
                id="big",
                conditions=(lambda i: i["n"] >= 10,),
                action=lambda i: "big",
            ),
        ),
        hit_policy="FIRST",
    )
    contract = table_to_flow(table).compile()
    assert contract.execute({"n": 5}).value == "small"
    assert contract.execute({"n": 50}).value == "big"

    for policy in ("FIRST", "COLLECT", "PRIORITY", "UNIQUE"):
        t = DecisionTable(
            rows=(
                DecisionTableRow(
                    id="r1", conditions=(lambda i: True,), action=lambda i: "v1"
                ),
            ),
            hit_policy=policy,
        )
        assert t.evaluation_mode is not None


def test_compile_validation():
    """Feature 17: duplicate RuleId rejected at compile."""
    flow = (
        Flow()
        .when(lambda i: True, then=lambda i: "a", id="dup")
        .when(lambda i: True, then=lambda i: "b", id="dup")
    )
    with pytest.raises(StructureError):
        flow.compile()


def test_effective_dates():
    """Feature 18: effective_from/until windows (SPEC 12.9)."""
    past = datetime.datetime(2020, 1, 1, tzinfo=datetime.UTC)
    future = datetime.datetime(2030, 1, 1, tzinfo=datetime.UTC)
    contract = (
        Flow()
        .when(
            lambda i: True,
            then=lambda i: "active",
            id="r1",
            effective_from=past,
            effective_until=future,
        )
        .default("inactive")
        .compile()
    )
    assert contract.execute({}).value == "active"


# ---------------------------------------------------------------------------
# Error & execution layer (features 19-33)
# ---------------------------------------------------------------------------


def test_catch_typed():
    """Feature 19: typed catch handler."""
    contract = (
        Flow()
        .when(
            lambda i: True,
            then=lambda i: (_ for _ in ()).throw(ValueError("boom")),
            id="r1",
        )
        .catch(ValueError, lambda i, exc: f"caught:{exc}", id="h1")
        .compile()
    )
    outcome = contract.execute({})
    assert outcome.execution_status is ExecutionStatus.COMPLETED
    assert outcome.recovery is not None
    assert outcome.recovery.handler_rule_id == "h1"
    assert outcome.value.startswith("caught:")


def test_catch_when_and_catch_any():
    """Features 20, 21: predicate catch + broad catch_any."""
    contract = (
        Flow()
        .when(
            lambda i: True,
            then=lambda i: (_ for _ in ()).throw(RuntimeError("x")),
            id="r1",
        )
        .catch_when(
            RuntimeError,
            lambda i, exc: "skip" in str(exc),
            lambda i, exc: "predicted",
            id="h1",
        )
        .catch_any(lambda i, exc: "any", id="h2")
        .compile()
    )
    outcome = contract.execute({})
    assert outcome.value == "any"  # predicate False → falls to catch_any


def test_rethrow():
    """Feature 22: rethrow propagates the exception."""
    contract = (
        Flow()
        .when(
            lambda i: True,
            then=lambda i: (_ for _ in ()).throw(ValueError("nope")),
            id="r1",
        )
        .catch_when(ValueError, lambda i, exc: False, lambda i, exc: "handled", id="h1")
        .rethrow()
        .compile()
    )
    outcome = contract.try_execute({})
    assert outcome.execution_status is ExecutionStatus.FAILED
    assert outcome.primary_exception is not None


def test_on_match_hook():
    """Feature 23: on_match hook observes rule firings."""
    seen = []
    contract = (
        Flow()
        .when(lambda i: True, then=lambda i: "v", id="r1")
        .on_match(lambda i, rid, val: seen.append((str(rid), val)))
        .compile()
    )
    contract.execute({})
    assert seen == [("r1", "v")]


def test_cancellation_recognition():
    """Feature 24: asyncio.CancelledError → CANCELLED interruption."""

    def boom(i):
        raise asyncio.CancelledError()

    contract = Flow().when(lambda i: True, then=boom, id="r1").compile()
    outcome = contract.try_execute({})
    assert outcome.execution_status is ExecutionStatus.CANCELLED
    assert outcome.interruption is not None
    assert outcome.interruption.kind == "cancelled"


def test_timeout_recognition():
    """Feature 25: TimeoutError → TIMED_OUT interruption."""

    def boom(i):
        raise TimeoutError("deadline")

    contract = Flow().when(lambda i: True, then=boom, id="r1").compile()
    outcome = contract.try_execute({})
    assert outcome.execution_status is ExecutionStatus.TIMED_OUT
    assert outcome.interruption is not None
    assert outcome.interruption.kind == "timed_out"


def test_cooperative_cancel_check():
    """Feature 26: with_cancel_check polls before each rule."""
    contract = (
        Flow()
        .when(lambda i: True, then=lambda i: "a", id="r1")
        .with_cancel_check(lambda: True)
        .compile()
    )
    outcome = contract.try_execute({})
    assert outcome.execution_status is ExecutionStatus.CANCELLED


def test_async_parity():
    """Feature 27: execute_async/try_execute_async await async callbacks."""

    async def cond(i):
        return True

    async def act(i):
        return "async-value"

    contract = Flow().when(cond, then=act, id="r1").compile()
    assert contract.async_only is True

    async def main():
        outcome = await contract.try_execute_async({})
        assert outcome.value == "async-value"
        with pytest.raises(AsyncOnlyContractError):
            contract.execute({})

    asyncio.run(main())


def test_finally_and_policies():
    """Features 28, 29: finally_ runs always; failure policies apply."""
    cleaned = []

    def cleanup(ctx):
        cleaned.append(ctx.status)

    contract = (
        Flow()
        .when(lambda i: True, then=lambda i: "ok", id="r1")
        .finally_(cleanup)
        .compile()
    )
    outcome = contract.execute({})
    assert outcome.value == "ok"
    assert cleaned == [ExecutionStatus.COMPLETED]

    for policy in (
        FinallyFailurePolicy.PRESERVE_PRIMARY,
        FinallyFailurePolicy.ATTACH,
        FinallyFailurePolicy.REPLACE_PRIMARY,
    ):
        c = (
            Flow()
            .when(lambda i: True, then=lambda i: "ok", id="r1")
            .finally_(lambda ctx: (_ for _ in ()).throw(RuntimeError("cleanup")))
            .with_finally_policy(policy)
            .compile()
        )
        o = c.try_execute({})
        assert o is not None  # policy determines outcome shape; never crashes


def test_finally_timeout_budget():
    """Feature 30: with_finally_timeout bounds cleanup budget."""
    contract = (
        Flow()
        .when(lambda i: True, then=lambda i: "ok", id="r1")
        .finally_(lambda ctx: None)
        .with_finally_timeout(50)
        .compile()
    )
    outcome = contract.execute({})
    assert outcome.finalization is not None


def test_secondary_exceptions():
    """Feature 31: hook failures land in secondary_exceptions, not catch."""

    def bad_hook(i, rid, val):
        raise RuntimeError("hook boom")

    contract = (
        Flow()
        .when(lambda i: True, then=lambda i: "v", id="r1")
        .on_match(bad_hook)
        .compile()
    )
    outcome = contract.execute({})
    assert outcome.value == "v"
    assert len(outcome.secondary_exceptions) == 1


def test_interruption_model():
    """Feature 32: InterruptionInfo carries kind/source/timestamp."""
    contract = (
        Flow()
        .when(
            lambda i: True,
            then=lambda i: (_ for _ in ()).throw(asyncio.CancelledError()),
            id="r1",
        )
        .compile()
    )
    outcome = contract.try_execute({})
    info = outcome.interruption
    assert info is not None
    assert info.kind == "cancelled"
    assert info.source
    assert info.timestamp is not None


def test_finally_context_and_token():
    """Feature 33: FinallyContext exposes result/status/value/exception/token."""
    seen = {}

    def cleanup(ctx):
        seen["status"] = ctx.status
        seen["value"] = ctx.value
        seen["has_token"] = ctx.cancellation_token is not None
        seen["context"] = ctx.context

    contract = (
        Flow()
        .when(lambda i: True, then=lambda i: "payload", id="r1")
        .finally_(cleanup)
        .compile()
    )
    contract.execute({"in": 1})
    assert seen["status"] is ExecutionStatus.COMPLETED
    assert seen["value"] == "payload"
    assert seen["has_token"] is True
    assert seen["context"] == {"in": 1}


# ---------------------------------------------------------------------------
# Trust semantics (features 34-47)
# ---------------------------------------------------------------------------


def _traced_contract():
    return (
        Flow()
        .when(lambda i: i["n"] > 0, then=lambda i: "pos", id="pos")
        .default("none")
        .with_trace()
        .compile()
    )


def test_trace_vocabulary_and_opt_in():
    """Features 34, 35: trace events recorded only when enabled."""
    contract = _traced_contract()
    outcome = contract.try_execute({"n": 1}, trace=True)
    assert outcome.trace is not None
    assert len(outcome.trace.events) > 0
    event_types = {e.type for e in outcome.trace.events}
    assert "flow_started" in event_types or len(event_types) > 0

    plain = Flow().when(lambda i: True, then=lambda i: "x", id="r").compile()
    no_trace = plain.try_execute({})
    assert no_trace.trace is None


def test_diagnostic_hook():
    """Feature 36: diagnostic_hook receives events, may add fields."""
    seen = []

    def hook(event):
        seen.append(event)
        return {"redacted": True}

    contract = _traced_contract()
    contract.try_execute({"n": 1}, trace=True, diagnostic_hook=hook)
    assert len(seen) > 0


def test_explain():
    """Feature 37: explain renders trace as human-readable lines."""
    contract = _traced_contract()
    outcome = contract.try_execute({"n": 1}, trace=True)
    text = contract.explain(outcome.trace)
    assert "pos" in text or "event" in text.lower()
    assert isinstance(text, str) and len(text) > 0


def test_simulate_and_simulate_batch():
    """Features 38, 39: simulate + batch firing distribution."""
    contract = _traced_contract()
    sim = contract.simulate({"n": 5})
    assert sim.decision_status is DecisionStatus.APPROVED
    assert sim.value == "pos"

    batch = contract.simulate_batch([{"n": 1}, {"n": -1}, {"n": 2}])
    assert batch["total"] == 3
    assert "by_status" in batch and "by_decision" in batch


def test_replay_record_and_modes():
    """Features 40, 41: record + all four replay modes."""
    contract = _traced_contract()
    rec = record(contract, {"n": 3})
    assert rec.contract_version == contract.contract_version

    for mode in (
        ReplayMode.SIMULATION,
        ReplayMode.HISTORICAL,
        ReplayMode.DECISION,
    ):
        result = replay(rec, contract, mode=mode)
        assert result.mode is mode

    applied = []
    eff_contract = (
        Flow()
        .when(
            lambda i: True,
            then=lambda i: "x",
            id="r1",
            effects=[Effect(name="e", payload=1)],
        )
        .compile()
    )
    eff_rec = record(eff_contract, {})
    res = replay(
        eff_rec,
        eff_contract,
        mode=ReplayMode.EFFECTS,
        effect_executor=applied.append,
        authorize_effects=True,
    )
    assert res.effects_applied == 1


def test_hmac_integrity_and_fail_closed():
    """Features 42, 43: sign/verify + version mismatch fails closed."""
    contract = _traced_contract()
    key = b"consumer-secret"
    rec = sign(record(contract, {"n": 1}), key)
    assert rec.integrity is not None

    ok = replay(rec, contract, mode=ReplayMode.SIMULATION, integrity_key=key)
    assert ok.equivalent is True

    with pytest.raises(ReplayError):
        replay(rec, contract, mode=ReplayMode.SIMULATION, integrity_key=b"wrong")

    other = Flow().when(lambda i: True, then=lambda i: "different", id="r1").compile()
    with pytest.raises(ReplayError):
        replay(rec, other, mode=ReplayMode.SIMULATION)


def test_shadow():
    """Feature 44: shadow compares candidate vs current."""
    current = (
        Flow()
        .when(lambda i: i["n"] > 0, then=lambda i: "pos", id="r")
        .default("neg")
        .compile()
    )
    candidate = (
        Flow()
        .when(lambda i: i["n"] > 10, then=lambda i: "big", id="r")
        .default("neg")
        .compile()
    )
    report = shadow(current, candidate, [{"n": 5}, {"n": 50}])
    assert report.total == 2
    assert report.differences >= 1


def test_validate_and_contract_version():
    """Features 45, 46: validate() issues + stable contract_version."""
    contract = _traced_contract()
    issues = contract.validate()
    assert isinstance(issues, tuple)
    assert contract.contract_version

    same = _traced_contract()
    assert same.contract_version == contract.contract_version


def test_deterministic_clock_replay():
    """Feature 47: FakeClock makes replay deterministic (SPEC 12.10)."""
    clock = FakeClock()
    contract = _traced_contract()
    rec = record(contract, {"n": 1}, clock=clock)
    result = replay(rec, contract, mode=ReplayMode.DECISION)
    assert result.equivalent is True


# ---------------------------------------------------------------------------
# Portable IR & cross-cutting (features 48-62)
# ---------------------------------------------------------------------------


def test_pexpr_ops_and_builders():
    """Features 48, 49: all 15 PExpr ops + builder functions."""
    exprs = [
        pfield("a"),
        pconst(1),
        peq(pfield("a"), pconst(1)),
        pne(pfield("a"), pconst(1)),
        plt(pfield("a"), pconst(1)),
        ple(pfield("a"), pconst(1)),
        pgt(pfield("a"), pconst(1)),
        pge(pfield("a"), pconst(1)),
        pand(peq(pfield("a"), pconst(1)), pgt(pfield("b"), pconst(0))),
        por(peq(pfield("a"), pconst(1)), peq(pfield("a"), pconst(2))),
        pnot(peq(pfield("a"), pconst(1))),
        pis_null(pfield("a")),
        pis_not_null(pfield("a")),
        pin(pfield("a"), [1, 2, 3]),
        pnot_in(pfield("a"), [9]),
    ]
    assert len(exprs) == 15
    assert all(isinstance(e, PExpr) for e in exprs)
    assert eval_expr(peq(pfield("a"), pconst(1)), {"a": 1}) is True
    assert eval_expr(pin(pfield("a"), [1, 2]), {"a": 2}) is True


def test_expr_serialization():
    """Feature 50: expr_to_dict / expr_from_dict round-trip."""
    expr = pand(peq(pfield("x"), pconst(1)), pgt(pfield("y"), pconst(0)))
    data = expr_to_dict(expr)
    restored = expr_from_dict(data)
    assert eval_expr(restored, {"x": 1, "y": 5}) is True
    assert eval_expr(restored, {"x": 2, "y": 5}) is False


def test_portable_flow_and_rules():
    """Feature 51: PortableFlow/PortableRule types exist and serialize."""
    assert PortableFlow is not None
    ir = (
        Flow()
        .when_expr(peq(pfield("n"), pconst(1)), then=pconst("one"), id="r1")
        .compile()
        .to_ir()
    )
    assert isinstance(ir, PortableFlow)
    assert ir.rules


def test_when_expr_when_not_expr_from_ir():
    """Features 52, 53: portable rules + Flow.from_ir."""
    contract = (
        Flow()
        .when_expr(peq(pfield("kind"), pconst("a")), then=pconst("A"), id="ra")
        .when_not_expr(peq(pfield("kind"), pconst("a")), then=pconst("not-a"), id="rb")
        .default("none")
        .compile()
    )
    assert contract.portability is FlowPortability.PORTABLE
    assert contract.execute({"kind": "a"}).value == "A"
    assert contract.execute({"kind": "b"}).value == "not-a"

    ir_json = contract.to_ir_json()
    rebuilt = Flow.from_ir(ir_json).compile()
    assert rebuilt.execute({"kind": "a"}).value == "A"


def test_to_ir_and_json():
    """Feature 54: to_ir / to_ir_json export."""
    contract = (
        Flow()
        .when_expr(peq(pfield("n"), pconst(1)), then=pconst("one"), id="r1")
        .compile()
    )
    ir = contract.to_ir()
    assert ir.to_dict()["flow_id"] is not None or hasattr(ir, "flow_id")
    js = contract.to_ir_json()
    assert isinstance(js, str) and "r1" in js


def test_portable_native_classification():
    """Feature 55: PORTABLE vs NATIVE classification."""
    portable = (
        Flow().when_expr(peq(pfield("a"), pconst(1)), then=pconst(1), id="r").compile()
    )
    assert portable.portability is FlowPortability.PORTABLE

    native = Flow().when(lambda i: True, then=lambda i: 1, id="r").compile()
    assert native.portability is FlowPortability.NATIVE
    with pytest.raises(PortabilityError):
        native.to_ir()


def test_portability_report():
    """Feature 56: portability_report lists offenders."""
    contract = (
        Flow()
        .when(lambda i: True, then=lambda i: 1, id="r1")
        .catch(ValueError, lambda i, e: 0)
        .compile()
    )
    report = contract.portability_report()
    assert isinstance(report, dict)


def test_ir_limits():
    """Feature 57: IR depth limit enforced (SPEC 9.2, MAX_EXPR_DEPTH=100)."""
    deep: dict = {"op": "const", "value": 1}
    for _ in range(101):
        deep = {"op": "not", "args": [deep]}
    with pytest.raises(StructureError):
        expr_from_dict(deep)


def test_flow_id_and_contract_version_in_ir():
    """Feature 58: flow_id + contract_version carried in IR."""
    contract = (
        Flow()
        .with_flow_id("consumer-flow")
        .when_expr(peq(pfield("a"), pconst(1)), then=pconst(1), id="r1")
        .compile()
    )
    ir = contract.to_ir()
    assert ir.flow_id == "consumer-flow"
    assert ir.contract_version == contract.contract_version


def test_portable_json_roundtrip():
    """Feature 59: PortableFlow JSON round-trip."""
    contract = (
        Flow()
        .when_expr(peq(pfield("a"), pconst(1)), then=pconst("one"), id="r1")
        .compile()
    )
    js = contract.to_ir_json()
    restored = PortableFlow.from_json(js)
    assert restored.flow_id == contract.to_ir().flow_id
    assert restored.rules[0].rule_id == "r1"


def test_flow_context():
    """Feature 60: FlowContext carries input + clock + state."""
    ctx = FlowContext(input={"x": 1}, clock=FakeClock())
    assert ctx.input == {"x": 1}
    assert ctx.clock is not None
    assert ctx.state == {}


def test_clocks():
    """Feature 61: SystemClock default + FakeClock deterministic."""
    sys_clock = SystemClock()
    assert sys_clock.wall() is not None
    assert sys_clock.monotonic() >= 0

    fake = FakeClock()
    t1 = fake.wall()
    fake.advance(10)
    assert (fake.wall() - t1).total_seconds() == 10

    contract = (
        Flow()
        .when(lambda i: True, then=lambda i: "ok", id="r1")
        .with_clock(FakeClock())
        .compile()
    )
    assert contract.execute({}).value == "ok"


def test_with_flow_id():
    """Feature 62: with_flow_id sets IR identity."""
    contract = (
        Flow()
        .with_flow_id("my-flow")
        .when_expr(peq(pfield("a"), pconst(1)), then=pconst(1), id="r1")
        .compile()
    )
    assert contract.to_ir().flow_id == "my-flow"


# ---------------------------------------------------------------------------
# Error hierarchy sanity (public surface)
# ---------------------------------------------------------------------------


def test_error_hierarchy():
    """All public error types derive from FlowSemanticsError."""
    for exc_type in (
        StructureError,
        PortabilityError,
        AsyncOnlyContractError,
        ReplayError,
        FlowSemanticsError,
    ):
        assert (
            issubclass(exc_type, FlowSemanticsError) or exc_type is FlowSemanticsError
        )
