package flowsemantics;

import java.util.*;
import java.util.function.*;

/** Flow builder + FlowContract — SPEC 7, 10, 11, 16. */
public final class Flow {
    /** Condition callback: returns true when the rule holds (SPEC 10.2). */
    public interface ConditionFn { boolean test(Object input) throws Exception; }
    /** Action callback: produces the rule's value (SPEC 10.2). */
    public interface ActionFn { Object apply(Object input, Object previous) throws Exception; }
    /** Guard callback: additional gate evaluated after the condition (SPEC 10.1). */
    public interface GuardFn { boolean test(Object input) throws Exception; }
    /** Catch handler: receives (input, exception), returns recovery value (SPEC 11.1). */
    public interface ExceptionHandler { Object handle(Object input, Object exc) throws Exception; }
    /** Catch predicate: decides whether a catch rule applies (SPEC 11.2). */
    public interface ExceptionPredicate { boolean test(Object input, Object exc) throws Exception; }
    /** Match hook: invoked after each when/when_not action (SPEC 11.5). */
    public interface HookFn { void accept(Object input, String ruleId, Object value); }
    /** Finalizer cleanup: invoked for every outcome (SPEC 11.8, 16.1). */
    public interface CleanupFn { void accept(FinallyContext ctx) throws Exception; }

    /** Context passed to a finalizer (SPEC 16.1). */
    public static final class FinallyContext {
        /** The outcome being finalized. */
        public final Outcome.FlowOutcome result;
        /** Execution status of the outcome. */
        public final Outcome.ExecutionStatus status;
        /** Produced value, if any. */
        public final Object value;
        /** Unrecovered primary exception, if any. */
        public final Object exception;
        /** The original input. */
        public final Object context;
        /** Cooperative cancellation token (single-element boolean array). */
        public final boolean[] cancellationToken = {false};
        FinallyContext(Outcome.FlowOutcome r, Object v, Object e, Object c) {
            result = r; status = r.executionStatus; value = v; exception = e; context = c;
        }
    }

    static final class Rule {
        String id; String kind; // when | when_not | then
        ConditionFn condition; GuardFn guard; ActionFn action;
        int priority; List<Outcome.Effect> effects = new ArrayList<>();
        Long effectiveFrom; Long effectiveUntil; // epoch ms (SPEC 12.9)
    }

    static final class CatchRule {
        String kind; // typed | when | any | rethrow
        String excKind; ExceptionPredicate predicate; ExceptionHandler handler; String id;
    }

    static final class Fallback {
        String kind; ActionFn action; Object value;
    }

    final List<Rule> rules = new ArrayList<>();
    final List<CatchRule> catches = new ArrayList<>();
    final List<HookFn> hooks = new ArrayList<>();
    final List<CleanupFn> finalizers = new ArrayList<>();
    Outcome.EvaluationMode mode = Outcome.EvaluationMode.FirstMatch;
    Fallback fallback;
    private Outcome.FinallyFailurePolicy finallyPolicy = Outcome.FinallyFailurePolicy.PreservePrimary;
    private boolean traceEnabled;
    private final List<Portable.PortableRule> portableRules = new ArrayList<>();
    private boolean hasPortable;
    private java.util.function.BooleanSupplier cancelCheck;
    private long finallyTimeoutMs;
    private String flowId;
    private Clock clock;
    private Outcome.DiagnosticHook diagnosticHook;

    /** Create a new empty flow builder (FirstMatch mode). */
    public static Flow create() { return new Flow(); }

    /** Set the evaluation mode (SPEC 10.6). */
    public Flow withMode(Outcome.EvaluationMode m) { mode = m; return this; }
    /** Set the flow identifier carried into Portable IR export (SPEC 14.2). */
    public Flow withFlowId(String id) { flowId = id; return this; }
    /** Inject a deterministic clock used for all timestamps (SPEC 6.2). */
    public Flow withClock(Clock c) { clock = c; return this; }

