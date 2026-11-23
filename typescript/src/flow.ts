// Flow builder + FlowContract — SPEC.md sections 7, 10, 11, 16.

import type { Clock } from "./clock.ts";
import { SystemClock } from "./clock.ts";
import {
  AsyncOnlyContractError,
  KindCancelled,
  KindTimeout,
  PortabilityError,
  StructureError,
} from "./errors.ts";
import { contractVersionOf } from "./trust.ts";
import { evalExpr, portableFlowFromDict, type PortableFlow } from "./portable.ts";
import {
  DecisionStatus,
  EvaluationMode,
  ExecutionStatus,
  FinallyFailurePolicy,
  InterruptionKind,
  type Effect,
  type ExecutionTrace,
  type FlowOutcome,
} from "./types.ts";
import { TraceRecorder, type DiagnosticHook } from "./trace.ts";

/** Condition callback: returns true when the rule holds (SPEC 10.2). */
export type ConditionFn = (input: unknown) => boolean;
/** Action callback: produces the rule's value (SPEC 10.2). */
export type ActionFn = (input: unknown, previous?: unknown) => unknown;
/** Guard callback: additional gate evaluated after the condition (SPEC 10.1). */
export type GuardFn = (input: unknown) => boolean;
/** Catch handler: receives (input, exception), returns recovery value (SPEC 11.1). */
export type ExceptionHandler = (input: unknown, exc: unknown) => unknown;
/** Catch predicate: decides whether a catch rule applies (SPEC 11.2). */
export type ExceptionPredicate = (input: unknown, exc: unknown) => boolean;
/** Match hook: invoked after each when/when_not action (SPEC 11.5). */
export type HookFn = (input: unknown, ruleId: string, value: unknown) => void | Promise<void>;
/** Finalizer cleanup: invoked for every outcome (SPEC 11.8, 16.1). */
export type CleanupFn = (ctx: FinallyContext) => unknown;

/** Context passed to a finalizer (SPEC 16.1). */
export interface FinallyContext {
  result: FlowOutcome;
  status: ExecutionStatus;
  value: unknown;
  exception: unknown;
  context: unknown;
  cancellation_token: { cancelled: boolean };
}

/** One rule in a flow (SPEC 10.2). */
export interface Rule {
  id: string;
  kind: "when" | "when_not" | "then";
  condition: ConditionFn | null;
  guard: GuardFn | null;
  action: ActionFn;
  priority: number;
  effects: Effect[];
  effective_from?: number | null;  // epoch ms, inclusive (SPEC 12.9)
  effective_until?: number | null; // epoch ms, exclusive
}

/** One exception handler in a flow (SPEC 11.1). */
export interface CatchRule {
  kind: "typed" | "when" | "any" | "rethrow";
  excType?: (new (...args: never[]) => Error) | undefined;
  predicate?: ExceptionPredicate | undefined;
  handler?: ExceptionHandler | undefined;
  id?: string | undefined;
}

/** The no-match fallback (SPEC 10.4). */
export interface Fallback {
  kind: "otherwise" | "default_if_no_match";
  action?: ActionFn;
  value?: unknown;
}

// -- builder -------------------------------------------------------------------

/** Flow builder (SPEC 7, 10, 11, 16). */
export class Flow {
  private rules: Rule[] = [];
  private catches: CatchRule[] = [];
  private hooks: HookFn[] = [];
  private finalizers: CleanupFn[] = [];
  private mode: EvaluationMode = EvaluationMode.FIRST_MATCH;
  private fallback: Fallback | null = null;
  private finallyPolicy: FinallyFailurePolicy = FinallyFailurePolicy.PRESERVE_PRIMARY;
  private finallyTimeoutMs: number | null = null;
  private traceEnabled = false;
  private portableRules: import("./portable.ts").PortableRule[] | null = null;
  private portableIr: PortableFlow | null = null;
  private cancelCheck: (() => boolean) | null = null;
  private flowId: string | null = null;
  private clock: Clock | null = null;
  private diagnosticHook: DiagnosticHook | null = null;

  /** Set the evaluation mode (SPEC 10.6). */
  withMode(mode: EvaluationMode): this { this.mode = mode; return this; }
  /** Set the flow identifier carried into Portable IR export (SPEC 14.2). */
  withFlowId(flowId: string): this { this.flowId = flowId; return this; }
  /** Inject a deterministic clock used for all timestamps (SPEC 6.2). */
  withClock(clock: Clock): this { this.clock = clock; return this; }

  /** Register a positive condition rule (SPEC 10.2). */
  when(cond: ConditionFn, action: ActionFn, opts: { id?: string; guard?: GuardFn; priority?: number; effects?: Effect[]; effectiveFrom?: number; effectiveUntil?: number } = {}): this {
    this.rules.push({ id: opts.id ?? `r${this.rules.length}`, kind: "when", condition: cond, guard: opts.guard ?? null, action, priority: opts.priority ?? 0, effects: opts.effects ?? [], effective_from: opts.effectiveFrom ?? null, effective_until: opts.effectiveUntil ?? null });
    return this;
  }
  /** Register a negated condition rule (SPEC 10.2). */
  whenNot(cond: ConditionFn, action: ActionFn, opts: { id?: string; guard?: GuardFn; priority?: number; effects?: Effect[]; effectiveFrom?: number; effectiveUntil?: number } = {}): this {
    this.rules.push({ id: opts.id ?? `r${this.rules.length}`, kind: "when_not", condition: cond, guard: opts.guard ?? null, action, priority: opts.priority ?? 0, effects: opts.effects ?? [], effective_from: opts.effectiveFrom ?? null, effective_until: opts.effectiveUntil ?? null });
    return this;
  }
  /** Register a sequential transformation stage (SPEC 10.5). */
  then(action: ActionFn, opts: { id?: string; effects?: Effect[] } = {}): this {
    this.rules.push({ id: opts.id ?? `t${this.rules.length}`, kind: "then", condition: null, guard: null, action, priority: 0, effects: opts.effects ?? [] });
    return this;
  }
  /** Register an otherwise fallback action (SPEC 10.4). */
  otherwise(action: ActionFn): this { this.fallback = { kind: "otherwise", action }; return this; }
  /** Convenience alias for defaultIfNoMatch (SPEC 10.4). */
  default(value: unknown): this { return this.defaultIfNoMatch(value); }
  /** Register a default_if_no_match fallback value (SPEC 10.4). */
  defaultIfNoMatch(value: unknown): this { this.fallback = { kind: "default_if_no_match", value }; return this; }

