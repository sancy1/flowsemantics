// Unit tests — node:test runner, zero deps.
// Run: node --test tests/engine.test.ts

import { test } from "node:test";
import assert from "node:assert/strict";
import { Flow } from "../src/flow.ts";
import { EvaluationMode, ExecutionStatus, DecisionStatus, FinallyFailurePolicy } from "../src/types.ts";
import { KindAny, KindCancelled, KindValueError, KindTimeout, StructureError } from "../src/errors.ts";
import { portableFlowFromDict, MAX_EXPR_DEPTH } from "../src/portable.ts";
import { FakeClock } from "../src/clock.ts";

test("when match produces APPROVED + value", () => {
  const c = new Flow().when(() => true, () => "ok", { id: "r1" }).compile();
  const o = c.tryExecute({});
  assert.equal(o.execution_status, ExecutionStatus.COMPLETED);
  assert.equal(o.decision_status, DecisionStatus.APPROVED);
  assert.equal(o.value, "ok");
});

test("no match without fallback is NO_MATCH", () => {
  const c = new Flow().when(() => false, () => "x").compile();
  const o = c.tryExecute({});
  assert.equal(o.decision_status, DecisionStatus.NO_MATCH);
  assert.equal(o.value, null);
});

test("when_not inverts condition", () => {
  const c = new Flow().whenNot(() => true, () => "no").when(() => true, () => "yes").compile();
  assert.equal(c.tryExecute({}).value, "yes");
});

test("FirstMatch stops at first match", () => {
  let second = 0;
  const c = new Flow()
    .when(() => true, () => "first")
    .when(() => { second++; return true; }, () => "second")
    .compile();
  assert.equal(c.tryExecute({}).value, "first");
  assert.equal(second, 0);
});

test("AllMatch evaluates all, last wins", () => {
  const c = new Flow()
    .withMode(EvaluationMode.ALL_MATCH)
    .when(() => true, () => "a")
    .when(() => true, () => "b")
    .compile();
  assert.equal(c.tryExecute({}).value, "b");
});

test("Priority orders by priority desc, first match wins", () => {
  const c = new Flow()
    .withMode(EvaluationMode.PRIORITY)
    .when(() => true, () => "low", { priority: 1 })
    .when(() => true, () => "high", { priority: 10 })
    .compile();
  assert.equal(c.tryExecute({}).value, "high");
});

test("then receives previous output", () => {
  const c = new Flow()
    .when(() => true, () => 1)
    .then((_i, prev) => (prev as number) + 1)
    .compile();
  assert.equal(c.tryExecute({}).value, 2);
});

test("guard vetoes true condition", () => {
  const c = new Flow()
    .when(() => true, () => "x", { guard: () => false })
    .compile();
  assert.equal(c.tryExecute({}).decision_status, DecisionStatus.NO_MATCH);
});

test("typed catch recovers with RecoveryInfo", () => {
  const c = new Flow()
    .when(() => true, () => { throw new KindValueError("boom"); })
    .catch(KindValueError as never, () => "recovered")
    .compile();
  const o = c.tryExecute({});
  assert.equal(o.execution_status, ExecutionStatus.COMPLETED);
  assert.equal(o.value, "recovered");
  assert.ok(o.recovery);
  assert.equal(o.decision_status, null);
});

test("uncaught exception is FAILED", () => {
  const c = new Flow()
    .when(() => true, () => { throw new KindValueError("boom"); })
    .compile();
  const o = c.tryExecute({});
  assert.equal(o.execution_status, ExecutionStatus.FAILED);
  assert.ok(o.primary_exception instanceof KindValueError);
});

test("catch_any handles uncaught kinds", () => {
  const c = new Flow()
    .when(() => true, () => { throw new KindAny("x"); })
    .catchAny(() => "any")
    .compile();
  assert.equal(c.tryExecute({}).value, "any");
});

