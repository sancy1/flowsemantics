// Consumer-driven contract tests — TypeScript.
// Written purely from the public documentation. Imports only the packed
// flow-semantics-ts artifact — never the source tree.
// Run: node --test tests/consumer.test.ts

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  Flow,
  EvaluationMode,
  ExecutionStatus,
  DecisionStatus,
  FinallyFailurePolicy,
  FlowContext,
  EVENT_TYPES,
  FlowSemanticsError,
  StructureError,
  PortabilityError,
  AsyncOnlyContractError,
  ReplayError,
  KindCancelled,
  KindTimeout,
  FakeClock,
  SystemClock,
  pfield,
  pconst,
  peq,
  pne,
  plt,
  ple,
  pgt,
  pge,
  pand,
  por,
  pnot,
  pis_null,
  pis_not_null,
  pin,
  pnot_in,
  evalExpr,
  exprToDict,
  exprFromDict,
  portableFlowFromJson,
  MAX_EXPR_DEPTH,
  tableToFlow,
  ReplayMode,
  record,
  replay,
  sign,
  shadow,
  type PExpr,
  type DecisionTable,
  type FlowOutcome,
} from "flow-semantics-ts";

// ---------------------------------------------------------------------------
// Core decision layer (features 1-18)
// ---------------------------------------------------------------------------

test("when produces APPROVED + value (features 1, 3)", () => {
  const c = new Flow()
    .when((i: any) => i.total > 100, () => "big", { id: "big" })
    .compile();
  const o = c.execute({ total: 150 });
  assert.equal(o.execution_status, ExecutionStatus.COMPLETED);
  assert.equal(o.decision_status, DecisionStatus.APPROVED);
  assert.equal(o.value, "big");
});

test("whenNot + otherwise (features 2, 4)", () => {
  const c = new Flow()
    .whenNot((i: any) => i.vip, () => "standard", { id: "std" })
    .otherwise(() => "fallback")
    .compile();
  assert.equal(c.execute({ vip: false }).value, "standard");
  assert.equal(c.execute({ vip: true }).value, "fallback");
});

test("default + defaultIfNoMatch (features 5, 6)", () => {
  const c1 = new Flow().when(() => false, () => "x", { id: "r" }).default("dflt").compile();
  const c2 = new Flow().when(() => false, () => "x", { id: "r" }).defaultIfNoMatch("d2").compile();
  assert.equal(c1.execute({}).value, "dflt");
  assert.equal(c2.execute({}).value, "d2");
});

test("evaluation modes (features 7-9)", () => {
  const build = (mode: EvaluationMode) =>
    new Flow()
      .withMode(mode)
      .when(() => true, () => "a", { id: "a" })
      .when(() => true, () => "b", { id: "b", priority: 5 })
      .compile();
  assert.equal(build(EvaluationMode.FIRST_MATCH).execute({}).value, "a");
  // AllMatch fires every matching rule; last action's value wins.
  assert.equal(build(EvaluationMode.ALL_MATCH).execute({}).value, "b");
  assert.equal(build(EvaluationMode.PRIORITY).execute({}).value, "b");
});

test("guard + rule priority (features 10, 11)", () => {
  const c = new Flow()
    .withMode(EvaluationMode.PRIORITY)
    .when(() => true, () => "unguarded", { id: "low", priority: 1 })
    .when(() => true, () => "guarded", {
      id: "high",
      guard: (i: any) => i.ok,
      priority: 10,
    })
    .compile();
  assert.equal(c.execute({ ok: true }).value, "guarded");
  assert.equal(c.execute({ ok: false }).value, "unguarded");
});

test("effects proposal (feature 12)", () => {
  const c = new Flow()
    .when(() => true, () => "done", {
      id: "r1",
      effects: [{ name: "notify", payload: { to: "ops" } }],
    })
    .compile();
  const o = c.execute({});
  assert.equal(o.value, "done");
  assert.equal(o.effects.length, 1);
  assert.equal(o.effects[0].name, "notify");
});

test("merge Flow + FlowContract (features 13, 14)", () => {
  const inner = new Flow().when((i: any) => i.x > 0, () => "pos", { id: "pos" });
  const contract = new Flow()
    .merge(inner)
    .when((i: any) => i.x < 0, () => "neg", { id: "neg" })
    .compile();
  assert.equal(contract.execute({ x: 1 }).value, "pos");
  assert.equal(contract.execute({ x: -1 }).value, "neg");

  const part = new Flow().when((i: any) => i.x === 0, () => "zero", { id: "zero" }).compile();
  const merged = new Flow().merge(part).compile();
  assert.equal(merged.execute({ x: 0 }).value, "zero");
});

