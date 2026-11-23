namespace FlowSemantics;

/// Terminal execution status of a flow outcome (SPEC 3.1).
public enum ExecutionStatus { Completed, Failed, Cancelled, TimedOut }

/// Decision status of a flow outcome (SPEC 3.2).
public enum DecisionStatus { Approved, NoMatch }

/// Rule evaluation mode (SPEC 10.6).
public enum EvaluationMode { FirstMatch, AllMatch, Priority }

/// How a finalizer failure interacts with the primary outcome (SPEC 16.3).
public enum FinallyFailurePolicy { PreservePrimary, Attach, ReplacePrimary }

/// Kind of interruption observed during execution (SPEC 3.3).
public enum InterruptionKind { Cancelled, TimedOut }

/// Interruption metadata recorded on an outcome (SPEC 3.3).
public sealed record InterruptionInfo(InterruptionKind Kind, string Source, long Timestamp);

/// Recovery metadata recorded when a catch rule recovers an exception (SPEC 3.4).
public sealed record RecoveryInfo(object OriginalException, string HandlerRuleId, long RecoveredAt);

/// Finalization metadata recorded on an outcome (SPEC 3.5, 16.4).
public sealed record FinalizationInfo(bool IsClean, IReadOnlyList<object> CleanupExceptions,
    bool CleanupBudgetExceeded = false, long CleanupBudgetUsedMs = 0);

/// A proposed effect — data only, never applied by the library (SPEC 3.7, 5).
public sealed record Effect(string Name, object? Payload);

/// A single trace event (SPEC 3.8, 12.1). Carries no input values.
public sealed record TraceEvent(string Type, string? RuleId, string? Reason, long Timestamp,
    string? ContractVersion = null, IReadOnlyDictionary<string, object?>? Diagnostics = null);

/// Diagnostic hook: receives each TraceEvent, may return extra fields (SPEC 12.2).
public delegate IReadOnlyDictionary<string, object?>? DiagnosticHook(TraceEvent e);

/// Collected execution trace (SPEC 3.8, 12.1-12.3).
public sealed class ExecutionTrace
{
    /// Emitted events in order.
    public List<TraceEvent> Events { get; } = new();
    /// Contract version stamped on every event.
    public string? ContractVersion { get; set; }
    /// Optional diagnostic hook invoked per event.
    public DiagnosticHook? Hook { get; set; }
    /// Emit a trace event, applying the diagnostic hook when present.
    public void Emit(string type, string? ruleId, string? reason, long timestamp)
    {
        var e = new TraceEvent(type, ruleId, reason, timestamp, ContractVersion);
        if (Hook is not null)
            e = e with { Diagnostics = Hook(e) };
        Events.Add(e);
    }
}

/// The canonical outcome of a flow execution (SPEC 3.6, 7).
public sealed class FlowOutcome
{
    /// Terminal execution status.
    public required ExecutionStatus ExecutionStatus { get; init; }
    /// Decision status; null for recovered outcomes (SPEC 7).
    public DecisionStatus? DecisionStatus { get; set; }
    /// Produced value.
    public object? Value { get; set; }
    /// Unrecovered primary exception, if any.
    public object? PrimaryException { get; set; }
    /// Recovery metadata when a catch rule recovered.
    public RecoveryInfo? Recovery { get; set; }
    /// Interruption metadata for CANCELLED/TIMED_OUT outcomes.
    public InterruptionInfo? Interruption { get; set; }
    /// Finalization metadata.
    public FinalizationInfo? Finalization { get; set; }
    /// Secondary exceptions isolated from hooks/finalizers.
    public List<object> SecondaryExceptions { get; set; } = new();
    /// Proposed effects in evaluation order.
    public List<Effect> Effects { get; set; } = new();
    /// Execution trace when tracing was enabled.
    public ExecutionTrace? Trace { get; set; }

    /// Create a COMPLETED + APPROVED outcome.
    public static FlowOutcome Completed(object? value) => new()
    {
        ExecutionStatus = ExecutionStatus.Completed,
        DecisionStatus = FlowSemantics.DecisionStatus.Approved,
        Value = value,
    };

    /// Create a COMPLETED + NO_MATCH outcome.
    public static FlowOutcome NoMatch(object? value) => new()
    {
        ExecutionStatus = ExecutionStatus.Completed,
        DecisionStatus = FlowSemantics.DecisionStatus.NoMatch,
        Value = value,
    };

    /// Create a FAILED outcome carrying the primary exception.
    public static FlowOutcome Failed(object exception) => new()
    {
        ExecutionStatus = ExecutionStatus.Failed,
        PrimaryException = exception,
    };
}
