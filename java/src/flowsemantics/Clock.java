package flowsemantics;

/** Injected clock abstraction (SPEC 6.1, 6.2). Wall is epoch ms; monotonic is a
 *  process-relative millisecond counter. */
public interface Clock {
    /** Wall-clock time in epoch milliseconds. */
    long wall();
    /** Monotonic time in milliseconds (process-relative). */
    long monotonic();
}

/** Default clock backed by the system clock (SPEC 6.3). */
final class SystemClock implements Clock {
    private final long start = System.nanoTime();
    /** Wall-clock time in epoch milliseconds. */
    public long wall() { return System.currentTimeMillis(); }
    /** Monotonic time in milliseconds since construction. */
    public long monotonic() { return (System.nanoTime() - start) / 1_000_000; }
}

