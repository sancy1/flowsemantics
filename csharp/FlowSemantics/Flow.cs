using System.Text.Json.Nodes;

namespace FlowSemantics;

/// Flow builder + FlowContract — SPEC 7, 10, 11, 16.
public sealed class Flow
{
    /// Condition callback: returns true when the rule holds (SPEC 10.2).
    public delegate bool ConditionFn(object? input);
    /// Action callback: produces the rule's value (SPEC 10.2).
    public delegate object? ActionFn(object? input, object? previous);
    /// Guard callback: additional gate evaluated after the condition (SPEC 10.1).
    public delegate bool GuardFn(object? input);
    /// Catch handler: receives (input, exception), returns recovery value (SPEC 11.1).
    public delegate object? ExceptionHandler(object? input, object exception);
    /// Catch predicate: decides whether a catch rule applies (SPEC 11.2).
    public delegate bool ExceptionPredicate(object? input, object exception);
    /// Match hook: invoked after each when/when_not action (SPEC 11.5).
    public delegate void HookFn(object? input, string ruleId, object? value);
    /// Finalizer cleanup: invoked for every outcome (SPEC 11.8, 16.1).
    public delegate void CleanupFn(FinallyContext ctx);

    /// Context passed to a finalizer (SPEC 16.1).
    public sealed class FinallyContext
    {
        /// The outcome being finalized.
        public required FlowOutcome Result { get; init; }
        /// Execution status of the outcome.
        public required ExecutionStatus Status { get; init; }
        /// Produced value, if any.
        public object? Value { get; init; }
        /// Unrecovered primary exception, if any.
        public object? Exception { get; init; }
        /// The original input.
        public object? Context { get; init; }
        /// Cooperative cancellation token (single-element bool array).
        public bool[] CancellationToken { get; } = { false };
    }

    internal sealed class Rule
    {
        public required string Id { get; init; }
        public required string Kind { get; init; } // when | when_not | then
        public ConditionFn? Condition { get; init; }
        public GuardFn? Guard { get; init; }
        public ActionFn? Action { get; init; }
        public int Priority { get; init; }
        public List<Effect> Effects { get; } = new();
        public long? EffectiveFrom { get; init; }
        public long? EffectiveUntil { get; init; }
    }

    internal sealed class CatchRule
    {
        public required string Kind { get; init; } // typed | when | any | rethrow
        public string? ExcKind { get; init; }
        public ExceptionPredicate? Predicate { get; init; }
        public ExceptionHandler? Handler { get; init; }
        public string? Id { get; init; }
    }

    internal sealed class Fallback
    {
        public required string Kind { get; init; }
        public ActionFn? Action { get; init; }
        public object? Value { get; init; }
    }

    private readonly List<Rule> _rules = new();
    private readonly List<CatchRule> _catches = new();
    private readonly List<HookFn> _hooks = new();
    private readonly List<CleanupFn> _finalizers = new();
    private EvaluationMode _mode = EvaluationMode.FirstMatch;
    private Fallback? _fallback;
    private FinallyFailurePolicy _finallyPolicy = FinallyFailurePolicy.PreservePrimary;
    private bool _traceEnabled;
    private readonly List<Portable.PortableRule> _portableRules = new();
    private bool _hasPortable;
    private Func<bool>? _cancelCheck;
    private long _finallyTimeoutMs;
    private string? _flowId;
    private IClock? _clock;
    private DiagnosticHook? _diagnosticHook;

    internal List<Rule> Rules => _rules;
    internal List<CatchRule> Catches => _catches;
    internal List<HookFn> Hooks => _hooks;
    internal List<CleanupFn> Finalizers => _finalizers;
    internal EvaluationMode Mode => _mode;
    internal Fallback? FallbackRule { get => _fallback; set => _fallback = value; }

    /// Create a new empty flow builder (FirstMatch mode).
    public static Flow Create() => new();

    /// Set the evaluation mode (SPEC 10.6).
    public Flow WithMode(EvaluationMode mode) { _mode = mode; return this; }
    /// Set the flow identifier carried into Portable IR export (SPEC 14.2).
    public Flow WithFlowId(string id) { _flowId = id; return this; }
    /// Inject a deterministic clock used for all timestamps (SPEC 6.2).
    public Flow WithClock(IClock clock) { _clock = clock; return this; }