test("rethrow propagates", () => {
  const c = new Flow()
    .when(() => true, () => { throw new KindValueError("x"); })
    .rethrow()
    .catch(KindValueError as never, () => "no")
    .compile();
  assert.equal(c.tryExecute({}).execution_status, ExecutionStatus.FAILED);
});

test("catch handler failure propagates new exception", () => {
  const c = new Flow()
    .when(() => true, () => { throw new KindValueError("orig"); })
    .catch(KindValueError as never, () => { throw new KindTimeout("new"); })
    .compile();
  const o = c.tryExecute({});
  assert.equal(o.execution_status, ExecutionStatus.FAILED);
  assert.ok(o.primary_exception instanceof KindTimeout);
});

test("hook failure isolated to secondary_exceptions", () => {
  const c = new Flow()
    .when(() => true, () => "v")
    .onMatch(() => { throw new Error("hook"); })
    .compile();
  const o = c.tryExecute({});
  assert.equal(o.value, "v");
  assert.equal(o.secondary_exceptions.length, 1);
});

test("cancelled interruption bypasses catches", () => {
  const c = new Flow()
    .when(() => true, () => { throw new KindCancelled("c"); })
    .catchAny(() => "should-not-happen")
    .compile();
  const o = c.tryExecute({});
  assert.equal(o.execution_status, ExecutionStatus.CANCELLED);
  assert.equal(o.interruption?.kind, "cancelled");
});

test("timeout interruption recognized", () => {
  const c = new Flow()
    .when(() => true, () => { throw new KindTimeout("t"); })
    .catchAny(() => "should-not-happen")
    .compile();
  const o = c.tryExecute({});
  assert.equal(o.execution_status, ExecutionStatus.TIMED_OUT);
  assert.equal(o.interruption?.kind, "timed_out");
});

test("finally runs on success, is_clean true", () => {
  let ran = false;
  const c = new Flow()
    .when(() => true, () => "v")
    .finally_(() => { ran = true; })
    .compile();
  const o = c.tryExecute({});
  assert.ok(ran);
  assert.equal(o.finalization?.is_clean, true);
});

test("finally runs on failure", () => {
  let ran = false;
  const c = new Flow()
    .when(() => true, () => { throw new KindValueError("x"); })
    .finally_(() => { ran = true; })
    .compile();
  const o = c.tryExecute({});
  assert.ok(ran);
  assert.equal(o.execution_status, ExecutionStatus.FAILED);
});

test("finally throw PreservePrimary keeps primary", () => {
  const c = new Flow()
    .when(() => true, () => { throw new KindValueError("primary"); })
    .finally_(() => { throw new Error("cleanup"); })
    .compile();
  const o = c.tryExecute({});
  assert.ok(o.primary_exception instanceof KindValueError);
  assert.equal(o.finalization?.is_clean, false);
  assert.equal(o.secondary_exceptions.length, 1);
});

test("finally ReplacePrimary swaps on FAILED", () => {
  const c = new Flow()
    .withFinallyPolicy(FinallyFailurePolicy.REPLACE_PRIMARY)
    .when(() => true, () => { throw new KindValueError("primary"); })
    .finally_(() => { throw new KindTimeout("cleanup"); })
    .compile();
  const o = c.tryExecute({});
  assert.ok(o.primary_exception instanceof KindTimeout);
  assert.equal(o.secondary_exceptions.length, 2);
});

test("effects proposed in evaluation order", () => {
  const c = new Flow()
    .withMode(EvaluationMode.ALL_MATCH)
    .when(() => true, () => "a", { effects: [{ name: "e1" }] })
    .when(() => true, () => "b", { effects: [{ name: "e2", payload: { x: 1 } }] })
    .compile();
  const o = c.tryExecute({});
  assert.deepEqual(o.effects.map((e) => e.name), ["e1", "e2"]);
});

