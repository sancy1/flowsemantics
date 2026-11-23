// Conformance runner — conformance/runner-protocol.md.
// Usage: node src/runner.ts --vectors <dir>

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { Flow, type FlowContract } from "./flow.ts";
import { FakeClock } from "./clock.ts";
import { EvaluationMode, FinallyFailurePolicy, type FlowOutcome } from "./types.ts";
import { newFixtureContext, resolveFixture, kindOfException, kindToExceptionType } from "./fixtures.ts";
import type { ConditionFn, ActionFn, GuardFn, ExceptionHandler, ExceptionPredicate, HookFn, CleanupFn } from "./flow.ts";

interface Vector {
  id: string;
  spec_version: string;
  spec_section: string;
  pipeline: Record<string, unknown>;
  input: { fixture: string; params?: Record<string, unknown> };
  expected: Record<string, unknown>;
  trace?: { type: string; rule_id?: string | null; reason?: string | null }[];
  trace_subset?: boolean;
  expected_error?: string;
}

function discover(dir: string): string[] {
  const out: string[] = [];
  for (const e of readdirSync(dir)) {
    const p = join(dir, e);
    if (statSync(p).isDirectory()) out.push(...discover(p));
    else if (e.endsWith(".json")) out.push(p);
  }
  return out.sort();
}

function buildFlow(vector: Vector): Flow | string {
  const pipeline = vector.pipeline;

  if ("portable_ir" in pipeline) {
    try {
      return Flow.fromIr(pipeline.portable_ir);
    } catch (exc) {
      return `portable_ir rejected: ${(exc as Error).message}`;
    }
  }

  const modeRaw = (pipeline.mode as string) ?? "FirstMatch";
  const mode = (EvaluationMode as Record<string, string>)[modeRaw] ??
    Object.values(EvaluationMode).find((m) => m === modeRaw);
  if (!mode) return `unknown evaluation mode: ${modeRaw}`;

  const flow = new Flow().withMode(mode as EvaluationMode);
  const ctx = newFixtureContext();

  for (const rule of (pipeline.rules as Record<string, unknown>[]) ?? []) {
    const kind = (rule.kind as string) ?? "when";
    const rid = String(rule.id);
    const action = resolveFixture(rule.action as never, ctx) as ActionFn;
    const effects = ((rule.effects as { name: string; payload?: unknown }[]) ?? []).map((e) => ({ name: e.name, payload: e.payload }));

    if (kind === "then") {
      flow.then(action, { id: rid, effects });
      continue;
    }
    const condition = resolveFixture(rule.condition as never, ctx) as ConditionFn;
    const guard = rule.guard != null
      ? (resolveFixture(rule.guard as never, ctx) as GuardFn)
      : undefined;
    const opts: { id: string; guard?: GuardFn; priority: number; effects: { name: string; payload?: unknown }[] } = {
      id: rid, priority: Number(rule.priority ?? 0), effects,
    };
    if (guard) opts.guard = guard;
    if (kind === "when_not") flow.whenNot(condition, action, opts);
    else if (kind === "when") flow.when(condition, action, opts);
    else return `unknown rule kind: ${kind}`;
  }

  // catches
  for (const c of (pipeline.catches as Record<string, unknown>[]) ?? []) {
    const ckind = c.kind as string;
    if (ckind === "rethrow") { flow.rethrow(); continue; }
    const cid = c.id as string | undefined;
    if (ckind === "any") {
      flow.catchAny(resolveFixture(c.handler as never, ctx) as ExceptionHandler, cid !== undefined ? { id: cid } : {});
      continue;
    }
    const excType = kindToExceptionType(String(c.exc_kind));
    const handler = resolveFixture(c.handler as never, ctx) as ExceptionHandler;
    const copts = cid !== undefined ? { id: cid } : {};
    if (ckind === "typed") {
      flow.catch(excType, handler, copts);
    } else if (ckind === "when") {
      const predRaw = resolveFixture(c.predicate as never, ctx) as ConditionFn;
      const predicate: ExceptionPredicate = (i, e) => Boolean(predRaw(i));
      flow.catchWhen(excType, predicate, handler, copts);
    } else {
      return `unknown catch kind: ${ckind}`;
    }
  }

  // hooks
  for (const h of (pipeline.on_match as Record<string, unknown>[]) ?? []) {
    flow.onMatch(resolveFixture(h as never, ctx) as HookFn);
  }

  // finalizer
  const fin = pipeline.finally;
  if (fin != null) {
    const ref = typeof fin === "string" ? { fixture: fin } : (fin as Record<string, unknown>);
    flow.finally_(resolveFixture(ref as never, ctx) as CleanupFn);
  }
  if (pipeline.finally_policy != null) {
    flow.withFinallyPolicy(pipeline.finally_policy as FinallyFailurePolicy);
  }
  if (pipeline.finally_timeout_ms != null) {
    flow.withFinallyTimeout(Number(pipeline.finally_timeout_ms));
  }

  // fallback
  const fb = pipeline.fallback as Record<string, unknown> | undefined;
  if (fb) {
    if (fb.kind === "otherwise") {
      flow.otherwise(resolveFixture(fb.action as never, ctx) as ActionFn);
    } else if (fb.kind === "default_if_no_match") {
      flow.defaultIfNoMatch(fb.value);
    } else {
      return `unknown fallback kind: ${fb.kind}`;
    }
  }
  return flow;
}