    /// Register a positive condition rule (SPEC 10.2).
    public Flow When(ConditionFn cond, ActionFn action, string id, GuardFn? guard = null, int priority = 0, List<Effect>? effects = null,
        long? effectiveFrom = null, long? effectiveUntil = null)
    {
        var r = new Rule { Id = id, Kind = "when", Condition = cond, Action = action, Guard = guard, Priority = priority,
            EffectiveFrom = effectiveFrom, EffectiveUntil = effectiveUntil };
        if (effects is not null) r.Effects.AddRange(effects);
        _rules.Add(r); return this;
    }

    /// Register a negated condition rule (SPEC 10.2).
    public Flow WhenNot(ConditionFn cond, ActionFn action, string id, long? effectiveFrom = null, long? effectiveUntil = null)
    {
        _rules.Add(new Rule { Id = id, Kind = "when_not", Condition = cond, Action = action,
            EffectiveFrom = effectiveFrom, EffectiveUntil = effectiveUntil });
        return this;
    }

    /// Register a sequential transformation stage (SPEC 10.5).
    public Flow Then(ActionFn action, string id)
    {
        _rules.Add(new Rule { Id = id, Kind = "then", Action = action });
        return this;
    }

    /// Register an otherwise fallback action (SPEC 10.4).
    public Flow Otherwise(ActionFn action) { _fallback = new Fallback { Kind = "otherwise", Action = action }; return this; }
    /// Register a default_if_no_match fallback value (SPEC 10.4).
    public Flow DefaultIfNoMatch(object? value) { _fallback = new Fallback { Kind = "default_if_no_match", Value = value }; return this; }

    /// Register a typed catch rule (SPEC 11.1).
    public Flow CatchTyped(string excKind, ExceptionHandler handler, string id)
    {
        _catches.Add(new CatchRule { Kind = "typed", ExcKind = excKind, Handler = handler, Id = id });
        return this;
    }

    /// Register a catch rule with a predicate (SPEC 11.2).
    public Flow CatchWhen(string excKind, ExceptionPredicate pred, ExceptionHandler handler, string id)
    {
        _catches.Add(new CatchRule { Kind = "when", ExcKind = excKind, Predicate = pred, Handler = handler, Id = id });
        return this;
    }

    /// Register a catch-all rule; must follow typed catches (SPEC 11.3).
    public Flow CatchAny(ExceptionHandler handler, string id)
    {
        _catches.Add(new CatchRule { Kind = "any", Handler = handler, Id = id });
        return this;
    }

    /// Register a rethrow marker that stops catch routing (SPEC 11.4).
    public Flow Rethrow() { _catches.Add(new CatchRule { Kind = "rethrow" }); return this; }
    /// Register a match hook invoked after each when/when_not action (SPEC 11.5).
    public Flow OnMatch(HookFn hook) { _hooks.Add(hook); return this; }
    /// Register a finalizer invoked for every outcome (SPEC 11.8, 16.1).
    public Flow Finally(CleanupFn cleanup) { _finalizers.Add(cleanup); return this; }
    /// Set the finalizer failure policy (SPEC 16.3).
    public Flow WithFinallyPolicy(FinallyFailurePolicy policy) { _finallyPolicy = policy; return this; }
    /// Set the finalizer cleanup budget in milliseconds (SPEC 16.7).
    public Flow WithFinallyTimeout(long ms) { _finallyTimeoutMs = ms; return this; }
    /// Set a cooperative cancellation check polled during evaluation (SPEC 11.6).
    public Flow WithCancelCheck(Func<bool> check) { _cancelCheck = check; return this; }
    /// Enable trace collection for executions of this flow (SPEC 12.3).
    public Flow WithTrace() { _traceEnabled = true; return this; }
    /// Enable trace collection with a diagnostic hook (SPEC 12.2, 12.3).
    public Flow WithTrace(DiagnosticHook hook) { _traceEnabled = true; _diagnosticHook = hook; return this; }
    /// Convenience alias for DefaultIfNoMatch (SPEC 10.4).
    public Flow DefaultValue(object? value) => DefaultIfNoMatch(value);

    /// Register a portable when rule (SPEC 14.2).
    public Flow WhenExpr(Portable.PExpr cond, Portable.PExpr transform, string id, List<Effect>? effects = null)
    {
        _hasPortable = true;
        var pr = new Portable.PortableRule { RuleId = id, Kind = "when", Condition = cond, Transform = transform };
        if (effects is not null) pr.Effects.AddRange(effects);
        _portableRules.Add(pr); return this;
    }

