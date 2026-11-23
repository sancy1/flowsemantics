package flowsemantics;

/** Deterministic clock for tests and replay (SPEC 6.2, 12.10). */
public final class FakeClock implements Clock {
    private long wallMs;
    private long monoMs;
    /** Create a FakeClock with fixed wall (epoch ms) and monotonic (ms) values. */
    public FakeClock(long wall, long mono) { wallMs = wall; monoMs = mono; }
    /** Current wall time in epoch milliseconds. */
    public long wall() { return wallMs; }
    /** Current monotonic time in milliseconds. */
    public long monotonic() { return monoMs; }
    /** Advance both wall and monotonic clocks by the given milliseconds. */
    public void advance(long ms) { wallMs += ms; monoMs += ms; }
}
