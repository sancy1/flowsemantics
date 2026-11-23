package flowsemantics;

import java.util.HashMap;
import java.util.Map;

/** Isolated per-invocation execution context (SPEC 4.1.3, 6.2). */
public final class FlowContext {
    /** The input value passed to the execution. */
    public final Object input;
    /** The injected clock (SystemClock when none supplied). */
    public final Clock clock;
    /** Per-invocation mutable state; never shared between invocations. */
    public final Map<String, Object> state;

    /** Create a FlowContext for one invocation. */
    public FlowContext(Object input, Clock clock) {
        this.input = input;
        this.clock = clock != null ? clock : new SystemClock();
        this.state = new HashMap<>();
    }
}