    /** Register a positive condition rule (SPEC 10.2). */
    public Flow when(ConditionFn cond, ActionFn action, String id) { return when(cond, action, id, null, 0, null); }
    /** Register a positive condition rule with guard, priority, and effects (SPEC 10.2). */
    public Flow when(ConditionFn cond, ActionFn action, String id, GuardFn guard, int priority, List<Outcome.Effect> effects) {
        return when(cond, action, id, guard, priority, effects, null, null);
    }
    /** Register a positive condition rule with all options (SPEC 10.2, 12.9). */
    public Flow when(ConditionFn cond, ActionFn action, String id, GuardFn guard, int priority, List<Outcome.Effect> effects, Long effFrom, Long effUntil) {
        Rule r = new Rule(); r.id = id; r.kind = "when"; r.condition = cond; r.action = action;
        r.guard = guard; r.priority = priority; if (effects != null) r.effects = effects;
        r.effectiveFrom = effFrom; r.effectiveUntil = effUntil;
        rules.add(r); return this;
    }
    /** Register a negated condition rule (SPEC 10.2). */
    public Flow whenNot(ConditionFn cond, ActionFn action, String id) { return whenNot(cond, action, id, null, null); }
    /** Register a negated condition rule with effective dates (SPEC 10.2, 12.9). */
    public Flow whenNot(ConditionFn cond, ActionFn action, String id, Long effFrom, Long effUntil) {
        Rule r = new Rule(); r.id = id; r.kind = "when_not"; r.condition = cond; r.action = action;
        r.effectiveFrom = effFrom; r.effectiveUntil = effUntil;
        rules.add(r); return this;
    }
    /** Register a sequential transformation stage (SPEC 10.5). */
    public Flow then(ActionFn action, String id) {
        Rule r = new Rule(); r.id = id; r.kind = "then"; r.action = action;
        rules.add(r); return this;
    }
    /** Register an otherwise fallback action (SPEC 10.4). */
    public Flow otherwise(ActionFn action) { fallback = new Fallback(); fallback.kind = "otherwise"; fallback.action = action; return this; }
    /** Register a default_if_no_match fallback value (SPEC 10.4). */
    public Flow defaultIfNoMatch(Object value) { fallback = new Fallback(); fallback.kind = "default_if_no_match"; fallback.value = value; return this; }

    /** Register a typed catch rule (SPEC 11.1). */
    public Flow catchTyped(String excKind, ExceptionHandler handler, String id) {
        CatchRule c = new CatchRule(); c.kind = "typed"; c.excKind = excKind; c.handler = handler; c.id = id;
        catches.add(c); return this;
    }
    /** Register a catch rule with a predicate (SPEC 11.2). */
    public Flow catchWhen(String excKind, ExceptionPredicate pred, ExceptionHandler handler, String id) {
        CatchRule c = new CatchRule(); c.kind = "when"; c.excKind = excKind; c.predicate = pred; c.handler = handler; c.id = id;
        catches.add(c); return this;
    }
    /** Register a catch-all rule; must follow typed catches (SPEC 11.3). */
    public Flow catchAny(ExceptionHandler handler, String id) {
        CatchRule c = new CatchRule(); c.kind = "any"; c.handler = handler; c.id = id;
        catches.add(c); return this;
    }
    /** Register a rethrow marker that stops catch routing (SPEC 11.4). */
    public Flow rethrow() { CatchRule c = new CatchRule(); c.kind = "rethrow"; catches.add(c); return this; }
    /** Register a match hook invoked after each when/when_not action (SPEC 11.5). */
    public Flow onMatch(HookFn hook) { hooks.add(hook); return this; }
    /** Register a finalizer invoked for every outcome (SPEC 11.8, 16.1). */
    public Flow finally_(CleanupFn cleanup) { finalizers.add(cleanup); return this; }
    /** Set the finalizer failure policy (SPEC 16.3). */
    public Flow withFinallyPolicy(Outcome.FinallyFailurePolicy p) { finallyPolicy = p; return this; }
    /** Set the finalizer cleanup budget in milliseconds (SPEC 16.7). */
    public Flow withFinallyTimeout(long ms) { finallyTimeoutMs = ms; return this; }
    /** Set a cooperative cancellation check polled during evaluation (SPEC 11.6). */
    public Flow withCancelCheck(java.util.function.BooleanSupplier check) { cancelCheck = check; return this; }
    /** Enable trace collection for executions of this flow (SPEC 12.3). */
    public Flow withTrace() { traceEnabled = true; return this; }
    /** Enable trace collection with a diagnostic hook (SPEC 12.2, 12.3). */
    public Flow withTrace(Outcome.DiagnosticHook hook) { traceEnabled = true; diagnosticHook = hook; return this; }
    /** Convenience alias for defaultIfNoMatch (SPEC 10.4). */
    public Flow defaultValue(Object value) { return defaultIfNoMatch(value); }

