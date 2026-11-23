namespace FlowSemantics;

/// Injected clock abstraction (SPEC 6.1, 6.2). Wall is epoch ms; Monotonic is a
/// process-relative millisecond counter.
public interface IClock
{
    /// Wall-clock time in epoch milliseconds.
    long Wall();
    /// Monotonic time in milliseconds (process-relative).
    long Monotonic();
}

/// Default clock backed by the system clock (SPEC 6.3).
public sealed class SystemClock : IClock
{
    private readonly long _start = System.Diagnostics.Stopwatch.GetTimestamp();
    /// Wall-clock time in epoch milliseconds.
    public long Wall() => DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
    /// Monotonic time in milliseconds since construction.
    public long Monotonic() => (long)((System.Diagnostics.Stopwatch.GetTimestamp() - _start) * 1000.0 / System.Diagnostics.Stopwatch.Frequency);
}

/// Deterministic clock for tests and replay (SPEC 6.2, 12.10).
public sealed class FakeClock : IClock
{
    private long _wallMs;
    private long _monoMs;
    /// Create a FakeClock with fixed wall (epoch ms) and monotonic (ms) values.
    public FakeClock(long wall, long mono) { _wallMs = wall; _monoMs = mono; }
    /// Current wall time in epoch milliseconds.
    public long Wall() => _wallMs;
    /// Current monotonic time in milliseconds.
    public long Monotonic() => _monoMs;
    /// Advance both wall and monotonic clocks by the given milliseconds.
    public void Advance(long ms) { _wallMs += ms; _monoMs += ms; }
}