test("decision table + hit policies (features 15, 16)", () => {
  const table: DecisionTable = {
    rows: [
      { id: "small", conditions: [(i: any) => i.n < 10], action: () => "small" },
      { id: "big", conditions: [(i: any) => i.n >= 10], action: () => "big" },
    ],
    hitPolicy: "FIRST",
  };
  const c = tableToFlow(table).compile();
  assert.equal(c.execute({ n: 5 }).value, "small");
  assert.equal(c.execute({ n: 50 }).value, "big");

  for (const policy of ["FIRST", "COLLECT", "PRIORITY", "UNIQUE"] as const) {
    const t: DecisionTable = {
      rows: [{ id: "r1", conditions: [() => true], action: () => "v1" }],
      hitPolicy: policy,
    };
    assert.ok(tableToFlow(t));
  }
});

test("compile validation — duplicate RuleId (feature 17)", () => {
  const flow = new Flow()
    .when(() => true, () => "a", { id: "dup" })
    .when(() => true, () => "b", { id: "dup" });
  assert.throws(() => flow.compile(), StructureError);
});

test("effective dates (feature 18)", () => {
  const c = new Flow()
    .when(() => true, () => "active", {
      id: "r1",
      effectiveFrom: 1_000_000,
      effectiveUntil: 9_000_000_000_000,
    })
    .default("inactive")
    .compile();
  assert.equal(c.execute({}).value, "active");
});

// ---------------------------------------------------------------------------
// Error & execution layer (features 19-33)
// ---------------------------------------------------------------------------

test("catch typed (feature 19)", () => {
  const c = new Flow()
    .when(() => true, () => { throw new ValueError("boom"); }, { id: "r1" })
    .catch(ValueError, (_i: unknown, exc: unknown) => `caught:${(exc as Error).message}`, { id: "h1" })
    .compile();
  const o = c.execute({});
  assert.equal(o.execution_status, ExecutionStatus.COMPLETED);
  assert.ok(o.recovery);
  assert.equal(o.recovery.handler_rule_id, "h1");
});

class ValueError extends Error {}
class RuntimeError extends Error {}

test("catchWhen + catchAny (features 20, 21)", () => {
  const c = new Flow()
    .when(() => true, () => { throw new RuntimeError("x"); }, { id: "r1" })
    .catchWhen(
      RuntimeError,
      (_i: unknown, exc: unknown) => String(exc).includes("skip"),
      () => "predicted",
      { id: "h1" },
    )
    .catchAny(() => "any", { id: "h2" })
    .compile();
  assert.equal(c.execute({}).value, "any");
});

test("rethrow (feature 22)", () => {
  const c = new Flow()
    .when(() => true, () => { throw new ValueError("nope"); }, { id: "r1" })
    .catchWhen(ValueError, () => false, () => "handled", { id: "h1" })
    .rethrow()
    .compile();
  const o = c.tryExecute({});
  assert.equal(o.execution_status, ExecutionStatus.FAILED);
  assert.ok(o.primary_exception);
});

test("onMatch hook (feature 23)", () => {
  const seen: [string, unknown][] = [];
  const c = new Flow()
    .when(() => true, () => "v", { id: "r1" })
    .onMatch((_i: unknown, rid: string, val: unknown) => seen.push([rid, val]))
    .compile();
  c.execute({});
  assert.deepEqual(seen, [["r1", "v"]]);
});

test("cancellation recognition (feature 24)", () => {
  const c = new Flow()
    .when(() => true, () => { throw new KindCancelled("stop"); }, { id: "r1" })
    .compile();
  const o = c.tryExecute({});
  assert.equal(o.execution_status, ExecutionStatus.CANCELLED);
  assert.equal(o.interruption?.kind, "cancelled");
});

test("timeout recognition (feature 25)", () => {
  const c = new Flow()
    .when(() => true, () => { throw new KindTimeout("deadline"); }, { id: "r1" })
    .compile();
  const o = c.tryExecute({});
  assert.equal(o.execution_status, ExecutionStatus.TIMED_OUT);
  assert.equal(o.interruption?.kind, "timed_out");
});

test("cooperative cancel check (feature 26)", () => {
  const c = new Flow()
    .when(() => true, () => "a", { id: "r1" })
    .withCancelCheck(() => true)
    .compile();
  const o = c.tryExecute({});
  assert.equal(o.execution_status, ExecutionStatus.CANCELLED);
});

