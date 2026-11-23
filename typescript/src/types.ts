// Core outcome model — SPEC.md sections 3.3-3.8, 7.
// Const-object enums (erasableSyntaxOnly: no TS enums).

/** Terminal execution status (SPEC 3.1). */
export const ExecutionStatus = {
  COMPLETED: "COMPLETED",
  FAILED: "FAILED",
  CANCELLED: "CANCELLED",
  TIMED_OUT: "TIMED_OUT",
} as const;
/** Union of ExecutionStatus values (SPEC 3.1). */
export type ExecutionStatus = (typeof ExecutionStatus)[keyof typeof ExecutionStatus];

/** Decision status (SPEC 3.2). */
export const DecisionStatus = {
  APPROVED: "APPROVED",
  REJECTED: "REJECTED",
  NO_MATCH: "NO_MATCH",
} as const;
/** Union of DecisionStatus values (SPEC 3.2). */
export type DecisionStatus = (typeof DecisionStatus)[keyof typeof DecisionStatus];

/** Rule evaluation mode (SPEC 10.6). */
export const EvaluationMode = {
  FIRST_MATCH: "FirstMatch",
  ALL_MATCH: "AllMatch",
  PRIORITY: "Priority",
} as const;
/** Union of EvaluationMode values (SPEC 10.6). */
export type EvaluationMode = (typeof EvaluationMode)[keyof typeof EvaluationMode];

/** Finalizer failure policy (SPEC 16.3). */
export const FinallyFailurePolicy = {
  PRESERVE_PRIMARY: "PreservePrimary",
  ATTACH: "Attach",
  REPLACE_PRIMARY: "ReplacePrimary",
} as const;
/** Union of FinallyFailurePolicy values (SPEC 16.3). */
export type FinallyFailurePolicy =
  (typeof FinallyFailurePolicy)[keyof typeof FinallyFailurePolicy];

/** Interruption kind (SPEC 3.3). */
export const InterruptionKind = {
  CANCELLED: "cancelled",
  TIMED_OUT: "timed_out",
} as const;
/** Union of InterruptionKind values (SPEC 3.3). */
export type InterruptionKind = (typeof InterruptionKind)[keyof typeof InterruptionKind];

/** Interruption metadata recorded on an outcome (SPEC 3.3). */
export interface InterruptionInfo {
  kind: InterruptionKind;
  source: "host" | "external";
  timestamp: number;
}

/** Recovery metadata recorded when a catch rule recovers (SPEC 3.4). */
export interface RecoveryInfo {
  original_exception: unknown;
  handler_rule_id: string | null;
  recovered_at: number;
}

/** Finalization metadata recorded on an outcome (SPEC 3.5, 16.4). */
export interface FinalizationInfo {
  is_clean: boolean;
  cleanup_exceptions: unknown[];
  cleanup_budget_exceeded?: boolean;
  cleanup_budget_used_ms?: number;
}

/** A proposed effect — data only, never applied by the library (SPEC 3.7, 5). */
export interface Effect {
  name: string;
  payload?: unknown;
}

/** The canonical outcome of a flow execution (SPEC 3.6, 7). */
export interface FlowOutcome {
  execution_status: ExecutionStatus;
  decision_status: DecisionStatus | null;
  value: unknown;
  primary_exception: unknown;
  recovery: RecoveryInfo | null;
  interruption: InterruptionInfo | null;
  finalization: FinalizationInfo | null;
  secondary_exceptions: unknown[];
  effects: Effect[];
  trace: ExecutionTrace | null;
}

// -- trace (SPEC 12.1) ---------------------------------------------------------

/** The 22-event trace vocabulary (SPEC 12.1). */
export const EVENT_TYPES = [
  "condition_evaluated", "condition_raised", "guard_evaluated",
  "action_executed", "action_raised", "catch_matched",
  "catch_predicate_evaluated", "catch_predicate_raised", "catch_handled",
  "catch_declined", "rethrow_reached", "hook_invoked", "hook_raised",
  "effect_proposed", "skipped_by_short_circuit", "skipped_by_mode",
  "finally_started", "finally_completed", "finally_raised",
  "cancelled_observed", "timed_out_observed", "rule_skipped",
] as const;
/** Union of the 22 trace event types (SPEC 12.1). */
export type EventType = (typeof EVENT_TYPES)[number];

/** Skip/failure reason vocabulary (SPEC 12.1). */
export const REASONS = [
  "condition_false", "guard_blocked", "not_effective",
  "earlier_match", "mode_excluded",
] as const;
/** Union of trace skip/failure reasons (SPEC 12.1). */
export type Reason = (typeof REASONS)[number];

/** A single trace event (SPEC 3.8, 12.1). Carries no input values. */
export interface TraceEvent {
  type: EventType;
  rule_id: string | null;
  reason: Reason | null;
  timestamp: number;
  contract_version: string | null;
  diagnostics: Record<string, unknown> | null;
}

/** Collected execution trace (SPEC 3.8, 12.1-12.3). */
export class ExecutionTrace {
  readonly events: TraceEvent[] = [];
  /** Emit a trace event. */
  emit(type: EventType, ruleId: string | null, reason: Reason | null, ts: number): void {
    this.events.push({ type, rule_id: ruleId, reason, timestamp: ts, contract_version: null, diagnostics: null });
  }
}

/** Isolated per-invocation execution context (SPEC 4.1.3, 6.2). */
export class FlowContext {
  readonly input: unknown;
  readonly clock: import("./clock.ts").Clock;
  readonly state: Record<string, unknown>;
  constructor(input: unknown, clock: import("./clock.ts").Clock, state: Record<string, unknown> = {}) {
    this.input = input;
    this.clock = clock;
    this.state = state;
  }
}