  /** Register a typed catch rule (SPEC 11.1). */
  catch(excType: new (...args: never[]) => Error, handler: ExceptionHandler, opts: { id?: string } = {}): this {
    this.catches.push({ kind: "typed", excType, handler, id: opts.id }); return this;
  }
  /** Register a catch rule with a predicate (SPEC 11.2). */
  catchWhen(excType: new (...args: never[]) => Error, predicate: ExceptionPredicate, handler: ExceptionHandler, opts: { id?: string } = {}): this {
    this.catches.push({ kind: "when", excType, predicate, handler, id: opts.id }); return this;
  }
  /** Register a catch-all rule; must follow typed catches (SPEC 11.3). */
  catchAny(handler: ExceptionHandler, opts: { id?: string } = {}): this {
    this.catches.push({ kind: "any", handler, id: opts.id }); return this;
  }
  /** Register a rethrow marker that stops catch routing (SPEC 11.4). */
  rethrow(): this { this.catches.push({ kind: "rethrow" }); return this; }
  /** Register a match hook invoked after each when/when_not action (SPEC 11.5). */
  onMatch(hook: HookFn): this { this.hooks.push(hook); return this; }
  /** Register a finalizer invoked for every outcome (SPEC 11.8, 16.1). */
  finally_(cleanup: CleanupFn): this { this.finalizers.push(cleanup); return this; }
  /** Register an async finalizer; the contract becomes async-only (SPEC 11.7, FR8). */
  finallyAsync(cleanup: (ctx: FinallyContext) => unknown | Promise<unknown>): this {
    this.finalizers.push(cleanup as CleanupFn); return this;
  }
  /** Set the finalizer failure policy (SPEC 16.3). */
  withFinallyPolicy(policy: FinallyFailurePolicy): this { this.finallyPolicy = policy; return this; }
  /** Set the finalizer cleanup budget in milliseconds (SPEC 16.7). */
  withFinallyTimeout(ms: number): this {
    if (ms < 1) throw new StructureError("finally timeout must be >= 1ms");
    this.finallyTimeoutMs = ms; return this;
  }
  /** Enable trace collection, optionally with a diagnostic hook (SPEC 12.2, 12.3). */
  withTrace(diagnosticHook?: DiagnosticHook): this {
    this.traceEnabled = true;
    this.diagnosticHook = diagnosticHook ?? null;
    return this;
  }
  /** Set a cooperative cancellation check polled during evaluation (SPEC 11.6). */
  withCancelCheck(check: () => boolean): this { this.cancelCheck = check; return this; }

  /** Splice another flow's rules, catches, hooks, and finalizers at the
   *  call site (SPEC 10.7). Modes must match; RuleIds must be unique;
   *  the outer (self) fallback wins when both flows define one. */
  merge(other: Flow | FlowContract): this {
    const spec = other instanceof FlowContract ? other.specSnapshot() : null;
    const mode = spec ? spec.mode : (other as Flow).mode;
    if (mode !== this.mode) {
      throw new StructureError(`cannot merge flows with different EvaluationMode: ${this.mode} vs ${mode} (SPEC 10.7)`);
    }
    const otherRules = spec ? spec.rules : (other as Flow).rules;
    const otherCatches = spec ? spec.catches : (other as Flow).catches;
    const otherHooks = spec ? spec.hooks : (other as Flow).hooks;
    const otherFinalizers = spec ? spec.finalizers : (other as Flow).finalizers;
    const otherFallback = spec ? spec.fallback : (other as Flow).fallback;
    const existing = new Set(this.rules.map((r) => r.id));
    for (const r of otherRules) {
      if (existing.has(r.id)) throw new StructureError(`merge would produce duplicate RuleId: ${r.id} (SPEC 10.7)`);
      existing.add(r.id);
    }
    this.rules.push(...otherRules);
    this.catches.push(...otherCatches);
    this.hooks.push(...otherHooks);
    this.finalizers.push(...otherFinalizers);
    if (this.fallback === null && otherFallback !== null) this.fallback = otherFallback;
    return this;
  }

  // -- portable IR (SPEC 14.2) -------------------------------------------------