    /// Register a portable when_not rule (SPEC 14.2).
    public Flow WhenNotExpr(Portable.PExpr cond, Portable.PExpr transform, string id, List<Effect>? effects = null)
    {
        _hasPortable = true;
        var pr = new Portable.PortableRule { RuleId = id, Kind = "when_not", Condition = cond, Transform = transform };
        if (effects is not null) pr.Effects.AddRange(effects);
        _portableRules.Add(pr); return this;
    }

    /// Build a Flow from a Portable IR document (SPEC 14.2).
    public static Flow FromIr(JsonNode ir)
    {
        var pf = Portable.PortableFlowFromNode(ir);
        var f = Create().WithMode(pf.Mode);
        f._hasPortable = true;
        foreach (var pr in pf.Rules)
        {
            if (pr.Kind == "when") f.WhenExpr(pr.Condition!, pr.Transform!, pr.RuleId, pr.Effects.Count > 0 ? pr.Effects : null);
            else f.WhenNotExpr(pr.Condition!, pr.Transform!, pr.RuleId, pr.Effects.Count > 0 ? pr.Effects : null);
        }
        if (pf.Fallback is not null && pf.Fallback["kind"]?.GetValue<string>() == "default_if_no_match")
            f.DefaultIfNoMatch(Portable.ToClr(pf.Fallback["value"]));
        return f;
    }

    /// Compile the builder into an immutable FlowContract (SPEC 4.3, 10.9).
    public FlowContract Compile()
    {
        for (var i = 0; i < _catches.Count; i++)
        {
            if (_catches[i].Kind == "any")
            {
                for (var j = i + 1; j < _catches.Count; j++)
                    if (_catches[j].Kind != "rethrow")
                        throw new StructureError("catch_any must be registered after typed catches");
            }
        }
        var compiled = new List<Rule>();
        if (_hasPortable)
        {
            foreach (var pr in _portableRules)
            {
                var cond = pr.Condition!;
                var tr = pr.Transform!;
                var r = new Rule
                {
                    Id = pr.RuleId, Kind = pr.Kind, Priority = pr.Priority,
                    Condition = input => Portable.EvalExpr(cond, input) is true,
                    Action = (input, prev) => Portable.EvalExpr(tr, input),
                    EffectiveFrom = Advanced.ParseEffective(pr.EffectiveFrom),
                    EffectiveUntil = Advanced.ParseEffective(pr.EffectiveUntil),
                };
                r.Effects.AddRange(pr.Effects);
                compiled.Add(r);
            }
        }
        else compiled.AddRange(_rules);

        foreach (var r in compiled)
            if (r.EffectiveFrom is not null && r.EffectiveUntil is not null && r.EffectiveFrom >= r.EffectiveUntil)
                throw new StructureError($"rule {r.Id}: effective_from must be before effective_until (SPEC 12.9)");

        var seenIds = new HashSet<string>();
        foreach (var r in compiled)
            if (!seenIds.Add(r.Id))
                throw new StructureError($"duplicate RuleId: {r.Id} (SPEC 4.3)");

        var contract = new FlowContract
        {
            Rules = compiled, Mode = _mode, Fallback = _fallback,
            Catches = new List<CatchRule>(_catches), Hooks = new List<HookFn>(_hooks),
            Finalizers = new List<CleanupFn>(_finalizers), FinallyPolicy = _finallyPolicy,
            TraceEnabled = _traceEnabled, Clock = _clock ?? new SystemClock(),
            CancelCheck = _cancelCheck, FinallyTimeoutMs = _finallyTimeoutMs,
            FlowId = _flowId, DiagnosticHook = _diagnosticHook,
        };
        contract.ContractVersion = Trust.ContractVersion(compiled, _fallback, _mode,
            new List<CatchRule>(_catches), _finalizers.Count, _finallyPolicy, _finallyTimeoutMs, _traceEnabled);
        contract.HasPortable = _hasPortable;
        contract.PortableRules = new List<Portable.PortableRule>(_portableRules);
        return contract;
    }

