# Error handling

FlowSemantics error semantics (SPEC.md Sections 11.1–11.6): catch rules,
hooks, cancellation, and timeout recognition.

## Catch rules

```python
from flowsemantics import Flow

flow = (
    Flow()
    .when(lambda order: order["total"] > 1000, then=lambda o: "manual-review")
    .catch(ValueError, lambda inp, exc: {"error": str(exc)})
    .catch_when(
        TimeoutError,
        lambda inp, exc: "transient" in str(exc),
        lambda inp, exc: "retry-later",
    )
    .catch_any(lambda inp, exc: "unexpected")
    .rethrow()  # optional: stop the chain, propagate
)
```

- `catch(exc_type, handler)` — isinstance match; first matching catch wins.
- `catch_when(exc_type, predicate, handler)` — additionally requires the
  predicate `(input, exception) -> bool`.
- `catch_any(handler)` — handles anything not caught earlier; must be
  registered after typed catches (`compile()` enforces ordering).
- `rethrow()` — propagates the current exception, stopping evaluation.
- A failing catch handler propagates the **new** exception, not the
  original (SPEC 11.1).

Handlers receive `(input, exception)` and return the outcome value.
A recovered outcome carries `RecoveryInfo` and `decision_status=None`.

## Hooks

```python
flow.on_match(lambda inp, rule_id, value: audit_log(rule_id, value))
```

Hooks observe successful rule actions. A hook failure is isolated into
`outcome.secondary_exceptions` — it never changes the outcome and never
triggers a catch (SPEC 11.5).

## Cancellation and timeout

- `asyncio.CancelledError` → `ExecutionStatus.CANCELLED` +
  `InterruptionInfo(kind="cancelled")`. Bypasses all catch rules
  (SPEC 11.6.1, 11.6.3).
- `TimeoutError` → `ExecutionStatus.TIMED_OUT` +
  `InterruptionInfo(kind="timed_out")`. The library **recognizes**
  externally-imposed timeouts; it does not enforce them (SPEC 11.6.2).
  Catch rules MUST NOT catch either interruption.

## Async parity

`execute_async`/`try_execute_async` mirror the sync semantics exactly
(SPEC 11.7). Async-only contracts (any async callable) reject
`execute()`/`try_execute()` with `AsyncOnlyContractError`.
