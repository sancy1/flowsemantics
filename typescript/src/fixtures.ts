// Fixture vocabulary — spec/fixtures.md. TS adapter for the runner.

import {
  exceptionForKind,
  KindAny,
  KindCancelled,
  KindTimeout,
  KindValueError,
} from "./errors.ts";
import type { ConditionFn, ActionFn, GuardFn, ExceptionHandler, ExceptionPredicate, HookFn, CleanupFn } from "./flow.ts";

/** Mutable context shared across fixture resolutions within one vector run. */
export interface FixtureContext {
  records: { rule_id: string; value: unknown }[];
}

/** Create an empty FixtureContext. */
export function newFixtureContext(): FixtureContext {
  return { records: [] };
}

const INPUTS: Record<string, unknown> = {
  "input.empty": {},
  "input.order_50": { total: 50 },
  "input.order_0": { total: 0 },
  "input.order_large": { total: 10000 },
};

const condTrue: ConditionFn = () => true;
const condFalse: ConditionFn = () => false;
const guardTrue: GuardFn = () => true;
const guardFalse: GuardFn = () => false;

function makeCondReturns(v: boolean): ConditionFn {
  return () => v;
}
function makeCondThrows(kind: string): ConditionFn {
  return () => { throw exceptionForKind(kind); };
}
function makeCondReturnsPerCall(values: boolean[]): ConditionFn {
  let i = 0;
  return () => {
    const v = i < values.length ? values[i]! : values[values.length - 1]!;
    i++;
    return v;
  };
}

function makeActionConst(v: unknown): ActionFn {
  return () => v;
}
function makeActionThrows(kind: string): ActionFn {
  return () => { throw exceptionForKind(kind); };
}
function makeActionPrev(): ActionFn {
  return (_input, previous) => previous;
}

function makeCatchHandles(v: unknown): ExceptionHandler {
  return () => v;
}
function makeCatchThrows(kind: string): ExceptionHandler {
  return () => { throw exceptionForKind(kind); };
}

function makeHookRecords(ctx: FixtureContext): HookFn {
  return (_input, ruleId, value) => { ctx.records.push({ rule_id: ruleId, value }); };
}
function makeHookThrows(kind: string): HookFn {
  return () => { throw exceptionForKind(kind); };
}

const cleanupSucceeds: CleanupFn = () => undefined;
function makeCleanupThrows(kind: string): CleanupFn {
  return () => { throw exceptionForKind(kind); };
}
const cleanupCooperative: CleanupFn = () => undefined;
const cleanupIgnoresToken: CleanupFn = () => undefined;
function makeCleanupDelays(ms: number): CleanupFn {
  return () => { Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms); };
}
function makeEnrichmentDelayed(ms: number): ActionFn {
  return () => {
    Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
    return { delayed_ms: ms };
  };
}

/** Map an abstract error kind to its concrete exception class. */
export function kindToExceptionType(kind: string): new (...args: never[]) => Error {
  switch (kind) {
    case "Kind.Timeout": return KindTimeout as never;
    case "Kind.Cancelled": return KindCancelled as never;
    case "Kind.ValueError": return KindValueError as never;
    case "Kind.Any": return KindAny as never;
    default: throw new Error(`unknown kind: ${kind}`);
  }
}

/** Return the abstract kind name for a concrete exception, or null if none. */
export function kindOfException(exc: unknown): string | null {
  if (exc instanceof KindTimeout) return "Kind.Timeout";
  if (exc instanceof KindCancelled) return "Kind.Cancelled";
  if (exc instanceof KindValueError) return "Kind.ValueError";
  if (exc instanceof KindAny) return "Kind.Any";
  return null;
}

/** Resolve a fixture reference ({fixture, params}) to a value or callable. */
export function resolveFixture(ref: { fixture: string; params?: Record<string, unknown> }, ctx: FixtureContext): unknown {
  const name = ref.fixture;
  const p = ref.params ?? {};
  const req = (k: string): unknown => {
    if (!(k in p)) throw new Error(`missing fixture param: ${k}`);
    return p[k];
  };

  if (name in INPUTS) return INPUTS[name];

  switch (name) {
    case "cond.true": return condTrue;
    case "cond.false": return condFalse;
    case "cond.returns": return makeCondReturns(Boolean(req("value") ?? req("v")));
    case "cond.throws": return makeCondThrows(String(req("kind")));
    case "cond.returns_per_call": return makeCondReturnsPerCall(req("values") as boolean[]);
    case "action.const": return makeActionConst(req("v") ?? req("value"));
    case "action.throws": return makeActionThrows(String(req("kind")));
    case "action.prev": return makeActionPrev();
    case "action.returns": {
      const sub = req("ref") ?? req("fixture_ref");
      return resolveFixture(sub as { fixture: string; params?: Record<string, unknown> }, ctx);
    }
    case "guard.true": return guardTrue;
    case "guard.false": return guardFalse;
    case "catch.handles": return makeCatchHandles(p.v ?? p.value ?? null);
    case "catch.throws": return makeCatchThrows(String(req("kind")));
    case "hook.records": return makeHookRecords(ctx);
    case "hook.throws": return makeHookThrows(String(req("kind")));
    case "cleanup.succeeds": return cleanupSucceeds;
    case "cleanup.throws": return makeCleanupThrows(String(req("kind")));
    case "cleanup.cooperative": return cleanupCooperative;
    case "cleanup.ignores_token": return cleanupIgnoresToken;
    case "cleanup.delays": return makeCleanupDelays(Number(req("ms")));
    case "enrichment.delayed": return makeEnrichmentDelayed(Number(req("ms")));
    default: throw new Error(`unknown fixture: ${name}`);
  }
}