    /** Register a portable when rule (SPEC 14.2). */
    public Flow whenExpr(Portable.PExpr cond, Portable.PExpr transform, String id, List<Outcome.Effect> effects) {
        hasPortable = true;
        Portable.PortableRule pr = new Portable.PortableRule();
        pr.ruleId = id; pr.kind = "when"; pr.condition = cond; pr.transform = transform;
        if (effects != null) pr.effects = effects;
        portableRules.add(pr); return this;
    }
    /** Register a portable when_not rule (SPEC 14.2). */
    public Flow whenNotExpr(Portable.PExpr cond, Portable.PExpr transform, String id, List<Outcome.Effect> effects) {
        hasPortable = true;
        Portable.PortableRule pr = new Portable.PortableRule();
        pr.ruleId = id; pr.kind = "when_not"; pr.condition = cond; pr.transform = transform;
        if (effects != null) pr.effects = effects;
        portableRules.add(pr); return this;
    }

    /** Build a Flow from a Portable IR document (SPEC 14.2). */
    public static Flow fromIr(Object ir) {
        Portable.PortableFlow pf = Portable.portableFlowFromDict(ir);
        Flow f = create().withMode(pf.mode);
        f.hasPortable = true;
        for (Portable.PortableRule pr : pf.rules) {
            if ("when".equals(pr.kind)) f.whenExpr(pr.condition, pr.transform, pr.ruleId, pr.effects);
            else f.whenNotExpr(pr.condition, pr.transform, pr.ruleId, pr.effects);
        }
        if (pf.fallback != null && "default_if_no_match".equals(pf.fallback.get("kind"))) {
            f.defaultIfNoMatch(pf.fallback.get("value"));
        }
        return f;
    }

    /** Compile the builder into an immutable FlowContract (SPEC 4.3, 10.9). */
    public FlowContract compile() {
        for (int i = 0; i < catches.size(); i++) {
            if ("any".equals(catches.get(i).kind)) {
                for (int j = i + 1; j < catches.size(); j++) {
                    if (!"rethrow".equals(catches.get(j).kind)) {
                        throw new FlowErrors.StructureError("catch_any must be registered after typed catches");
                    }
                }
            }
        }
        List<Rule> compiled = new ArrayList<>();
        if (hasPortable) {
            for (Portable.PortableRule pr : portableRules) {
                Rule r = new Rule();
                r.id = pr.ruleId; r.kind = pr.kind; r.priority = pr.priority; r.effects = pr.effects;
                r.effectiveFrom = Advanced.parseEffective(pr.effectiveFrom);
                r.effectiveUntil = Advanced.parseEffective(pr.effectiveUntil);
                Portable.PExpr cond = pr.condition, tr = pr.transform;
                r.condition = input -> truthy(Portable.evalExpr(cond, input));
                r.action = (input, prev) -> Portable.evalExpr(tr, input);
                compiled.add(r);
            }
        } else {
            compiled.addAll(rules);
        }
        FlowContract c = new FlowContract();
        c.rules = compiled; c.mode = mode; c.fallback = fallback;
        c.catches = new ArrayList<>(catches); c.hooks = new ArrayList<>(hooks);
        c.finalizers = new ArrayList<>(finalizers); c.finallyPolicy = finallyPolicy;
        c.traceEnabled = traceEnabled;
        c.clock = clock != null ? clock : new SystemClock();
        c.cancelCheck = cancelCheck; c.finallyTimeoutMs = finallyTimeoutMs;
        c.flowId = flowId; c.diagnosticHook = diagnosticHook;
        // effective date validation (SPEC 12.9)
        for (Rule r : compiled) {
            if (r.effectiveFrom != null && r.effectiveUntil != null && r.effectiveFrom >= r.effectiveUntil) {
                throw new FlowErrors.StructureError("rule " + r.id + ": effective_from must be before effective_until (SPEC 12.9)");
            }
        }
        c.contractVersion = Trust.contractVersion(compiled, fallback, mode,
            new ArrayList<>(catches), finalizers.size(), finallyPolicy, finallyTimeoutMs, traceEnabled);
        // duplicate RuleId validation (SPEC 4.3)
        java.util.Set<String> seenIds = new java.util.HashSet<>();
        for (Rule r : compiled) {
            if (!seenIds.add(r.id)) {
                throw new FlowErrors.StructureError("duplicate RuleId: " + r.id + " (SPEC 4.3)");
            }
        }
        c.hasPortable = hasPortable;
        c.portableRules = new ArrayList<>(portableRules);
        return c;
    }

