// TraceRecorder — SPEC.md 12.1-12.3.

import { ExecutionTrace, type EventType, type Reason, type TraceEvent } from "./types.ts";

const EVENT_TYPES = new Set<string>([
  "condition_evaluated", "condition_raised", "guard_evaluated",
  "action_executed", "action_raised", "catch_matched",
  "catch_predicate_evaluated", "catch_predicate_raised", "catch_handled",
  "catch_declined", "rethrow_reached", "hook_invoked", "hook_raised",
  "effect_proposed", "skipped_by_short_circuit", "skipped_by_mode",
  "finally_started", "finally_completed", "finally_raised",
  "cancelled_observed", "timed_out_observed", "rule_skipped",
]);

const REASONS = new Set<string>([
  "condition_false", "guard_blocked", "not_effective",
  "earlier_match", "mode_excluded",
]);

/** Diagnostic hook: receives each TraceEvent, may return extra fields (SPEC 12.2). */
export type DiagnosticHook = (event: TraceEvent) => Record<string, unknown> | null;

/** Trace recorder that validates event types/reasons and applies the
 *  diagnostic hook (SPEC 12.1-12.3). */
export class TraceRecorder {
  private events: TraceEvent[] = [];
  private readonly contractVersion: string;
  private readonly diagnosticHook: DiagnosticHook | null;

  /** Create a TraceRecorder stamped with the contract version. */
  constructor(contractVersion: string, diagnosticHook: DiagnosticHook | null = null) {
    this.contractVersion = contractVersion;
    this.diagnosticHook = diagnosticHook;
  }

  /** Emit a validated trace event, applying the diagnostic hook when present. */
  emit(type: EventType, ruleId: string | null, reason: Reason | null, timestamp: number): void {
    if (!EVENT_TYPES.has(type)) throw new Error(`unknown trace event: ${type}`);
    if (reason !== null && !REASONS.has(reason)) throw new Error(`unknown trace reason: ${reason}`);
    const event: TraceEvent = {
      type, rule_id: ruleId, reason, timestamp,
      contract_version: this.contractVersion, diagnostics: null,
    };
    if (this.diagnosticHook) {
      const diag = this.diagnosticHook(event);
      if (diag) event.diagnostics = diag;
    }
    this.events.push(event);
  }

  /** Return the collected events as an ExecutionTrace. */
  toTrace(): ExecutionTrace {
    const trace = new ExecutionTrace();
    trace.events.push(...this.events);
    return trace;
  }
}