    /// A compiled, immutable flow contract (SPEC 4.1, 10.9).
    public sealed class FlowContract
    {
        internal List<Rule> Rules { get; init; } = null!;
        internal EvaluationMode Mode { get; init; }
        internal Fallback? Fallback { get; init; }
        internal List<CatchRule> Catches { get; init; } = null!;
        internal List<HookFn> Hooks { get; init; } = null!;
        internal List<CleanupFn> Finalizers { get; init; } = null!;
        internal FinallyFailurePolicy FinallyPolicy { get; init; }
        internal bool TraceEnabled { get; init; }
        internal IClock Clock { get; init; } = null!;
        internal Func<bool>? CancelCheck { get; init; }
        internal long FinallyTimeoutMs { get; init; }
        internal string? FlowId { get; init; }
        internal DiagnosticHook? DiagnosticHook { get; init; }

        /// Structural contract version (SHA-256, algorithm v1) (SPEC 12.9).
        public string ContractVersion { get; internal set; } = "1";
        internal bool HasPortable { get; set; }
        internal List<Portable.PortableRule> PortableRules { get; set; } = new();

        /// The clock injected at build time.
        public IClock ClockRef => Clock;

        /// Execute and always return a FlowOutcome (SPEC 11.4).
        public FlowOutcome TryExecute(object? input) => TryExecute(input, Clock, TraceEnabled);

        /// Execute with an explicit clock and trace flag (SPEC 11.4, 12.3).
        public FlowOutcome TryExecute(object? input, IClock clock, bool trace)
        {
            if (clock is null) clock = Clock;
            var rec = trace ? new ExecutionTrace { ContractVersion = ContractVersion, Hook = DiagnosticHook } : null;
            var primary = Primary(input, clock, rec);
            var outcome = Finalize(input, clock, primary, rec);
            if (rec is not null) outcome.Trace = rec;
            return outcome;
        }

        // Async parity: C# awaits are host-side; execute path is identical (SPEC 11.7).
        /// Async-parity variant; identical semantics to TryExecute (SPEC 11.7).
        public FlowOutcome ExecuteAsync(object? input) => TryExecute(input);

        /// Execute propagating an unrecovered exception (SPEC 11.4, D13).
        public FlowOutcome Execute(object? input)
        {
            var o = TryExecute(input);
            if (o.ExecutionStatus == ExecutionStatus.Failed && o.PrimaryException is not null)
            {
                if (o.PrimaryException is Exception e) throw e;
                throw new Exception(Convert.ToString(o.PrimaryException));
            }
            return o;
        }

        private List<Rule> OrderedRules()
        {
            var r = new List<Rule>(Rules);
            if (Mode == EvaluationMode.Priority)
                r.Sort((a, b) => b.Priority.CompareTo(a.Priority));
            return r;
        }

        private FlowOutcome Primary(object? input, IClock clock, ExecutionTrace? rec)
        {
            try { return Evaluate(input, clock, rec); }
            catch (KindCancelled t)
            {
                rec?.Emit("cancelled_observed", null, null, clock.Wall());
                return new FlowOutcome
                {
                    ExecutionStatus = ExecutionStatus.Cancelled,
                    Interruption = new InterruptionInfo(InterruptionKind.Cancelled, "host", clock.Wall()),
                    PrimaryException = t,
                };
            }
            catch (KindTimeout t)
            {
                rec?.Emit("timed_out_observed", null, null, clock.Wall());
                return new FlowOutcome
                {
                    ExecutionStatus = ExecutionStatus.TimedOut,
                    Interruption = new InterruptionInfo(InterruptionKind.TimedOut, "external", clock.Wall()),
                    PrimaryException = t,
                };
            }
            catch (Exception t) { return HandleException(input, clock, t, rec); }
        }