    private static boolean truthy(Object v) { return Boolean.TRUE.equals(v); }

    /** A compiled, immutable flow contract (SPEC 4.1, 10.9). */
    public static final class FlowContract {
        List<Rule> rules; Outcome.EvaluationMode mode; Fallback fallback;
        List<CatchRule> catches; List<HookFn> hooks; List<CleanupFn> finalizers;
        Outcome.FinallyFailurePolicy finallyPolicy; boolean traceEnabled; Clock clock;
        java.util.function.BooleanSupplier cancelCheck; long finallyTimeoutMs;
        String contractVersion = "1";
        boolean hasPortable;
        List<Portable.PortableRule> portableRules = new ArrayList<>();
        String flowId;
        Outcome.DiagnosticHook diagnosticHook;

        /** The clock injected at build time. */
        public Clock clock() { return clock; }

        /** Execute and always return a FlowOutcome (SPEC 11.4). */
        public Outcome.FlowOutcome tryExecute(Object input) { return tryExecute(input, clock, traceEnabled); }
        /** Execute with an explicit clock and trace flag (SPEC 11.4, 12.3). */
        public Outcome.FlowOutcome tryExecute(Object input, Clock clk, boolean trace) {
            if (clk == null) clk = clock;
            Outcome.ExecutionTrace rec = trace ? new Outcome.ExecutionTrace(contractVersion, diagnosticHook) : null;
            Outcome.FlowOutcome primary = primary(input, clk, rec);
            Outcome.FlowOutcome outcome = finalize(input, clk, primary, rec);
            if (rec != null) outcome.trace = rec;
            return outcome;
        }
        // Async parity: Java has no awaitables; executeAsync is identical (SPEC 11.7 equivalent).
        /** Async-parity variant; identical semantics to tryExecute (SPEC 11.7). */
        public Outcome.FlowOutcome executeAsync(Object input) { return tryExecute(input); }

        /** Execute propagating an unrecovered exception (SPEC 11.4, D13). */
        public Outcome.FlowOutcome execute(Object input) throws Exception {
            Outcome.FlowOutcome o = tryExecute(input);
            if (o.executionStatus == Outcome.ExecutionStatus.FAILED && o.primaryException != null) {
                if (o.primaryException instanceof Exception e) throw e;
                if (o.primaryException instanceof Error e) throw e;
                throw new RuntimeException(String.valueOf(o.primaryException));
            }
            return o;
        }

        private List<Rule> orderedRules() {
            List<Rule> r = new ArrayList<>(rules);
            if (mode == Outcome.EvaluationMode.Priority) {
                r.sort((a, b) -> Integer.compare(b.priority, a.priority));
            }
            return r;
        }

        private Outcome.FlowOutcome primary(Object input, Clock clock, Outcome.ExecutionTrace rec) {
            try {
                return evaluate(input, clock, rec);
            } catch (Throwable t) {
                if (t instanceof FlowErrors.KindCancelled) {
                    if (rec != null) rec.emit("cancelled_observed", null, null, clock.wall());
                    Outcome.FlowOutcome o = new Outcome.FlowOutcome();
                    o.executionStatus = Outcome.ExecutionStatus.CANCELLED;
                    o.interruption = new Outcome.InterruptionInfo(Outcome.InterruptionKind.cancelled, "host", clock.wall());
                    o.primaryException = t;
                    return o;
                }
                if (t instanceof FlowErrors.KindTimeout) {
                    if (rec != null) rec.emit("timed_out_observed", null, null, clock.wall());
                    Outcome.FlowOutcome o = new Outcome.FlowOutcome();
                    o.executionStatus = Outcome.ExecutionStatus.TIMED_OUT;
                    o.interruption = new Outcome.InterruptionInfo(Outcome.InterruptionKind.timed_out, "external", clock.wall());
                    o.primaryException = t;
                    return o;
                }
                return handleException(input, clock, t, rec);
            }
        }