test("async parity (feature 27)", async () => {
  const c = new Flow()
    .when(async () => true, async () => "async-value", { id: "r1" })
    .compile();
  const o = await c.tryExecuteAsync({});
  assert.equal(o.value, "async-value");
  assert.throws(() => c.execute({}), AsyncOnlyContractError);
});

test("finally + policies (features 28, 29)", () => {
  const cleaned: ExecutionStatus[] = [];
  const c = new Flow()
    .when(() => true, () => "ok", { id: "r1" })
    .finally_((ctx) => cleaned.push(ctx.status))
    .compile();
  const o = c.execute({});
  assert.equal(o.value, "ok");
  assert.deepEqual(cleaned, [ExecutionStatus.COMPLETED]);

  for (const policy of [
    FinallyFailurePolicy.PRESERVE_PRIMARY,
    FinallyFailurePolicy.ATTACH,
    FinallyFailurePolicy.REPLACE_PRIMARY,
  ]) {
    const c2 = new Flow()
      .when(() => true, () => "ok", { id: "r1" })
      .finally_(() => { throw new Error("cleanup"); })
      .withFinallyPolicy(policy)
      .compile();
    assert.ok(c2.tryExecute({}));
  }
});

test("finally timeout budget (feature 30)", () => {
  const c = new Flow()
    .when(() => true, () => "ok", { id: "r1" })
    .finally_(() => {})
    .withFinallyTimeout(50)
    .compile();
  const o = c.execute({});
  assert.ok(o.finalization);
});

test("secondary_exceptions (feature 31)", () => {
  const c = new Flow()
    .when(() => true, () => "v", { id: "r1" })
    .onMatch(() => { throw new Error("hook boom"); })
    .compile();
  const o = c.execute({});
  assert.equal(o.value, "v");
  assert.equal(o.secondary_exceptions.length, 1);
});

test("interruption model (feature 32)", () => {
  const c = new Flow()
    .when(() => true, () => { throw new KindCancelled("x"); }, { id: "r1" })
    .compile();
  const o = c.tryExecute({});
  const info = o.interruption;
  assert.ok(info);
  assert.equal(info.kind, "cancelled");
  assert.ok(info.source);
  assert.ok(info.timestamp);
});

test("FinallyContext + cancellation token (feature 33)", () => {
  const seen: Record<string, unknown> = {};
  const c = new Flow()
    .when(() => true, () => "payload", { id: "r1" })
    .finally_((ctx) => {
      seen.status = ctx.status;
      seen.value = ctx.value;
      seen.has_token = ctx.cancellation_token !== undefined;
      seen.context = ctx.context;
    })
    .compile();
  c.execute({ in: 1 });
  assert.equal(seen.status, ExecutionStatus.COMPLETED);
  assert.equal(seen.value, "payload");
  assert.equal(seen.has_token, true);
  assert.deepEqual(seen.context, { in: 1 });
});

// ---------------------------------------------------------------------------
// Trust semantics (features 34-47)
// ---------------------------------------------------------------------------

function tracedContract() {
  return new Flow()
    .when((i: any) => i.n > 0, () => "pos", { id: "pos" })
    .default("none")
    .withTrace()
    .compile();
}

test("trace vocabulary + opt-in (features 34, 35)", () => {
  const c = tracedContract();
  const o = c.tryExecute({ n: 1 }, { trace: true });
  assert.ok(o.trace);
  assert.ok(o.trace.events.length > 0);
  const types = new Set(o.trace.events.map((e) => e.type));
  assert.ok(types.size > 0);
  assert.ok(EVENT_TYPES.length === 22);

  const plain = new Flow().when(() => true, () => "x", { id: "r" }).compile();
  assert.equal(plain.tryExecute({}).trace, null);
});

test("diagnostic hook (feature 36)", () => {
  const seen: unknown[] = [];
  const c = tracedContract();
  c.tryExecute({ n: 1 }, {
    trace: true,
    diagnosticHook: (ev: any) => { seen.push(ev); return { redacted: true }; },
  });
  assert.ok(seen.length > 0);
});

test("explain (feature 37)", () => {
  const c = tracedContract();
  const o = c.tryExecute({ n: 1 }, { trace: true });
  const text = c.explain(o.trace!);
  assert.ok(text.length > 0);
});

test("simulate + simulateBatch (features 38, 39)", () => {
  const c = tracedContract();
  const sim = c.simulate({ n: 5 });
  assert.equal(sim.decision_status, DecisionStatus.APPROVED);
  assert.equal(sim.value, "pos");

  const batch = c.simulateBatch([{ n: 1 }, { n: -1 }, { n: 2 }]);
  assert.equal(batch.total, 3);
  assert.ok(batch.by_status && batch.by_decision);
});

