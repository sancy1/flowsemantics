// Trust layer — SPEC.md 12.5-12.8, 9.5. Parity with python trust/.

import { createHmac } from "node:crypto";
import type { FlowContract } from "./flow.ts";
import type { ExecutionTrace, FlowOutcome } from "./types.ts";
import type { Clock } from "./clock.ts";
import { FakeClock } from "./clock.ts";
import { ReplayError } from "./errors.ts";

/** SPEC version this implementation conforms to. */
export const SPEC_VERSION = "0.1.0";

/** The four replay operations (SPEC 12.6). */
export const ReplayMode = {
  SIMULATION: "simulation",
  HISTORICAL: "historical",
  DECISION: "decision",
  EFFECTS: "effects",
} as const;
/** Union of ReplayMode values (SPEC 12.6). */
export type ReplayMode = (typeof ReplayMode)[keyof typeof ReplayMode];

/** A recorded decision tuple (SPEC 12.6, 12.10). */
export interface ReplayRecord {
  spec_version: string;
  contract_version: string;
  input: unknown;
  clock_wall: number;
  clock_monotonic: number;
  outcome: FlowOutcome;
  trace?: ExecutionTrace | null;
  effects: unknown[];
  integrity: string | null;
}

/** Result of a replay operation (SPEC 12.6). */
export interface ReplayResult {
  mode: ReplayMode;
  outcome: FlowOutcome | null;
  equivalent: boolean | null;
  effects_applied: number;
}

// FNV-1a 64-bit-ish hash → hex. Structural contract version, algorithm v1.
/** Compute the structural contract version (SPEC 12.9). */
export function contractVersionOf(contract: FlowContract): string {
  const summary = JSON.stringify({
    mode: (contract as unknown as { spec: { mode: string } }).spec.mode,
    rules: (contract as unknown as { spec: { rules: { id: string; kind: string; priority: number }[] } }).spec.rules
      .map((r) => [r.id, r.kind, r.priority]),
  });
  let h1 = 0x811c9dc5, h2 = 0x01000193;
  for (let i = 0; i < summary.length; i++) {
    const c = summary.charCodeAt(i);
    h1 = Math.imul(h1 ^ c, 0x01000193) >>> 0;
    h2 = Math.imul(h2 + c, 0x85ebca6b) >>> 0;
  }
  return `v1-${h1.toString(16).padStart(8, "0")}${h2.toString(16).padStart(8, "0")}`;
}

function canonicalPayload(rec: ReplayRecord): string {
  const o = rec.outcome;
  return JSON.stringify({
    spec_version: rec.spec_version,
    contract_version: rec.contract_version,
    input: rec.input,
    clock_wall: rec.clock_wall,
    clock_monotonic: rec.clock_monotonic,
    outcome: {
      execution_status: o.execution_status,
      decision_status: o.decision_status,
      value: o.value ?? null,
      has_recovery: o.recovery !== null,
      interruption_kind: o.interruption?.kind ?? null,
    },
    effects: rec.effects.map((e) => JSON.stringify(e)),
  });
}

/** Return a copy of the record with an HMAC-SHA256 integrity tag (SPEC 9.5). */
export function sign(rec: ReplayRecord, key: string | Buffer): ReplayRecord {
  const digest = createHmac("sha256", key).update(canonicalPayload(rec), "utf8").digest("hex");
  return { ...rec, integrity: digest };
}

/** Execute with tracing and capture a ReplayRecord (SPEC 12.6). */
export function record(contract: FlowContract, input: unknown, opts: { clock?: Clock } = {}): ReplayRecord {
  const clock = opts.clock ?? contract.clock;
  const outcome = contract.tryExecute(input, { clock, trace: true });
  return {
    spec_version: SPEC_VERSION,
    contract_version: contractVersionOf(contract),
    input,
    clock_wall: clock.wall(),
    clock_monotonic: clock.monotonic(),
    outcome,
    trace: outcome.trace ?? null,
    effects: outcome.effects.map((e) => ({ name: e.name, payload: e.payload ?? null })),
    integrity: null,
  };
}

function verifyIntegrity(rec: ReplayRecord, key: string | Buffer | null): void {
  if (rec.integrity === null) return;
  if (key === null) throw new ReplayError("record is integrity-tagged but no key supplied");
  const expected = createHmac("sha256", key).update(canonicalPayload(rec), "utf8").digest("hex");
  if (expected !== rec.integrity) throw new ReplayError("replay record integrity check failed");
}