        private FlowOutcome Evaluate(object? input, IClock clock, ExecutionTrace? rec)
        {
            var rs = OrderedRules();
            var secondary = new List<object>();
            var effects = new List<Effect>();
            var matched = false;
            object? value = null;

            foreach (var rule in rs)
            {
                if (CancelCheck is not null && CancelCheck())
                    throw new KindCancelled("cancelled");
                if (rule.Kind == "then")
                {
                    if (!matched) continue;
                    try
                    {
                        value = rule.Action!(input, value);
                        rec?.Emit("action_executed", rule.Id, null, clock.Wall());
                    }
                    catch (Exception)
                    {
                        rec?.Emit("action_raised", rule.Id, null, clock.Wall());
                        throw;
                    }
                    effects.AddRange(rule.Effects);
                    if (rule.Effects.Count > 0) rec?.Emit("effect_proposed", rule.Id, null, clock.Wall());
                    continue;
                }
                if (matched && Mode != EvaluationMode.AllMatch)
                {
                    rec?.Emit("skipped_by_short_circuit", rule.Id, null, clock.Wall());
                    continue;
                }
                if ((rule.EffectiveFrom is not null && clock.Wall() < rule.EffectiveFrom) ||
                    (rule.EffectiveUntil is not null && clock.Wall() >= rule.EffectiveUntil))
                {
                    rec?.Emit("rule_skipped", rule.Id, "not_effective", clock.Wall());
                    continue;
                }
                bool holds;
                string? skipReason = null;
                try
                {
                    holds = rule.Condition!(input);
                    rec?.Emit("condition_evaluated", rule.Id, null, clock.Wall());
                    if (rule.Kind == "when_not") holds = !holds;
                    if (rule.Guard is not null)
                    {
                        var g = rule.Guard(input);
                        rec?.Emit("guard_evaluated", rule.Id, null, clock.Wall());
                        if (!g) { holds = false; skipReason = "guard_blocked"; }
                    }
                    if (!holds && skipReason is null) skipReason = "condition_false";
                }
                catch (Exception)
                {
                    rec?.Emit("condition_raised", rule.Id, null, clock.Wall());
                    throw;
                }
                if (!holds)
                {
                    if (skipReason is not null) rec?.Emit("rule_skipped", rule.Id, skipReason, clock.Wall());
                    continue;
                }
                matched = true;
                try
                {
                    value = rule.Action!(input, null);
                    rec?.Emit("action_executed", rule.Id, null, clock.Wall());
                }
                catch (Exception)
                {
                    rec?.Emit("action_raised", rule.Id, null, clock.Wall());
                    throw;
                }
                effects.AddRange(rule.Effects);
                if (rule.Effects.Count > 0) rec?.Emit("effect_proposed", rule.Id, null, clock.Wall());
                foreach (var hook in Hooks)
                {
                    try
                    {
                        hook(input, rule.Id, value);
                        rec?.Emit("hook_invoked", rule.Id, null, clock.Wall());
                    }
                    catch (Exception t)
                    {
                        secondary.Add(t);
                        rec?.Emit("hook_raised", rule.Id, null, clock.Wall());
                    }
                }
            }

            if (matched)
                return new FlowOutcome { ExecutionStatus = ExecutionStatus.Completed, DecisionStatus = DecisionStatus.Approved, Value = value, SecondaryExceptions = secondary, Effects = effects };
            if (Fallback is not null)
            {
                if (Fallback.Kind == "otherwise" && Fallback.Action is not null)
                    return new FlowOutcome { ExecutionStatus = ExecutionStatus.Completed, DecisionStatus = DecisionStatus.NoMatch, Value = Fallback.Action(input, null), SecondaryExceptions = secondary, Effects = effects };
                if (Fallback.Kind == "default_if_no_match")
                    return new FlowOutcome { ExecutionStatus = ExecutionStatus.Completed, DecisionStatus = DecisionStatus.NoMatch, Value = Fallback.Value, SecondaryExceptions = secondary, Effects = effects };
            }
            return new FlowOutcome { ExecutionStatus = ExecutionStatus.Completed, DecisionStatus = DecisionStatus.NoMatch, SecondaryExceptions = secondary, Effects = effects };
        }