  /** Register a portable when rule (SPEC 14.2). */
  whenExpr(cond: import("./portable.ts").PExpr, transform: import("./portable.ts").PExpr, opts: { id?: string; effects?: Effect[] } = {}): this {
    const id = opts.id ?? `p${this.portableRules?.length ?? 0}`;
    this.portableRules ??= [];
    this.portableRules.push({
      rule_id: id, kind: "when",
      condition: cond, transform,
      priority: 0, effects: (opts.effects ?? []).map((e) => ({ name: e.name, payload: e.payload })),
    });
    return this;
  }
  /** Register a portable when_not rule (SPEC 14.2). */
  whenNotExpr(cond: import("./portable.ts").PExpr, transform: import("./portable.ts").PExpr, opts: { id?: string; effects?: Effect[] } = {}): this {
    const id = opts.id ?? `p${this.portableRules?.length ?? 0}`;
    this.portableRules ??= [];
    this.portableRules.push({
      rule_id: id, kind: "when_not",
      condition: cond, transform,
      priority: 0, effects: (opts.effects ?? []).map((e) => ({ name: e.name, payload: e.payload })),
    });
    return this;
  }

  /** Build a Flow from a Portable IR document (SPEC 14.2). */
  static fromIr(ir: unknown): Flow {
    const pf = portableFlowFromDict(ir);
    const flow = new Flow().withMode(pf.mode as EvaluationMode);
    flow.portableIr = pf;
    for (const r of pf.rules) {
      const cond = r.condition!;
      const tr = r.transform!;
      const effects = r.effects.map((e) => ({ name: e.name, payload: e.payload }));
      if (r.kind === "when") {
        flow.whenExpr(cond, tr, { id: r.rule_id, effects });
      } else {
        flow.whenNotExpr(cond, tr, { id: r.rule_id, effects });
      }
    }
    if (pf.fallback?.kind === "default_if_no_match") {
      flow.defaultIfNoMatch(pf.fallback.value);
    }
    return flow;
  }

  /** Compile the builder into an immutable FlowContract (SPEC 4.3, 10.9). */
  compile(): FlowContract {
    // catch_any must be last (SPEC 11.3)
    const anyIdx = this.catches.findIndex((c) => c.kind === "any");
    if (anyIdx >= 0 && this.catches.slice(anyIdx + 1).some((c) => c.kind !== "rethrow")) {
      throw new StructureError("catch_any must be registered after typed catches (SPEC 11.3)");
    }
    let rules: Rule[];
    if (this.portableRules) {
      rules = this.portableRules.map((pr) => {
        const cond = pr.condition!;
        const tr = pr.transform!;
        const effFrom = pr.effective_from ? Date.parse(pr.effective_from) : null;
        const effUntil = pr.effective_until ? Date.parse(pr.effective_until) : null;
        return {
          id: pr.rule_id,
          kind: pr.kind,
          condition: (inp: unknown) => Boolean(evalExpr(cond, inp)),
          guard: pr.guard ? (inp: unknown) => Boolean(evalExpr(pr.guard!, inp)) : null,
          action: (_inp: unknown, prev?: unknown) => evalExpr(tr, prev !== undefined ? { input: _inp, prev } : _inp),
          priority: pr.priority,
          effects: pr.effects.map((e) => ({ name: e.name, payload: e.payload })),
          effective_from: effFrom,
          effective_until: effUntil,
        };
      });
    } else {
      rules = [...this.rules];
    }
    for (const r of rules) {
      if (r.effective_from != null && r.effective_until != null && r.effective_from >= r.effective_until) {
        throw new StructureError(`rule ${r.id}: effective_from must be before effective_until (SPEC 12.9)`);
      }
    }
    const seenIds = new Set<string>();
    for (const r of rules) {
      if (seenIds.has(r.id)) {
        throw new StructureError(`duplicate RuleId: ${r.id} (SPEC 4.3)`);
      }
      seenIds.add(r.id);
    }
    return new FlowContract({
      rules,
      mode: this.mode,
      fallback: this.fallback,
      catches: [...this.catches],
      hooks: [...this.hooks],
      finalizers: [...this.finalizers],
      finallyPolicy: this.finallyPolicy,
      finallyTimeoutMs: this.finallyTimeoutMs,
      traceEnabled: this.traceEnabled,
      clock: this.clock ?? new SystemClock(),
      cancelCheck: this.cancelCheck,
      diagnosticHook: this.diagnosticHook,
      portableRules: this.portableRules,
      portableIr: this.portableIr ?? (this.portableRules ? {
        spec_version: "0.1.0", flow_id: this.flowId ?? "flow", portability: "PORTABLE",
        mode: this.mode, rules: this.portableRules, fallback: null,
      } : null),
    });
  }
}

// -- contract ------------------------------------------------------------------

/** The compiled contract specification (internal shape, SPEC 4.1). */
export interface ContractSpec {
  rules: Rule[];
  mode: EvaluationMode;
  fallback: Fallback | null;
  catches: CatchRule[];
  hooks: HookFn[];
  finalizers: CleanupFn[];
  finallyPolicy: FinallyFailurePolicy;
  finallyTimeoutMs: number | null;
  traceEnabled: boolean;
  clock: Clock;
  portableIr: PortableFlow | null;
  cancelCheck?: (() => boolean) | null;
  diagnosticHook?: DiagnosticHook | null;
  portableRules?: import("./portable.ts").PortableRule[] | null;
}

function isThenable(value: unknown): value is Promise<unknown> {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as { then?: unknown }).then === "function"
  );
}

function emptyOutcome(status: ExecutionStatus): FlowOutcome {
  return {
    execution_status: status,
    decision_status: null,
    value: null,
    primary_exception: null,
    recovery: null,
    interruption: null,
    finalization: null,
    secondary_exceptions: [],
    effects: [],
    trace: null,
  };
}

/** A compiled, immutable flow contract (SPEC 4.1, 10.9). */
export class FlowContract {
  private spec: ContractSpec;
  constructor(spec: ContractSpec) { this.spec = spec; }