test("trace collects events when enabled", () => {
  const c = new Flow()
    .when(() => false, () => "x", { id: "r1" })
    .when(() => true, () => "y", { id: "r2" })
    .compile();
  const o = c.tryExecute({}, { trace: true });
  assert.ok(o.trace);
  const types = o.trace!.events.map((e) => e.type);
  assert.ok(types.includes("rule_skipped"));
  assert.ok(types.includes("action_executed"));
});

test("sync rejects awaitable results", async () => {
  const c = new Flow()
    .when(() => true, () => Promise.resolve("x"))
    .compile();
  const o = c.tryExecute({});
  assert.equal(o.execution_status, ExecutionStatus.FAILED);
  assert.ok(o.primary_exception instanceof StructureError);
  const oa = await c.tryExecuteAsync({});
  assert.equal(oa.value, "x");
});

test("async parity: same outcome", async () => {
  const build = () => new Flow()
    .when(() => true, () => "v", { effects: [{ name: "n" }] })
    .compile();
  const sync = build().tryExecute({});
  const asy = await build().tryExecuteAsync({});
  assert.equal(sync.value, asy.value);
  assert.equal(sync.decision_status, asy.decision_status);
  assert.deepEqual(sync.effects, asy.effects);
});

test("portable IR round trip via fromIr", () => {
  const c = Flow.fromIr({
    spec_version: "0.1.0", flow_id: "f", portability: "PORTABLE",
    mode: "FirstMatch",
    rules: [{
      rule_id: "r1", kind: "when",
      condition: { op: "gt", args: [{ op: "field", value: "x" }, { op: "const", value: 0 }] },
      transform: { op: "const", value: "pos" },
    }],
    fallback: { kind: "default_if_no_match", value: "neg" },
  }).compile();
  assert.equal(c.tryExecute({ x: 5 }).value, "pos");
  assert.equal(c.tryExecute({ x: -1 }).value, "neg");
});

test("IR rejects duplicate rule ids", () => {
  const rule = { rule_id: "d", kind: "when", condition: { op: "const", value: true }, transform: { op: "const", value: 1 } };
  assert.throws(() => portableFlowFromDict({
    spec_version: "0.1.0", flow_id: "f", portability: "PORTABLE", mode: "FirstMatch",
    rules: [rule, { ...rule }],
  }), StructureError);
});

test("IR rejects excessive depth", () => {
  let expr: Record<string, unknown> = { op: "const", value: true };
  for (let i = 0; i < MAX_EXPR_DEPTH + 2; i++) expr = { op: "not", args: [expr] };
  assert.throws(() => portableFlowFromDict({
    spec_version: "0.1.0", flow_id: "f", portability: "PORTABLE", mode: "FirstMatch",
    rules: [{ rule_id: "r", kind: "when", condition: expr, transform: { op: "const", value: 1 } }],
  }), StructureError);
});

test("IR rejects then kind (ADR-0003)", () => {
  assert.throws(() => portableFlowFromDict({
    spec_version: "0.1.0", flow_id: "f", portability: "PORTABLE", mode: "FirstMatch",
    rules: [{ rule_id: "t", kind: "then", transform: { op: "const", value: 1 } }],
  }), StructureError);
});

test("FakeClock is deterministic", () => {
  const c1 = new FakeClock(1000, 0);
  const c2 = new FakeClock(1000, 0);
  assert.equal(c1.wall(), c2.wall());
  c1.advance(5);
  assert.equal(c1.wall(), 1005);
});

// -- trust layer ---------------------------------------------------------------

import { record, replay, sign, shadow, ReplayMode, contractVersionOf } from "../src/trust.ts";
import { ReplayError } from "../src/errors.ts";

test("record + replay DECISION is equivalent", () => {
  const c = new Flow().when(() => true, () => "v").compile();
  const rec = record(c, {});
  const res = replay(rec, c, { mode: ReplayMode.DECISION });
  assert.equal(res.equivalent, true);
  assert.equal(res.outcome?.value, "v");
});

test("replay HISTORICAL returns recorded outcome", () => {
  const c = new Flow().when(() => true, () => "v").compile();
  const rec = record(c, {});
  const res = replay(rec, c, { mode: ReplayMode.HISTORICAL });
  assert.equal(res.outcome?.value, "v");
});

