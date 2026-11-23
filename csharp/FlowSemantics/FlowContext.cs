namespace FlowSemantics;

/// Isolated per-invocation execution context (SPEC 4.1.3, 6.2).
public sealed class FlowContext
{
    /// The input value passed to the execution.
    public object? Input { get; }
    /// The injected clock (SystemClock when none supplied).
    public IClock Clock { get; }
    /// Per-invocation mutable state; never shared between invocations.
    public Dictionary<string, object?> State { get; } = new();

    /// Create a FlowContext for one invocation.
    public FlowContext(object? input, IClock? clock)
    {
        Input = input;
        Clock = clock ?? new SystemClock();
    }
}