        private Outcome.FlowOutcome evaluate(Object input, Clock clock, Outcome.ExecutionTrace rec) throws Exception {
            List<Rule> rs = orderedRules();
            List<Object> secondary = new ArrayList<>();
            List<Outcome.Effect> effects = new ArrayList<>();
            boolean matched = false;
            Object value = null;

            for (Rule rule : rs) {
                if (cancelCheck != null && cancelCheck.getAsBoolean()) {
                    throw new FlowErrors.KindCancelled("cancelled");
                }
                if ("then".equals(rule.kind)) {
                    if (!matched) continue;
                    try {
                        value = rule.action.apply(input, value);
                        if (rec != null) rec.emit("action_executed", rule.id, null, clock.wall());
                    } catch (Throwable t) {
                        if (rec != null) rec.emit("action_raised", rule.id, null, clock.wall());
                        throw t;
                    }
                    effects.addAll(rule.effects);
                    if (!rule.effects.isEmpty() && rec != null) rec.emit("effect_proposed", rule.id, null, clock.wall());
                    continue;
                }
                if (matched && mode != Outcome.EvaluationMode.AllMatch) {
                    if (rec != null) rec.emit("skipped_by_short_circuit", rule.id, null, clock.wall());
                    continue;
                }
                if (rule.effectiveFrom != null && clock.wall() < rule.effectiveFrom ||
                    rule.effectiveUntil != null && clock.wall() >= rule.effectiveUntil) {
                    if (rec != null) rec.emit("rule_skipped", rule.id, "not_effective", clock.wall());
                    continue;
                }
                boolean holds;
                String skipReason = null;
                try {
                    holds = rule.condition.test(input);
                    if (rec != null) rec.emit("condition_evaluated", rule.id, null, clock.wall());
                    if ("when_not".equals(rule.kind)) holds = !holds;
                    if (rule.guard != null) {
                        boolean g = rule.guard.test(input);
                        if (rec != null) rec.emit("guard_evaluated", rule.id, null, clock.wall());
                        if (!g) { holds = false; skipReason = "guard_blocked"; }
                    }
                    if (!holds && skipReason == null) skipReason = "condition_false";
                } catch (Throwable t) {
                    if (rec != null) rec.emit("condition_raised", rule.id, null, clock.wall());
                    throw t;
                }
                if (!holds) {
                    if (skipReason != null && rec != null) rec.emit("rule_skipped", rule.id, skipReason, clock.wall());
                    continue;
                }
                matched = true;
                try {
                    value = rule.action.apply(input, null);
                    if (rec != null) rec.emit("action_executed", rule.id, null, clock.wall());
                } catch (Throwable t) {
                    if (rec != null) rec.emit("action_raised", rule.id, null, clock.wall());
                    throw t;
                }
                effects.addAll(rule.effects);
                if (!rule.effects.isEmpty() && rec != null) rec.emit("effect_proposed", rule.id, null, clock.wall());
                for (HookFn hook : hooks) {
                    try {
                        hook.accept(input, rule.id, value);
                        if (rec != null) rec.emit("hook_invoked", rule.id, null, clock.wall());
                    } catch (Throwable t) {
                        secondary.add(t);
                        if (rec != null) rec.emit("hook_raised", rule.id, null, clock.wall());
                    }
                }
            }

            if (matched) {
                Outcome.FlowOutcome o = Outcome.completed(value);
                o.secondaryExceptions = secondary;
                o.effects = effects;
                return o;
            }
            if (fallback != null) {
                if ("otherwise".equals(fallback.kind) && fallback.action != null) {
                    Outcome.FlowOutcome o = Outcome.noMatch(fallback.action.apply(input, null));
                    o.secondaryExceptions = secondary; o.effects = effects;
                    return o;
                }
                if ("default_if_no_match".equals(fallback.kind)) {
                    Outcome.FlowOutcome o = Outcome.noMatch(fallback.value);
                    o.secondaryExceptions = secondary; o.effects = effects;
                    return o;
                }
            }
            Outcome.FlowOutcome o = Outcome.noMatch(null);
            o.secondaryExceptions = secondary; o.effects = effects;
            return o;
        }