test("replay fails closed on contract version mismatch", () => {
  const c1 = new Flow().when(() => true, () => "v", { id: "r1" }).compile();
  const c2 = new Flow().when(() => true, () => "different", { id: "r2" }).compile();
  const rec = record(c1, {});
  assert.throws(() => replay(rec, c2), ReplayError);
});

test("sign + verify integrity", () => {
  const c = new Flow().when(() => true, () => "v").compile();
  const rec = sign(record(c, {}), "secret");
  const res = replay(rec, c, { mode: ReplayMode.DECISION, integrity_key: "secret" });
  assert.equal(res.equivalent, true);
  const tampered = { ...rec, input: { evil: true } };
  assert.throws(() => replay(tampered, c, { mode: ReplayMode.DECISION, integrity_key: "secret" }), ReplayError);
});

test("tagged record without key fails", () => {
  const c = new Flow().when(() => true, () => "v").compile();
  const rec = sign(record(c, {}), "secret");
  assert.throws(() => replay(rec, c), ReplayError);
});

test("EFFECTS mode requires authorization", () => {
  const c = new Flow().when(() => true, () => "v", { effects: [{ name: "e" }] }).compile();
  const rec = record(c, {});
  assert.throws(() => replay(rec, c, { mode: ReplayMode.EFFECTS }), ReplayError);
  const res = replay(rec, c, { mode: ReplayMode.EFFECTS, authorize_effects: true, effect_executor: () => {} });
  assert.equal(res.effects_applied, 1);
});

test("shadow detects divergence", () => {
  const a = new Flow().when(() => true, () => "same").compile();
  const b = new Flow().when(() => true, () => "different").compile();
  const report = shadow(a, b, [{}, {}]);
  assert.equal(report.total, 2);
  assert.equal(report.divergent, 2);
});

test("contractVersionOf is stable", () => {
  const c = new Flow().when(() => true, () => "v", { id: "r1" }).compile();
  assert.equal(contractVersionOf(c), contractVersionOf(c));
});

// --- advanced features ---

test("merge splices rules and preserves outer fallback", () => {
  const inner = new Flow().when(() => false, () => "inner", { id: "inner1" }).defaultIfNoMatch("inner-fb");
  const outer = new Flow().when(() => true, () => "outer", { id: "outer1" }).defaultIfNoMatch("outer-fb");
  outer.merge(inner);
  const c = outer.compile();
  assert.equal(c.tryExecute(null).value, "outer");
  const noMatch = new Flow().merge(inner).compile();
  assert.equal(noMatch.tryExecute(null).value, "inner-fb");
});

test("merge rejects mode mismatch and duplicate RuleIds", () => {
  assert.throws(() => new Flow().merge(new Flow().withMode(EvaluationMode.ALL_MATCH)), StructureError);
  const a = new Flow().when(() => true, () => 1, { id: "dup" });
  const b = new Flow().when(() => true, () => 2, { id: "dup" });
  assert.throws(() => a.merge(b), StructureError);
});

test("effective dates gate rule firing", () => {
  const from = 1700000000000, until = 1800000000000;
  const c = new Flow().when(() => true, () => "v", { id: "r1", effectiveFrom: from, effectiveUntil: until }).compile();
  assert.equal(c.tryExecute(null, { clock: new FakeClock(0, 0) }).decision_status, DecisionStatus.NO_MATCH);
  assert.equal(c.tryExecute(null, { clock: new FakeClock((from + until) / 2, 0) }).value, "v");
  assert.equal(c.tryExecute(null, { clock: new FakeClock(until + 1, 0) }).decision_status, DecisionStatus.NO_MATCH);
  assert.throws(() => new Flow().when(() => true, () => "v", { id: "r1", effectiveFrom: until, effectiveUntil: from }).compile(), StructureError);
});