  /** The clock injected at build time. */
  get clock(): Clock { return this.spec.clock; }
  /** Whether trace collection is enabled by default. */
  get traceEnabled(): boolean { return this.spec.traceEnabled; }
  /** The structural contract version (SPEC 12.9). */
  get contractVersion(): string { return contractVersionOf(this); }
  /** Internal spec snapshot for Flow.merge(FlowContract) (SPEC 10.7). */
  specSnapshot(): ContractSpec { return this.spec; }

  /** Execute and propagate an unrecovered exception (SPEC 11.4, D13). */
  execute(input: unknown, opts: { clock?: Clock } = {}): FlowOutcome {
    if (this.specHasAsync()) {
      throw new AsyncOnlyContractError("contract is async-only; use executeAsync()");
    }
    const outcome = this.tryExecute(input, opts);
    if (outcome.execution_status === ExecutionStatus.FAILED && outcome.primary_exception !== null) {
      throw outcome.primary_exception;
    }
    return outcome;
  }

  /** Async execution variant; propagates unrecovered exceptions (SPEC 11.7). */
  async executeAsync(input: unknown, opts: { clock?: Clock } = {}): Promise<FlowOutcome> {
    const outcome = await this.tryExecuteAsync(input, opts);
    if (outcome.execution_status === ExecutionStatus.FAILED && outcome.primary_exception !== null) {
      throw outcome.primary_exception;
    }
    return outcome;
  }

  /** Execute and always return a FlowOutcome (SPEC 11.4). */
  tryExecute(input: unknown, opts: { clock?: Clock; trace?: boolean; diagnosticHook?: DiagnosticHook } = {}): FlowOutcome {
    if (this.specHasAsync()) {
      throw new AsyncOnlyContractError("contract is async-only; use tryExecuteAsync()");
    }
    const clock = opts.clock ?? this.spec.clock;
    const trace = opts.trace ?? this.spec.traceEnabled;
    const rec = trace ? new TraceRecorder(contractVersionOf(this), opts.diagnosticHook ?? this.spec.diagnosticHook ?? null) : null;
    const primary = this.primary(input, clock, rec);
    const outcome = this.finalize(input, clock, primary, rec);
    if (rec) outcome.trace = rec.toTrace();
    return outcome;
  }

  /** Async execution variant that always returns a FlowOutcome (SPEC 11.7). */
  async tryExecuteAsync(input: unknown, opts: { clock?: Clock; trace?: boolean; diagnosticHook?: DiagnosticHook } = {}): Promise<FlowOutcome> {
    const clock = opts.clock ?? this.spec.clock;
    const trace = opts.trace ?? this.spec.traceEnabled;
    const rec = trace ? new TraceRecorder(contractVersionOf(this), opts.diagnosticHook ?? this.spec.diagnosticHook ?? null) : null;
    let primary: FlowOutcome;
    try {
      primary = await this.primaryAsync(input, clock, rec);
    } catch (exc) {
      if (exc instanceof KindCancelled) {
        rec?.emit("cancelled_observed", null, null, clock.wall());
        primary = { ...emptyOutcome(ExecutionStatus.CANCELLED), interruption: { kind: InterruptionKind.CANCELLED, source: "host", timestamp: clock.wall() }, primary_exception: exc };
      } else if (exc instanceof KindTimeout) {
        rec?.emit("timed_out_observed", null, null, clock.wall());
        primary = { ...emptyOutcome(ExecutionStatus.TIMED_OUT), interruption: { kind: InterruptionKind.TIMED_OUT, source: "external", timestamp: clock.wall() }, primary_exception: exc };
      } else {
        primary = { ...emptyOutcome(ExecutionStatus.FAILED), primary_exception: exc };
      }
    }
    const outcome = await this.finalizeAsync(input, clock, primary, rec);
    if (rec) outcome.trace = rec.toTrace();
    return outcome;
  }

  private specHasAsync(): boolean {
    const isAsync = (fn: unknown): boolean =>
      typeof fn === "function" && fn.constructor.name === "AsyncFunction";
    for (const r of this.spec.rules) {
      if (isAsync(r.condition) || isAsync(r.guard) || isAsync(r.action)) return true;
    }
    for (const c of this.spec.catches) {
      if (isAsync(c.handler) || isAsync(c.predicate)) return true;
    }
    if (this.spec.hooks.some(isAsync)) return true;
    return this.spec.finalizers.some(isAsync);
  }

  // -- primary evaluation ------------------------------------------------------

  private primary(input: unknown, clock: Clock, rec: TraceRecorder | null): FlowOutcome {
    try {
      return this.evaluate(input, clock, rec, false);
    } catch (exc) {
      if (exc instanceof KindCancelled) {
        rec?.emit("cancelled_observed", null, null, clock.wall());
        return { ...emptyOutcome(ExecutionStatus.CANCELLED), interruption: { kind: InterruptionKind.CANCELLED, source: "host", timestamp: clock.wall() }, primary_exception: exc };
      }
      if (exc instanceof KindTimeout) {
        rec?.emit("timed_out_observed", null, null, clock.wall());
        return { ...emptyOutcome(ExecutionStatus.TIMED_OUT), interruption: { kind: InterruptionKind.TIMED_OUT, source: "external", timestamp: clock.wall() }, primary_exception: exc };
      }
      return this.handleException(input, clock, exc as Error, rec);
    }
  }