test("replay record + modes (features 40, 41)", () => {
  const c = tracedContract();
  const rec = record(c, { n: 3 });
  assert.equal(rec.contract_version, c.contractVersion);

  for (const mode of [ReplayMode.SIMULATION, ReplayMode.HISTORICAL, ReplayMode.DECISION]) {
    const res = replay(rec, c, { mode });
    assert.equal(res.mode, mode);
  }

  const applied: unknown[] = [];
  const effC = new Flow()
    .when(() => true, () => "x", { id: "r1", effects: [{ name: "e", payload: 1 }] })
    .compile();
  const effRec = record(effC, {});
  const res = replay(effRec, effC, {
    mode: ReplayMode.EFFECTS,
    effect_executor: (e: unknown) => applied.push(e),
    authorize_effects: true,
  });
  assert.equal(res.effects_applied, 1);
});

test("HMAC integrity + fail-closed (features 42, 43)", () => {
  const c = tracedContract();
  const key = "consumer-secret";
  const rec = sign(record(c, { n: 1 }), key);
  assert.ok(rec.integrity);

  const ok = replay(rec, c, { mode: ReplayMode.SIMULATION, integrity_key: key });
  assert.equal(ok.equivalent, true);

  assert.throws(
    () => replay(rec, c, { mode: ReplayMode.SIMULATION, integrity_key: "wrong" }),
    ReplayError,
  );

  const other = new Flow().when(() => true, () => "different", { id: "r1" }).compile();
  assert.throws(() => replay(rec, other, { mode: ReplayMode.SIMULATION }), ReplayError);
});

test("shadow (feature 44)", () => {
  const current = new Flow()
    .when((i: any) => i.n > 0, () => "pos", { id: "r" })
    .default("neg")
    .compile();
  const candidate = new Flow()
    .when((i: any) => i.n > 10, () => "big", { id: "r" })
    .default("neg")
    .compile();
  const report = shadow(current, candidate, [{ n: 5 }, { n: 50 }]);
  assert.equal(report.total, 2);
  assert.ok(report.differences >= 1);
});

test("validate + contractVersion (features 45, 46)", () => {
  const c = tracedContract();
  const issues = c.validate();
  assert.ok(Array.isArray(issues));
  assert.ok(c.contractVersion);
  assert.equal(tracedContract().contractVersion, c.contractVersion);
});

test("deterministic clock replay (feature 47)", () => {
  const clock = new FakeClock();
  const c = tracedContract();
  const rec = record(c, { n: 1 }, { clock });
  const res = replay(rec, c, { mode: ReplayMode.DECISION });
  assert.equal(res.equivalent, true);
});

// ---------------------------------------------------------------------------
// Portable IR & cross-cutting (features 48-62)
// ---------------------------------------------------------------------------

test("PExpr ops + builders (features 48, 49)", () => {
  const exprs: PExpr[] = [
    pfield("a"), pconst(1),
    peq(pfield("a"), pconst(1)), pne(pfield("a"), pconst(1)),
    plt(pfield("a"), pconst(1)), ple(pfield("a"), pconst(1)),
    pgt(pfield("a"), pconst(1)), pge(pfield("a"), pconst(1)),
    pand(peq(pfield("a"), pconst(1)), pgt(pfield("b"), pconst(0))),
    por(peq(pfield("a"), pconst(1)), peq(pfield("a"), pconst(2))),
    pnot(peq(pfield("a"), pconst(1))),
    pis_null(pfield("a")), pis_not_null(pfield("a")),
    pin(pfield("a"), [1, 2, 3]), pnot_in(pfield("a"), [9]),
  ];
  assert.equal(exprs.length, 15);
  assert.equal(evalExpr(peq(pfield("a"), pconst(1)), { a: 1 }), true);
  assert.equal(evalExpr(pin(pfield("a"), [1, 2]), { a: 2 }), true);
});

test("expr serialization (feature 50)", () => {
  const expr = pand(peq(pfield("x"), pconst(1)), pgt(pfield("y"), pconst(0)));
  const restored = exprFromDict(exprToDict(expr));
  assert.equal(evalExpr(restored, { x: 1, y: 5 }), true);
  assert.equal(evalExpr(restored, { x: 2, y: 5 }), false);
});

test("PortableFlow/PortableRule (feature 51)", () => {
  const ir = new Flow()
    .whenExpr(peq(pfield("n"), pconst(1)), pconst("one"), { id: "r1" })
    .compile()
    .toIR();
  assert.ok(ir.rules.length > 0);
  assert.equal(ir.rules[0].rule_id, "r1");
});