test("cancel check produces CANCELLED", () => {
  let cancelled = false;
  const c = new Flow().withCancelCheck(() => cancelled).when(() => true, () => "v", { id: "r1" }).compile();
  cancelled = true;
  assert.equal(c.tryExecute(null).execution_status, ExecutionStatus.CANCELLED);
});

test("simulateBatch produces firing distribution", () => {
  const c = new Flow().when(() => true, () => "v", { id: "r1" }).compile();
  const rep = c.simulateBatch([null, null]);
  assert.equal(rep.total, 2);
  assert.equal(rep.by_decision["APPROVED"], 2);
});

test("portability report classifies native vs portable", () => {
  const native = new Flow().when(() => true, () => "v").compile();
  const rep = native.portability();
  assert.equal(rep.classification, "NATIVE");
  assert.ok(rep.offenders.length > 0);
});

test("validate flags possible_gap and duplicate ids", () => {
  const c = new Flow().when(() => true, () => "v", { id: "r1" }).compile();
  const codes = c.validate().map((i) => i.code);
  assert.ok(codes.includes("possible_gap"));
});

test("finally timeout sets cleanup_budget_exceeded", async () => {
  const c = new Flow().withFinallyTimeout(1)
    .when(() => true, () => "v", { id: "r1" })
    .finally_(() => new Promise((r) => setTimeout(r, 5)))
    .compile();
  const o = await c.tryExecuteAsync(null);
  assert.equal(o.finalization?.cleanup_budget_exceeded, true);
});

import { tableToFlow, type DecisionTable } from "../src/table.ts";

test("decision table FIRST hit policy compiles to flow", () => {
  const table: DecisionTable = {
    hitPolicy: "FIRST",
    rows: [
      { id: "big", conditions: [(i: any) => i.total > 100], action: () => "bulk" },
      { id: "std", conditions: [() => true], action: () => "standard" },
    ],
  };
  const c = tableToFlow(table).compile();
  assert.equal(c.tryExecute({ total: 150 }).value, "bulk");
  assert.equal(c.tryExecute({ total: 50 }).value, "standard");
});

test("decision table COLLECT hit policy collects all matches", () => {
  const table: DecisionTable = {
    hitPolicy: "COLLECT",
    rows: [
      { id: "a", conditions: [() => true], action: () => "x" },
      { id: "b", conditions: [() => true], action: () => "y" },
    ],
  };
  const c = tableToFlow(table).compile();
  const o = c.tryExecute(null);
  assert.equal(o.decision_status, DecisionStatus.APPROVED);
});

test("decision table rejects empty rows and bad policy", () => {
  assert.throws(() => tableToFlow({ rows: [] }));
  assert.throws(() => tableToFlow({ rows: [{ id: "r", conditions: [() => true], action: () => 1 }], hitPolicy: "BOGUS" as any }));
});

import { pconst, pfield, peq, pgt, pand, por, pnot, pis_null, pnot_in, evalExpr, exprToDict, exprFromDict, portableFlowToDict, portableFlowFromJson, OPS } from "../src/portable.ts";
import { FlowContext } from "../src/types.ts";

test("execute propagates unrecovered exception", () => {
  const c = new Flow().when(() => { throw new KindValueError("boom"); }, () => "v").compile();
  assert.throws(() => c.execute(null), /boom/);
  const o = c.tryExecute(null);
  assert.equal(o.execution_status, ExecutionStatus.FAILED);
});

test("executeAsync propagates unrecovered exception", async () => {
  const c = new Flow().when(() => { throw new KindValueError("boom"); }, () => "v").compile();
  await assert.rejects(() => c.executeAsync(null), /boom/);
});

test("finallyAsync marks contract async-only", async () => {
  const c = new Flow().when(() => true, () => "v", { id: "r1" })
    .finallyAsync(async () => {})
    .compile();
  assert.throws(() => c.tryExecute(null), /async-only/);
  const o = await c.tryExecuteAsync(null);
  assert.equal(o.value, "v");
});