        private FlowOutcome HandleException(object? input, IClock clock, Exception exc, ExecutionTrace? rec)
        {
            object current = exc;
            foreach (var cr in Catches)
            {
                if (cr.Kind == "rethrow")
                {
                    rec?.Emit("rethrow_reached", null, null, clock.Wall());
                    break;
                }
                if (cr.Kind == "any")
                {
                    rec?.Emit("catch_matched", cr.Id, null, clock.Wall());
                    try
                    {
                        var v = cr.Handler!(input, (Exception)current);
                        rec?.Emit("catch_handled", cr.Id, null, clock.Wall());
                        return new FlowOutcome
                        {
                            ExecutionStatus = ExecutionStatus.Completed,
                            Value = v,
                            Recovery = new RecoveryInfo(current, cr.Id!, clock.Wall()),
                        };
                    }
                    catch (Exception t) { current = t; continue; }
                }
                if (FlowErrors.KindOfException(current) != cr.ExcKind)
                {
                    rec?.Emit("catch_declined", cr.Id, null, clock.Wall());
                    continue;
                }
                if (cr.Kind == "when" && cr.Predicate is not null)
                {
                    rec?.Emit("catch_predicate_evaluated", cr.Id, null, clock.Wall());
                    try
                    {
                        if (!cr.Predicate(input, (Exception)current))
                        {
                            rec?.Emit("catch_declined", cr.Id, null, clock.Wall());
                            continue;
                        }
                    }
                    catch (Exception t)
                    {
                        rec?.Emit("catch_predicate_raised", cr.Id, null, clock.Wall());
                        current = t; continue;
                    }
                }
                rec?.Emit("catch_matched", cr.Id, null, clock.Wall());
                try
                {
                    var v = cr.Handler!(input, (Exception)current);
                    rec?.Emit("catch_handled", cr.Id, null, clock.Wall());
                    return new FlowOutcome
                    {
                        ExecutionStatus = ExecutionStatus.Completed,
                        Value = v,
                        Recovery = new RecoveryInfo(current, cr.Id!, clock.Wall()),
                    };
                }
                catch (Exception t) { current = t; continue; }
            }
            return FlowOutcome.Failed(current);
        }

        private FlowOutcome Finalize(object? input, IClock clock, FlowOutcome outcome, ExecutionTrace? rec)
        {
            if (Finalizers.Count == 0) return outcome;
            var cleanupExcs = new List<object>();
            var isClean = true;
            var budgetExceeded = false;
            long budgetUsedMs = 0;
            for (var i = Finalizers.Count - 1; i >= 0; i--)
            {
                var fn = Finalizers[i];
                var fctx = new FinallyContext
                {
                    Result = outcome, Status = outcome.ExecutionStatus,
                    Value = outcome.Value, Exception = outcome.PrimaryException, Context = input,
                };
                rec?.Emit("finally_started", null, null, clock.Wall());
                var start = clock.Monotonic();
                try { fn(fctx); rec?.Emit("finally_completed", null, null, clock.Wall()); }
                catch (Exception t) { isClean = false; cleanupExcs.Add(t); rec?.Emit("finally_raised", null, null, clock.Wall()); }
                if (FinallyTimeoutMs > 0)
                {
                    var elapsed = clock.Monotonic() - start;
                    budgetUsedMs += elapsed;
                    if (elapsed > FinallyTimeoutMs) budgetExceeded = true;
                }
            }
            if (budgetExceeded) isClean = false;
            var secondary = new List<object>(outcome.SecondaryExceptions);
            secondary.AddRange(cleanupExcs);
            object? primaryExc = outcome.PrimaryException;
            if (FinallyPolicy == FinallyFailurePolicy.ReplacePrimary &&
                outcome.ExecutionStatus == ExecutionStatus.Failed &&
                outcome.PrimaryException is not null && cleanupExcs.Count > 0)
            {
                secondary.Add(outcome.PrimaryException);
                primaryExc = cleanupExcs[^1];
            }
            outcome.SecondaryExceptions = secondary;
            outcome.PrimaryException = primaryExc;
            outcome.Finalization = new FinalizationInfo(isClean, cleanupExcs, budgetExceeded, budgetUsedMs);
            return outcome;
        }

        /// Simulate decision semantics without hooks or finalizers (SPEC 12.5).
        public FlowOutcome Simulate(object? input) => SimulateWithClock(input, Clock);

        /// Simulate with an explicit clock (SPEC 12.5).
        public FlowOutcome SimulateWithClock(object? input, IClock clock)
        {
            var sim = new FlowContract
            {
                Rules = Rules, Mode = Mode, Fallback = Fallback,
                Catches = new List<CatchRule>(), Hooks = new List<HookFn>(),
                Finalizers = new List<CleanupFn>(), FinallyPolicy = FinallyPolicy, Clock = clock,
                ContractVersion = ContractVersion, HasPortable = HasPortable, PortableRules = PortableRules,
                CancelCheck = CancelCheck, FinallyTimeoutMs = FinallyTimeoutMs, FlowId = FlowId,
            };
            return sim.TryExecute(input);
        }
    }
}