  private async primaryAsync(input: unknown, clock: Clock, rec: TraceRecorder | null): Promise<FlowOutcome> {
    try {
      return await this.evaluateAsync(input, clock, rec);
    } catch (exc) {
      if (exc instanceof KindCancelled) {
        rec?.emit("cancelled_observed", null, null, clock.wall());
        return { ...emptyOutcome(ExecutionStatus.CANCELLED), interruption: { kind: InterruptionKind.CANCELLED, source: "host", timestamp: clock.wall() }, primary_exception: exc };
      }
      if (exc instanceof KindTimeout) {
        rec?.emit("timed_out_observed", null, null, clock.wall());
        return { ...emptyOutcome(ExecutionStatus.TIMED_OUT), interruption: { kind: InterruptionKind.TIMED_OUT, source: "external", timestamp: clock.wall() }, primary_exception: exc };
      }
      return this.handleException(input, clock, exc as Error, rec);
    }
  }

  private orderedRules(): Rule[] {
    const rules = [...this.spec.rules];
    if (this.spec.mode === EvaluationMode.PRIORITY) {
      rules.sort((a, b) => b.priority - a.priority);
    }
    return rules;
  }

  private evaluate(input: unknown, clock: Clock, rec: TraceRecorder | null, _async: boolean): FlowOutcome {
    const rules = this.orderedRules();
    const secondary: unknown[] = [];
    const effects: Effect[] = [];
    let matched = false;
    let value: unknown = null;
    let activeThen: Rule[] = [];

    for (let i = 0; i < rules.length; i++) {
      const rule = rules[i]!;
      if (this.spec.cancelCheck?.()) throw new KindCancelled("cancelled");
      if (rule.kind === "then") {
        if (!matched) continue;
        try {
          value = rule.action(input, value);
          this.rejectAwaitable(value);
          rec?.emit("action_executed", rule.id, null, clock.wall());
        } catch (exc) {
          rec?.emit("action_raised", rule.id, null, clock.wall());
          throw exc;
        }
        for (const e of rule.effects) effects.push(e);
        rec?.emit("effect_proposed", rule.id, null, clock.wall());
        continue;
      }
      // when / when_not
      if (matched && this.spec.mode !== EvaluationMode.ALL_MATCH) {
        rec?.emit("skipped_by_short_circuit", rule.id, null, clock.wall());
        continue;
      }
      if ((rule.effective_from != null && clock.wall() < rule.effective_from) ||
          (rule.effective_until != null && clock.wall() >= rule.effective_until)) {
        rec?.emit("rule_skipped", rule.id, "not_effective" as never, clock.wall());
        continue;
      }
      let holds = false;
      let skipReason: string | null = null;
      try {
        const condResult = rule.condition!(input);
        rec?.emit("condition_evaluated", rule.id, null, clock.wall());
        holds = rule.kind === "when" ? Boolean(condResult) : !condResult;
        if (rule.guard) {
          const g = rule.guard(input);
          rec?.emit("guard_evaluated", rule.id, null, clock.wall());
          if (!g) { holds = false; skipReason = "guard_blocked"; }
        }
        if (!holds && skipReason === null) skipReason = "condition_false";
      } catch (exc) {
        rec?.emit("condition_raised", rule.id, null, clock.wall());
        throw exc;
      }
      if (!holds) {
        if (skipReason) rec?.emit("rule_skipped", rule.id, skipReason as never, clock.wall());
        continue;
      }
      matched = true;
      try {
        value = rule.action(input);
        this.rejectAwaitable(value);
        rec?.emit("action_executed", rule.id, null, clock.wall());
      } catch (exc) {
        rec?.emit("action_raised", rule.id, null, clock.wall());
        throw exc;
      }
      for (const e of rule.effects) effects.push(e);
      if (rule.effects.length) rec?.emit("effect_proposed", rule.id, null, clock.wall());
      for (const hook of this.spec.hooks) {
        try { hook(input, rule.id, value); rec?.emit("hook_invoked", rule.id, null, clock.wall()); }
        catch (exc) { secondary.push(exc); rec?.emit("hook_raised", rule.id, null, clock.wall()); }
      }
    }

    if (matched) {
      return {
        ...emptyOutcome(ExecutionStatus.COMPLETED),
        decision_status: DecisionStatus.APPROVED,
        value,
        secondary_exceptions: secondary,
        effects,
      };
    }
    // no match → fallback
    if (this.spec.fallback?.kind === "otherwise" && this.spec.fallback.action) {
      const fb = this.spec.fallback.action(input);
      this.rejectAwaitable(fb);
      return { ...emptyOutcome(ExecutionStatus.COMPLETED), decision_status: DecisionStatus.NO_MATCH, value: fb, secondary_exceptions: secondary, effects };
    }
    if (this.spec.fallback?.kind === "default_if_no_match") {
      return { ...emptyOutcome(ExecutionStatus.COMPLETED), decision_status: DecisionStatus.NO_MATCH, value: this.spec.fallback.value ?? null, secondary_exceptions: secondary, effects };
    }
    return { ...emptyOutcome(ExecutionStatus.COMPLETED), decision_status: DecisionStatus.NO_MATCH, value: null, secondary_exceptions: secondary, effects };
  }