function compareExpected(outcome: FlowOutcome, expected: Record<string, unknown>): string | null {
  const exp = expected;
  if (outcome.execution_status !== exp.execution_status) {
    return `execution_status: expected ${exp.execution_status}, got ${outcome.execution_status}`;
  }
  const gotDecision = outcome.decision_status;
  if ((exp.decision_status ?? null) !== gotDecision) {
    return `decision_status: expected ${exp.decision_status}, got ${gotDecision}`;
  }
  if ("value" in exp && !deepEqual(outcome.value, exp.value)) {
    return `value: expected ${JSON.stringify(exp.value)}, got ${JSON.stringify(outcome.value)}`;
  }
  if (Boolean(exp.has_recovery) !== (outcome.recovery !== null)) return "has_recovery mismatch";
  if (Boolean(exp.has_interruption) !== (outcome.interruption !== null)) return "has_interruption mismatch";
  const gotKind = outcome.interruption?.kind ?? null;
  if ((exp.interruption_kind ?? null) !== gotKind) {
    return `interruption_kind: expected ${exp.interruption_kind}, got ${gotKind}`;
  }
  if (Boolean(exp.has_finalization) !== (outcome.finalization !== null)) return "has_finalization mismatch";
  const gotClean = outcome.finalization?.is_clean ?? null;
  if ((exp.is_clean ?? null) !== gotClean) return `is_clean: expected ${exp.is_clean}, got ${gotClean}`;
  const expSec = Number(exp.secondary_exceptions_count ?? 0);
  if (expSec !== outcome.secondary_exceptions.length) {
    return `secondary_exceptions_count: expected ${expSec}, got ${outcome.secondary_exceptions.length}`;
  }
  const gotPrimary = outcome.primary_exception ? kindOfException(outcome.primary_exception) : null;
  if ((exp.primary_exception_kind ?? null) !== gotPrimary) {
    return `primary_exception_kind: expected ${exp.primary_exception_kind}, got ${gotPrimary}`;
  }
  if (exp.effects !== undefined) {
    const got = outcome.effects.map((e) => ({ name: e.name, payload: e.payload ?? null }));
    const want = (exp.effects as { name: string; payload?: unknown }[]).map((e) => ({ name: e.name, payload: e.payload ?? null }));
    if (JSON.stringify(got) !== JSON.stringify(want)) {
      return `effects: expected ${JSON.stringify(want)}, got ${JSON.stringify(got)}`;
    }
  }
  return null;
}

function deepEqual(a: unknown, b: unknown): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