test("whenExpr/whenNotExpr + fromIr (features 52, 53)", () => {
  const c = new Flow()
    .whenExpr(peq(pfield("kind"), pconst("a")), pconst("A"), { id: "ra" })
    .whenNotExpr(peq(pfield("kind"), pconst("a")), pconst("not-a"), { id: "rb" })
    .default("none")
    .compile();
  assert.equal(c.portability().classification, "PORTABLE");
  assert.equal(c.execute({ kind: "a" }).value, "A");
  assert.equal(c.execute({ kind: "b" }).value, "not-a");

  const rebuilt = Flow.fromIr(c.toIR()).compile();
  assert.equal(rebuilt.execute({ kind: "a" }).value, "A");
});

test("toIR + toIRJSON (feature 54)", () => {
  const c = new Flow()
    .whenExpr(peq(pfield("n"), pconst(1)), pconst("one"), { id: "r1" })
    .compile();
  const ir = c.toIR();
  assert.ok(ir.flow_id);
  const js = c.toIRJSON();
  assert.ok(js.includes("r1"));
  const round = portableFlowFromJson(js);
  assert.equal(round.rules[0].rule_id, "r1");
});

test("PORTABLE/NATIVE classification (feature 55)", () => {
  const portable = new Flow()
    .whenExpr(peq(pfield("a"), pconst(1)), pconst(1), { id: "r" })
    .compile();
  assert.equal(portable.portability().classification, "PORTABLE");

  const native = new Flow().when(() => true, () => 1, { id: "r" }).compile();
  assert.equal(native.portability().classification, "NATIVE");
  assert.throws(() => native.toIR(), PortabilityError);
});

test("portability report (feature 56)", () => {
  const c = new Flow()
    .when(() => true, () => 1, { id: "r1" })
    .catch(Error, () => 0)
    .compile();
  const report = c.portability();
  assert.ok(report.classification);
  assert.ok(Array.isArray(report.offenders));
});

test("IR limits (feature 57)", () => {
  assert.ok(MAX_EXPR_DEPTH > 0);
  let deep: Record<string, unknown> = { op: "const", value: 1 };
  for (let i = 0; i < MAX_EXPR_DEPTH + 1; i++) {
    deep = { op: "not", args: [deep] };
  }
  assert.throws(() => exprFromDict(deep), StructureError);
});

test("flow_id + contract_version in IR (feature 58)", () => {
  const c = new Flow()
    .withFlowId("consumer-flow")
    .whenExpr(peq(pfield("a"), pconst(1)), pconst(1), { id: "r1" })
    .compile();
  const ir = c.toIR();
  assert.equal(ir.flow_id, "consumer-flow");
  assert.equal(ir.contract_version, c.contractVersion);
});

test("PortableFlow JSON round-trip (feature 59)", () => {
  const c = new Flow()
    .whenExpr(peq(pfield("a"), pconst(1)), pconst("one"), { id: "r1" })
    .compile();
  const js = c.toIRJSON();
  const restored = portableFlowFromJson(js);
  assert.equal(restored.flow_id, c.toIR().flow_id);
  assert.equal(restored.rules[0].rule_id, "r1");
});

test("FlowContext (feature 60)", () => {
  const ctx = new FlowContext({ x: 1 }, new FakeClock());
  assert.deepEqual(ctx.input, { x: 1 });
  assert.ok(ctx.clock);
  assert.deepEqual(ctx.state, {});
});

test("clocks (feature 61)", () => {
  const sys = new SystemClock();
  assert.ok(sys.wall() > 0);
  assert.ok(sys.monotonic() >= 0);

  const fake = new FakeClock();
  const t1 = fake.wall();
  fake.advance(10_000);
  assert.equal(fake.wall() - t1, 10_000);

  const c = new Flow()
    .when(() => true, () => "ok", { id: "r1" })
    .withClock(new FakeClock())
    .compile();
  assert.equal(c.execute({}).value, "ok");
});

test("withFlowId (feature 62)", () => {
  const c = new Flow()
    .withFlowId("my-flow")
    .whenExpr(peq(pfield("a"), pconst(1)), pconst(1), { id: "r1" })
    .compile();
  assert.equal(c.toIR().flow_id, "my-flow");
});

// ---------------------------------------------------------------------------
// Error hierarchy sanity
// ---------------------------------------------------------------------------

test("error hierarchy", () => {
  for (const E of [StructureError, PortabilityError, AsyncOnlyContractError, ReplayError]) {
    assert.ok(new E("x") instanceof FlowSemanticsError);
  }
});