  private async evaluateAsync(input: unknown, clock: Clock, rec: TraceRecorder | null): Promise<FlowOutcome> {
    // Async parity: same semantics; awaits awaitable results (SPEC 11.7).
    const rules = this.orderedRules();
    const secondary: unknown[] = [];
    const effects: Effect[] = [];
    let matched = false;
    let value: unknown = null;

    const resolve = async (v: unknown): Promise<unknown> =>
      isThenable(v) ? await v : v;

    for (const rule of rules) {
      if (this.spec.cancelCheck?.()) throw new KindCancelled("cancelled");
      if (rule.kind === "then") {
        if (!matched) continue;
        try {
          value = await resolve(rule.action(input, value));
          rec?.emit("action_executed", rule.id, null, clock.wall());
        } catch (exc) {
          rec?.emit("action_raised", rule.id, null, clock.wall());
          throw exc;
        }
        for (const e of rule.effects) effects.push(e);
        if (rule.effects.length) rec?.emit("effect_proposed", rule.id, null, clock.wall());
        continue;
      }
      if (matched && this.spec.mode !== EvaluationMode.ALL_MATCH) {
        rec?.emit("skipped_by_short_circuit", rule.id, null, clock.wall());
        continue;
      }
      if ((rule.effective_from != null && clock.wall() < rule.effective_from) ||
          (rule.effective_until != null && clock.wall() >= rule.effective_until)) {
        rec?.emit("rule_skipped", rule.id, "not_effective" as never, clock.wall());
        continue;
      }
      let holds = false;
      let skipReason: string | null = null;
      try {
        const condResult = await resolve(rule.condition!(input));
        rec?.emit("condition_evaluated", rule.id, null, clock.wall());
        holds = rule.kind === "when" ? Boolean(condResult) : !condResult;
        if (rule.guard) {
          const g = await resolve(rule.guard(input));
          rec?.emit("guard_evaluated", rule.id, null, clock.wall());
          if (!g) { holds = false; skipReason = "guard_blocked"; }
        }
        if (!holds && skipReason === null) skipReason = "condition_false";
      } catch (exc) {
        rec?.emit("condition_raised", rule.id, null, clock.wall());
        throw exc;
      }
      if (!holds) {
        if (skipReason) rec?.emit("rule_skipped", rule.id, skipReason as never, clock.wall());
        continue;
      }
      matched = true;
      try {
        value = await resolve(rule.action(input));
        rec?.emit("action_executed", rule.id, null, clock.wall());
      } catch (exc) {
        rec?.emit("action_raised", rule.id, null, clock.wall());
        throw exc;
      }
      for (const e of rule.effects) effects.push(e);
      if (rule.effects.length) rec?.emit("effect_proposed", rule.id, null, clock.wall());
      for (const hook of this.spec.hooks) {
        try {
          const r = hook(input, rule.id, value);
          if (isThenable(r)) await r;
          rec?.emit("hook_invoked", rule.id, null, clock.wall());
        } catch (exc) { secondary.push(exc); rec?.emit("hook_raised", rule.id, null, clock.wall()); }
      }
    }

    if (matched) {
      return { ...emptyOutcome(ExecutionStatus.COMPLETED), decision_status: DecisionStatus.APPROVED, value, secondary_exceptions: secondary, effects };
    }
    if (this.spec.fallback?.kind === "otherwise" && this.spec.fallback.action) {
      const fb = await resolve(this.spec.fallback.action(input));
      return { ...emptyOutcome(ExecutionStatus.COMPLETED), decision_status: DecisionStatus.NO_MATCH, value: fb, secondary_exceptions: secondary, effects };
    }
    if (this.spec.fallback?.kind === "default_if_no_match") {
      return { ...emptyOutcome(ExecutionStatus.COMPLETED), decision_status: DecisionStatus.NO_MATCH, value: this.spec.fallback.value ?? null, secondary_exceptions: secondary, effects };
    }
    return { ...emptyOutcome(ExecutionStatus.COMPLETED), decision_status: DecisionStatus.NO_MATCH, value: null, secondary_exceptions: secondary, effects };
  }

  private rejectAwaitable(value: unknown): void {
    if (isThenable(value)) {
      throw new StructureError("sync execution cannot return awaitables (SPEC 11.7)");
    }
  }

  // -- exception routing (SPEC 11.1-11.4) ---------------------------------------

  private handleException(input: unknown, clock: Clock, exc: Error, rec: TraceRecorder | null): FlowOutcome {
    let current: unknown = exc;
    for (const c of this.spec.catches) {
      if (c.kind === "rethrow") {
        rec?.emit("rethrow_reached", null, null, clock.wall());
        break;
      }
      if (c.kind === "any") {
        rec?.emit("catch_matched", c.id ?? null, null, clock.wall());
        try {
          const v = c.handler!(input, current);
          this.rejectAwaitable(v);
          rec?.emit("catch_handled", c.id ?? null, null, clock.wall());
          return {
            ...emptyOutcome(ExecutionStatus.COMPLETED),
            value: v,
            recovery: { original_exception: current, handler_rule_id: c.id ?? null, recovered_at: clock.wall() },
          };
        } catch (newExc) {
          current = newExc;
          continue; // handler failure propagates the NEW exception
        }
      }
      // typed / when
      const isInstance = c.excType ? current instanceof c.excType : false;
      if (!isInstance) { rec?.emit("catch_declined", c.id ?? null, null, clock.wall()); continue; }
      if (c.kind === "when" && c.predicate) {
        rec?.emit("catch_predicate_evaluated", c.id ?? null, null, clock.wall());
        let pred = false;
        try { pred = c.predicate(input, current); }
        catch (pe) { rec?.emit("catch_predicate_raised", c.id ?? null, null, clock.wall()); current = pe; continue; }
        if (!pred) { rec?.emit("catch_declined", c.id ?? null, null, clock.wall()); continue; }
      }
      rec?.emit("catch_matched", c.id ?? null, null, clock.wall());
      try {
        const v = c.handler!(input, current);
        this.rejectAwaitable(v);
        rec?.emit("catch_handled", c.id ?? null, null, clock.wall());
        return {
          ...emptyOutcome(ExecutionStatus.COMPLETED),
          value: v,
          recovery: { original_exception: current, handler_rule_id: c.id ?? null, recovered_at: clock.wall() },
        };
      } catch (newExc) {
        current = newExc;
        continue;
      }
    }
    return { ...emptyOutcome(ExecutionStatus.FAILED), primary_exception: current };
  }

