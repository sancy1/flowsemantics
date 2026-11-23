# When not to use FlowSemantics

The honesty page. Native code is the right choice in all of the following
cases.

## Native code wins

- A single `if (x > 10)`.
- A short chain of `elif` branches.
- A simple `switch` / `match`.
- A simple `try / catch` / `try / except`.
- `with` / `async with` for resource cleanup.
- A tight hot loop.
- A `finally` block that must mutate the result value.
- Any decision that does not need to be traced, tested, simulated,
  versioned, audited, ported, externalized, or validated.

For these, FlowSemantics adds no value and some overhead. Do not use it.

## Specific notes

### unless()

`unless()` is deliberately omitted from v0.1. `when_not(predicate)`
expresses the same logic without ambiguity. Do not expect `unless()` to
appear in the API before v0.2 at the earliest, and only if a compelling
ergonomic case is demonstrated.

### Thread safety

A compiled `FlowContract` is structurally immutable, and execution
contexts are isolated per invocation. **User callbacks are not guaranteed
to be thread-safe.** A callback that closes over a mutable object is not
safe to execute concurrently. The library does not claim otherwise.

### Cleanup timeout

`WithFinallyTimeout` establishes a bounded cooperative budget for cleanup.
It does **not** forcibly terminate arbitrary synchronous code. The
guarantee is honest: cooperative callbacks receive a fresh cancellation
token bounded by the budget; callbacks that ignore the token can overrun
the budget, and the overrun is reported via `finalization.cleanup_budget_exceeded`.