function checkVersions(rec: ReplayRecord, contract: FlowContract): void {
  if (rec.spec_version !== SPEC_VERSION) {
    throw new ReplayError(`spec_version mismatch: record ${rec.spec_version}, current ${SPEC_VERSION}`);
  }
  const current = contractVersionOf(contract);
  if (rec.contract_version !== current) {
    throw new ReplayError(`contract_version mismatch: record ${rec.contract_version}, current ${current}`);
  }
}

function reconstructClock(rec: ReplayRecord): FakeClock {
  return new FakeClock(rec.clock_wall, rec.clock_monotonic);
}

function semanticallyEquivalent(a: FlowOutcome, b: FlowOutcome): boolean {
  return (
    a.execution_status === b.execution_status &&
    a.decision_status === b.decision_status &&
    JSON.stringify(a.value ?? null) === JSON.stringify(b.value ?? null) &&
    (a.recovery !== null) === (b.recovery !== null) &&
    (a.recovery === null || b.recovery === null ||
      a.recovery.handler_rule_id === b.recovery.handler_rule_id) &&
    (a.interruption?.kind ?? null) === (b.interruption?.kind ?? null)
  );
}

/** Replay a recorded decision (SPEC 12.6). Fails closed on version or
 *  integrity mismatch; EFFECTS mode requires explicit authorization. */
export function replay(
  rec: ReplayRecord,
  contract: FlowContract,
  opts: {
    mode?: ReplayMode;
    integrity_key?: string | Buffer | null;
    effect_executor?: (e: unknown) => void;
    authorize_effects?: boolean;
  } = {},
): ReplayResult {
  const mode = opts.mode ?? ReplayMode.SIMULATION;
  verifyIntegrity(rec, opts.integrity_key ?? null);
  checkVersions(rec, contract);

  if (mode === ReplayMode.HISTORICAL) {
    return { mode, outcome: rec.outcome, equivalent: null, effects_applied: 0 };
  }
  if (mode === ReplayMode.SIMULATION || mode === ReplayMode.DECISION) {
    const clock = reconstructClock(rec);
    const outcome = contract.simulate(rec.input, { clock });
    return { mode, outcome, equivalent: semanticallyEquivalent(outcome, rec.outcome), effects_applied: 0 };
  }
  if (mode === ReplayMode.EFFECTS) {
    if (!opts.authorize_effects) {
      throw new ReplayError("effect re-execution requires explicit authorization (authorize_effects=true)");
    }
    if (!opts.effect_executor) throw new ReplayError("EFFECTS mode requires an effect_executor");
    let applied = 0;
    for (const e of rec.effects) { opts.effect_executor(e); applied++; }
    return { mode, outcome: null, equivalent: null, effects_applied: applied };
  }
  throw new ReplayError(`unknown replay mode: ${mode}`);
}

// -- shadow (SPEC 12.7) ---------------------------------------------------------

/** One shadow-comparison entry (SPEC 12.7). */
export interface ShadowEntry {
  index: number;
  input: unknown;
  current: FlowOutcome;
  candidate: FlowOutcome;
  differs: boolean;
  differing_fields: string[];
  /** @deprecated use differs */
  equivalent: boolean;
}

/** Shadow comparison report (SPEC 12.7). */
export interface ShadowReport {
  total: number;
  differences: number;
  /** @deprecated use differences */
  divergent: number;
  entries: ShadowEntry[];
}

function diffFields(a: FlowOutcome, b: FlowOutcome): string[] {
  const fields: string[] = [];
  if (a.execution_status !== b.execution_status) fields.push("execution_status");
  if (a.decision_status !== b.decision_status) fields.push("decision_status");
  if (JSON.stringify(a.value ?? null) !== JSON.stringify(b.value ?? null)) fields.push("value");
  if ((a.recovery !== null) !== (b.recovery !== null)) fields.push("recovery");
  if ((a.interruption?.kind ?? null) !== (b.interruption?.kind ?? null)) fields.push("interruption");
  return fields;
}

/** Compare a candidate contract against the current one over inputs (SPEC 12.7). */
export function shadow(
  current: FlowContract,
  candidate: FlowContract,
  inputs: unknown[],
  opts: { clock?: Clock } = {},
): ShadowReport {
  const entries: ShadowEntry[] = [];
  inputs.forEach((input, index) => {
    const c = current.simulate(input, opts.clock !== undefined ? { clock: opts.clock } : {});
    const d = candidate.simulate(input, opts.clock !== undefined ? { clock: opts.clock } : {});
    const fields = diffFields(c, d);
    entries.push({
      index, input, current: c, candidate: d,
      differs: fields.length > 0, differing_fields: fields,
      equivalent: fields.length === 0,
    });
  });
  const differences = entries.filter((e) => e.differs).length;
  return { total: entries.length, differences, divergent: differences, entries };
}