  // -- finalization (SPEC 11.8, 16) ---------------------------------------------

  private finalize(input: unknown, clock: Clock, outcome: FlowOutcome, rec: TraceRecorder | null): FlowOutcome {
    if (!this.spec.finalizers.length) return outcome;
    const cleanupExcs: unknown[] = [];
    let isClean = true;
    let budgetUsedMs = 0;
    let budgetExceeded = false;
    const timeout = this.spec.finallyTimeoutMs;
    for (let i = this.spec.finalizers.length - 1; i >= 0; i--) {
      const fn = this.spec.finalizers[i]!;
      const fctx: FinallyContext = {
        result: outcome, status: outcome.execution_status, value: outcome.value,
        exception: outcome.primary_exception, context: input,
        cancellation_token: { cancelled: false },
      };
      rec?.emit("finally_started", null, null, clock.wall());
      const start = clock.monotonic();
      try { fn(fctx); rec?.emit("finally_completed", null, null, clock.wall()); }
      catch (exc) { isClean = false; cleanupExcs.push(exc); rec?.emit("finally_raised", null, null, clock.wall()); }
      if (timeout != null && timeout > 0) {
        const elapsed = clock.monotonic() - start;
        budgetUsedMs += elapsed;
        if (elapsed > timeout) budgetExceeded = true;
      }
    }
    return this.mergeFinalization(outcome, cleanupExcs, isClean, budgetExceeded, budgetUsedMs);
  }

  private async finalizeAsync(input: unknown, clock: Clock, outcome: FlowOutcome, rec: TraceRecorder | null): Promise<FlowOutcome> {
    if (!this.spec.finalizers.length) return outcome;
    const cleanupExcs: unknown[] = [];
    let isClean = true;
    let budgetUsedMs = 0;
    let budgetExceeded = false;
    const timeout = this.spec.finallyTimeoutMs;
    for (let i = this.spec.finalizers.length - 1; i >= 0; i--) {
      const fn = this.spec.finalizers[i]!;
      const fctx: FinallyContext = {
        result: outcome, status: outcome.execution_status, value: outcome.value,
        exception: outcome.primary_exception, context: input,
        cancellation_token: { cancelled: false },
      };
      rec?.emit("finally_started", null, null, clock.wall());
      const start = clock.monotonic();
      try {
        const r = fn(fctx);
        if (isThenable(r)) await r;
        rec?.emit("finally_completed", null, null, clock.wall());
      } catch (exc) { isClean = false; cleanupExcs.push(exc); rec?.emit("finally_raised", null, null, clock.wall()); }
      if (timeout != null && timeout > 0) {
        const elapsed = clock.monotonic() - start;
        budgetUsedMs += elapsed;
        if (elapsed > timeout) budgetExceeded = true;
      }
    }
    return this.mergeFinalization(outcome, cleanupExcs, isClean, budgetExceeded, budgetUsedMs);
  }

  private mergeFinalization(outcome: FlowOutcome, cleanupExcs: unknown[], isClean: boolean, budgetExceeded = false, budgetUsedMs = 0): FlowOutcome {
    const secondary = [...outcome.secondary_exceptions, ...cleanupExcs];
    let primaryExc = outcome.primary_exception;
    let status = outcome.execution_status;
    if (
      this.spec.finallyPolicy === FinallyFailurePolicy.REPLACE_PRIMARY &&
      outcome.execution_status === ExecutionStatus.FAILED &&
      outcome.primary_exception != null &&
      cleanupExcs.length > 0
    ) {
      secondary.push(outcome.primary_exception);
      primaryExc = cleanupExcs[cleanupExcs.length - 1];
    }
    return {
      ...outcome,
      primary_exception: primaryExc,
      execution_status: status,
      secondary_exceptions: secondary,
      finalization: {
        is_clean: isClean,
        cleanup_exceptions: cleanupExcs,
        cleanup_budget_exceeded: budgetExceeded,
        cleanup_budget_used_ms: budgetUsedMs,
      },
    };
  }

  // -- trust layer ---------------------------------------------------------------

  /** Simulate decision semantics without hooks or finalizers (SPEC 12.5). */
  simulate(input: unknown, opts: { clock?: Clock } = {}): FlowOutcome {
    // SPEC 12.5: decision semantics without hooks/finalizers/effects.
    const simSpec: ContractSpec = { ...this.spec, hooks: [], finalizers: [], catches: [] };
    const sim = new FlowContract(simSpec);
    return sim.tryExecute(input, opts.clock !== undefined ? { clock: opts.clock } : {});
  }

  /** Render an execution trace as human-readable lines (SPEC 12.4). */
  explain(trace: ExecutionTrace): string {
    return trace.events.map((e) => `${e.type}${e.rule_id ? ` ${e.rule_id}` : ""}${e.reason ? ` (${e.reason})` : ""}`).join("\n");
  }

  // -- portable IR export (SPEC 14.2) -------------------------------------------