function compareTrace(vector: Vector, outcome: FlowOutcome): string | null {
  if (!vector.trace) return null;
  if (!outcome.trace) return "trace expected but not collected";
  const observed = outcome.trace.events.map((e) => ({ type: e.type, rule_id: e.rule_id, reason: e.reason }));
  const expected = vector.trace.map((e) => ({ type: e.type, rule_id: e.rule_id ?? null, reason: e.reason ?? null }));
  const matches = (o: typeof observed[number], e: typeof expected[number]) =>
    o.type === e.type &&
    (e.rule_id == null || o.rule_id === e.rule_id) &&
    (e.reason == null || o.reason === e.reason);
  if (vector.trace_subset) {
    let pos = 0;
    for (const e of expected) {
      let found = false;
      while (pos < observed.length) {
        if (matches(observed[pos]!, e)) { found = true; pos++; break; }
        pos++;
      }
      if (!found) return `trace subset: missing ${JSON.stringify(e)}`;
    }
    return null;
  }
  if (observed.length !== expected.length) {
    return `trace length: expected ${expected.length}, got ${observed.length}`;
  }
  for (let i = 0; i < expected.length; i++) {
    if (!matches(observed[i]!, expected[i]!)) {
      return `trace[${i}]: expected ${JSON.stringify(expected[i])}, got ${JSON.stringify(observed[i])}`;
    }
  }
  return null;
}

async function runVector(path: string): Promise<{ id: string; passed: boolean; reason: string }> {
  let vector: Vector;
  try {
    vector = JSON.parse(readFileSync(path, "utf-8")) as Vector;
  } catch (exc) {
    return { id: path, passed: false, reason: `runner failure: parse: ${(exc as Error).message}` };
  }
  const id = vector.id ?? path;
  if (!vector.pipeline || !("rules" in vector.pipeline) && !("portable_ir" in vector.pipeline)) {
    return { id, passed: false, reason: "runner failure: pipeline.rules or portable_ir missing" };
  }
  const expectedError = vector.expected_error;
  const built = buildFlow(vector);
  if (typeof built === "string") {
    return expectedError !== undefined
      ? { id, passed: built.includes(expectedError), reason: built }
      : { id, passed: false, reason: built };
  }
  let input: unknown;
  try {
    input = resolveFixture(vector.input, newFixtureContext());
  } catch (exc) {
    const msg = `fixture resolution failed: ${(exc as Error).message}`;
    return expectedError !== undefined
      ? { id, passed: msg.includes(expectedError), reason: msg }
      : { id, passed: false, reason: msg };
  }
  let contract: FlowContract;
  try {
    contract = built.compile();
  } catch (exc) {
    const msg = `compile failed: ${(exc as Error).message}`;
    return expectedError !== undefined
      ? { id, passed: msg.includes(expectedError), reason: msg }
      : { id, passed: false, reason: msg };
  }
  const clock = new FakeClock();
  const traceEnabled = vector.trace !== undefined;
  let outcome: FlowOutcome;
  try {
    if (vector.pipeline.execution === "async") {
      outcome = await contract.tryExecuteAsync(input, { clock, trace: traceEnabled });
    } else {
      outcome = contract.tryExecute(input, { clock, trace: traceEnabled });
    }
  } catch (exc) {
    const msg = `execution threw: ${(exc as Error).message}`;
    return expectedError !== undefined
      ? { id, passed: msg.includes(expectedError), reason: msg }
      : { id, passed: false, reason: msg };
  }
  if (expectedError !== undefined) {
    return { id, passed: false, reason: `expected rejection containing ${JSON.stringify(expectedError)} but execution completed` };
  }
  const mismatch = compareExpected(outcome, vector.expected);
  if (mismatch) return { id, passed: false, reason: mismatch };
  const traceErr = compareTrace(vector, outcome);
  if (traceErr) return { id, passed: false, reason: traceErr };
  return { id, passed: true, reason: "" };
}

async function main(): Promise<number> {
  const args = process.argv.slice(2);
  const idx = args.indexOf("--vectors");
  if (idx < 0 || !args[idx + 1]) {
    console.error("usage: node src/runner.ts --vectors <dir>");
    return 2;
  }
  const dir = resolve(args[idx + 1]!);
  const paths = discover(dir);
  if (!paths.length) {
    console.log("RESULT: 0/0 passed (no vectors discovered)");
    return 0;
  }
  let passed = 0;
  for (const p of paths) {
    const r = await runVector(p);
    if (r.passed) { passed++; console.log(`PASS ${r.id}`); }
    else console.log(`FAIL ${r.id}: ${r.reason}`);
  }
  console.log(`RESULT: ${passed}/${paths.length} passed`);
  return passed === paths.length ? 0 : 1;
}

process.exit(await main());