        private Outcome.FlowOutcome handleException(Object input, Clock clock, Throwable exc, Outcome.ExecutionTrace rec) {
            Object current = exc;
            for (CatchRule cr : catches) {
                if ("rethrow".equals(cr.kind)) {
                    if (rec != null) rec.emit("rethrow_reached", null, null, clock.wall());
                    break;
                }
                if ("any".equals(cr.kind)) {
                    if (rec != null) rec.emit("catch_matched", cr.id, null, clock.wall());
                    try {
                        Object v = cr.handler.handle(input, current);
                        if (rec != null) rec.emit("catch_handled", cr.id, null, clock.wall());
                        Outcome.FlowOutcome o = Outcome.completed(v);                        o.decisionStatus = null;                        o.recovery = new Outcome.RecoveryInfo(current, cr.id, clock.wall());
                        return o;
                    } catch (Throwable t) { current = t; continue; }
                }
                if (!FlowErrors.kindOfException(current).equals(cr.excKind)) {
                    if (rec != null) rec.emit("catch_declined", cr.id, null, clock.wall());
                    continue;
                }
                if ("when".equals(cr.kind) && cr.predicate != null) {
                    if (rec != null) rec.emit("catch_predicate_evaluated", cr.id, null, clock.wall());
                    try {
                        if (!cr.predicate.test(input, current)) {
                            if (rec != null) rec.emit("catch_declined", cr.id, null, clock.wall());
                            continue;
                        }
                    } catch (Throwable t) {
                        if (rec != null) rec.emit("catch_predicate_raised", cr.id, null, clock.wall());
                        current = t; continue;
                    }
                }
                if (rec != null) rec.emit("catch_matched", cr.id, null, clock.wall());
                try {
                    Object v = cr.handler.handle(input, current);
                    if (rec != null) rec.emit("catch_handled", cr.id, null, clock.wall());
                    Outcome.FlowOutcome o = Outcome.completed(v);                    o.decisionStatus = null;                    o.recovery = new Outcome.RecoveryInfo(current, cr.id, clock.wall());
                    return o;
                } catch (Throwable t) { current = t; continue; }
            }
            return Outcome.failed(current);
        }

        private Outcome.FlowOutcome finalize(Object input, Clock clock, Outcome.FlowOutcome outcome, Outcome.ExecutionTrace rec) {
            if (finalizers.isEmpty()) return outcome;
            List<Object> cleanupExcs = new ArrayList<>();
            boolean isClean = true;
            boolean budgetExceeded = false;
            long budgetUsedMs = 0;
            for (int i = finalizers.size() - 1; i >= 0; i--) {
                CleanupFn fn = finalizers.get(i);
                FinallyContext fctx = new FinallyContext(outcome, outcome.value, outcome.primaryException, input);
                if (rec != null) rec.emit("finally_started", null, null, clock.wall());
                long start = clock.monotonic();
                try {
                    fn.accept(fctx);
                    if (rec != null) rec.emit("finally_completed", null, null, clock.wall());
                } catch (Throwable t) {
                    isClean = false; cleanupExcs.add(t);
                    if (rec != null) rec.emit("finally_raised", null, null, clock.wall());
                }
                if (finallyTimeoutMs > 0) {
                    long elapsed = clock.monotonic() - start;
                    budgetUsedMs += elapsed;
                    if (elapsed > finallyTimeoutMs) budgetExceeded = true;
                }
            }
            if (budgetExceeded) isClean = false;
            List<Object> secondary = new ArrayList<>(outcome.secondaryExceptions);
            secondary.addAll(cleanupExcs);
            Object primaryExc = outcome.primaryException;
            if (finallyPolicy == Outcome.FinallyFailurePolicy.ReplacePrimary &&
                outcome.executionStatus == Outcome.ExecutionStatus.FAILED &&
                outcome.primaryException != null && !cleanupExcs.isEmpty()) {
                secondary.add(outcome.primaryException);
                primaryExc = cleanupExcs.get(cleanupExcs.size() - 1);
            }
            outcome.secondaryExceptions = secondary;
            outcome.primaryException = primaryExc;
            outcome.finalization = new Outcome.FinalizationInfo(isClean, cleanupExcs, budgetExceeded, budgetUsedMs);
            return outcome;
        }

        /** Simulate decision semantics without hooks or finalizers (SPEC 12.5). */
        public Outcome.FlowOutcome simulate(Object input) { return simulateWithClock(input, clock); }

        /** Simulate with an explicit clock (SPEC 12.5). */
        public Outcome.FlowOutcome simulateWithClock(Object input, Clock clk) {
            FlowContract sim = new FlowContract();
            sim.rules = rules; sim.mode = mode; sim.fallback = fallback;
            sim.catches = List.of(); sim.hooks = List.of(); sim.finalizers = List.of();
            sim.finallyPolicy = finallyPolicy; sim.clock = clk;
            sim.contractVersion = contractVersion;
            sim.hasPortable = hasPortable; sim.portableRules = portableRules;
            sim.cancelCheck = cancelCheck; sim.finallyTimeoutMs = finallyTimeoutMs;
            sim.flowId = flowId;
            return sim.tryExecute(input);
        }
    }
}