  /** Export a PORTABLE contract as a PortableFlow IR document (SPEC 14.2). */
  toIR(): PortableFlow {
    if (!this.spec.portableIr) {
      throw new PortabilityError("contract is NATIVE; only PORTABLE contracts can be exported to the Portable IR (SPEC 14.2)");
    }
    return { ...this.spec.portableIr, contract_version: contractVersionOf(this) } as PortableFlow & { contract_version: string };
  }

  /** Export a PORTABLE contract as canonical Portable IR JSON (SPEC 14.2). */
  toIRJSON(): string {
    return JSON.stringify(this.toIR());
  }

  /** Perform static analysis on the contract without executing it (SPEC 12.8). */
  validate(): { severity: string; code: string; message: string; rule_id?: string }[] {
    const issues: { severity: string; code: string; message: string; rule_id?: string }[] = [];
    if (this.spec.rules.length === 0 && this.spec.fallback === null) {
      issues.push({ severity: "error", code: "empty_flow", message: "flow has neither rules nor a fallback" });
    }
    const ids = new Set<string>();
    for (const r of this.spec.rules) {
      if (ids.has(r.id)) issues.push({ severity: "error", code: "duplicate_rule_id", message: `duplicate RuleId: ${r.id}`, rule_id: r.id });
      ids.add(r.id);
    }
    let seenAny = false;
    for (const c of this.spec.catches) {
      if (c.kind === "any") seenAny = true;
      else if (seenAny && (c.kind === "typed" || c.kind === "when")) {
        issues.push({ severity: "error", code: "catch_any_ordering", message: "typed catch registered after catch_any" });
      }
    }
    for (const r of this.spec.rules) {
      if (r.effective_from != null && r.effective_until != null && r.effective_from >= r.effective_until) {
        issues.push({ severity: "error", code: "invalid_effective_window", message: "effective_from must be before effective_until", rule_id: r.id });
      }
    }
    // unreachable: provable only for portable const-true (SPEC 12.8)
    if (this.spec.mode !== EvaluationMode.ALL_MATCH && this.spec.portableRules) {
      let unconditional = false;
      for (let i = 0; i < this.spec.rules.length; i++) {
        const r = this.spec.rules[i]!;
        if (r.kind === "then") continue;
        if (unconditional) {
          issues.push({ severity: "warning", code: "unreachable_rule", message: "rule cannot match: an earlier unconditional rule always matches first", rule_id: r.id });
          continue;
        }
        const pc = this.spec.portableRules[i]?.condition;
        if (pc && pc.op === "const" && pc.value === true) unconditional = true;
      }
    }
    // overlap: identical portable conditions
    if (this.spec.portableRules) {
      const prs = this.spec.portableRules;
      for (let i = 0; i < prs.length; i++) {
        for (let j = i + 1; j < prs.length; j++) {
          if (prs[i]!.kind === prs[j]!.kind && exprEqual(prs[i]!.condition, prs[j]!.condition)) {
            issues.push({ severity: "warning", code: "overlapping_rules", message: "rules have structurally identical conditions", rule_id: prs[j]!.rule_id });
          }
        }
      }
    }
    if (this.spec.fallback === null && this.spec.rules.length > 0) {
      issues.push({ severity: "warning", code: "possible_gap", message: "no fallback configured; some inputs may produce NO_MATCH" });
    }
    return issues;
  }

  /** Batch simulation with firing distribution (SPEC 12.5). */
  simulateBatch(inputs: unknown[]): {
    total: number;
    by_status: Record<string, number>;
    by_decision: Record<string, number>;
    by_value: Record<string, number>;
    outcomes: FlowOutcome[];
  } {
    const byStatus: Record<string, number> = {};
    const byDecision: Record<string, number> = {};
    const byValue: Record<string, number> = {};
    const outcomes: FlowOutcome[] = [];
    for (const input of inputs) {
      const o = this.simulate(input);
      outcomes.push(o);
      byStatus[o.execution_status] = (byStatus[o.execution_status] ?? 0) + 1;
      const d = o.decision_status ?? "null";
      byDecision[d] = (byDecision[d] ?? 0) + 1;
      const v = JSON.stringify(o.value ?? null);
      byValue[v] = (byValue[v] ?? 0) + 1;
    }
    return { total: inputs.length, by_status: byStatus, by_decision: byDecision, by_value: byValue, outcomes };
  }

  /** Portability classification + offending components (SPEC 4.4). */
  portability(): { classification: "PORTABLE" | "NATIVE"; offenders: string[] } {
    if (!this.spec.portableIr && !this.spec.portableRules) {
      return { classification: "NATIVE", offenders: ["native rules"] };
    }
    const offenders: string[] = [];
    if (this.spec.catches.length) offenders.push("catches");
    if (this.spec.finalizers.length) offenders.push("finalizers");
    if (this.spec.hooks.length) offenders.push("hooks");
    return offenders.length === 0
      ? { classification: "PORTABLE", offenders: [] }
      : { classification: "NATIVE", offenders };
  }
}

function exprEqual(a: import("./portable.ts").PExpr | undefined, b: import("./portable.ts").PExpr | undefined): boolean {
  if (a === b) return true;
  if (!a || !b) return false;
  if (a.op !== b.op) return false;
  if (JSON.stringify(a.value ?? null) !== JSON.stringify(b.value ?? null)) return false;
  if ((a.args?.length ?? 0) !== (b.args?.length ?? 0)) return false;
  for (let i = 0; i < (a.args?.length ?? 0); i++) {
    if (!exprEqual(a.args![i], b.args![i])) return false;
  }
  return true;
}