test("withClock injects deterministic clock", () => {
  const clock = new FakeClock(1_700_000_000_000, 42);
  const c = new Flow().withClock(clock).when(() => true, () => "v", { id: "r1" }).compile();
  assert.equal(c.clock, clock);
});

test("withFlowId flows into portable IR", () => {
  const c = new Flow().withFlowId("my-flow")
    .whenExpr(pconst(true), pconst("v"), { id: "p1" })
    .compile();
  assert.equal(c.toIR().flow_id, "my-flow");
});

test("diagnostic hook enriches trace events", () => {
  const c = new Flow().when(() => true, () => "v", { id: "r1" }).compile();
  const o = c.tryExecute(null, { trace: true, diagnosticHook: (e: any) => ({ tag: e.type }) });
  assert.ok(o.trace);
  assert.equal(o.trace!.events[0]!.diagnostics?.tag, o.trace!.events[0]!.type);
  assert.ok(o.trace!.events[0]!.contract_version);
});

test("withTrace diagnostic hook applies by default", () => {
  const c = new Flow().withTrace((e: any) => ({ t: e.type }))
    .when(() => true, () => "v", { id: "r1" })
    .compile();
  const o = c.tryExecute(null);
  assert.ok(o.trace!.events.every((e) => e.diagnostics?.t === e.type));
});

test("PExpr builders + dict round trip", () => {
  const e = pand(pgt(pfield("total"), pconst(100)), pnot(pis_null(pfield("sku"))));
  const d = exprToDict(e);
  const back = exprFromDict(d);
  assert.deepEqual(exprToDict(back), d);
  assert.ok(OPS.has("field"));
  assert.equal(evalExpr(pnot_in(pfield("s"), ["a", "b"]), { s: "c" }), true);
  assert.equal(evalExpr(pand(pgt(pfield("t"), pconst(1)), pnot(pis_null(pfield("x")))), { t: 5, x: 1 }), true);
  assert.equal(evalExpr(por(pconst(false), pconst(true)), null), true);
});

test("portableFlowToDict/FromJson round trip", () => {
  const c = new Flow().withFlowId("f")
    .whenExpr(peq(pfield("x"), pconst(1)), pconst("one"), { id: "r1" })
    .compile();
  const ir = c.toIR();
  const dict = portableFlowToDict(ir);
  const back = portableFlowFromJson(JSON.stringify(dict));
  assert.equal(back.flow_id, "f");
  assert.equal(back.rules.length, 1);
});

test("merge accepts FlowContract", () => {
  const inner = new Flow().when(() => false, () => "inner", { id: "i1" }).defaultIfNoMatch("ifb").compile();
  const outer = new Flow().when(() => true, () => "outer", { id: "o1" }).defaultIfNoMatch("ofb");
  outer.merge(inner);
  assert.equal(outer.compile().tryExecute(null).value, "outer");
});

test("FlowContext carries input and clock", () => {
  const clock = new FakeClock();
  const ctx = new FlowContext({ a: 1 }, clock);
  assert.deepEqual(ctx.input, { a: 1 });
  assert.equal(ctx.clock, clock);
});

test("replay reconstructs recorded clock", () => {
  const clock = new FakeClock(1_700_000_000_000, 7);
  const c = new Flow().withClock(clock).when(() => true, () => "v", { id: "r1" }).compile();
  const rec = record(c, null);
  const res = replay(rec, c, { mode: ReplayMode.DECISION });
  assert.equal(res.equivalent, true);
});

test("shadow reports differing_fields", () => {
  const a = new Flow().when(() => true, () => "x", { id: "r1" }).compile();
  const b = new Flow().when(() => true, () => "y", { id: "r1" }).compile();
  const rep = shadow(a, b, [null]);
  assert.equal(rep.differences, 1);
  assert.deepEqual(rep.entries[0]!.differing_fields, ["value"]);
  assert.equal(rep.entries[0]!.index, 0);
});
