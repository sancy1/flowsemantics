# Finalization

Outcome-aware finalization (SPEC.md Sections 11.8, 16): `finally_`
registers cleanup that runs for **every** outcome status, including
FAILED, CANCELLED, and TIMED_OUT.

## Basic usage

```python
from flowsemantics import Flow, FinallyContext

def cleanup(ctx: FinallyContext) -> None:
    print(ctx.status, ctx.result.value)  # read-only view

flow = Flow().when(...).finally_(cleanup)
```

The `FinallyContext` exposes `result`, `status`, `value`, `exception`,
`context` (the input), and a **fresh** `cancellation_token` bounded by
the finally timeout — never the outer cancellation token (SPEC 16.1).

## Failure policies

When a finalizer raises, `FinallyFailurePolicy` decides (SPEC 16.4):

| Policy | Behavior |
|---|---|
| `PreservePrimary` (default) | Outcome unchanged; cleanup exception → `secondary_exceptions`; `is_clean=False` |
| `Attach` | Same as PreservePrimary for outcome; cleanup exception attached |
| `ReplacePrimary` | On FAILED outcomes, the cleanup exception becomes primary; the original is demoted to secondary |

```python
flow.with_finally_policy("ReplacePrimary")
```

## Timeout budget

```python
flow.with_finally_timeout(500)  # ms per finalizer; default 5000
```

The budget is **cooperative**: the finalizer receives a cancellation
token and is expected to observe it. The library does not hard-kill
synchronous finalizers (SPEC 16.7, B8). Async finalizers are bounded
via `asyncio.wait_for`.

## Ordering and isolation

- Finalizers run **LIFO** (innermost first).
- Each finalizer is isolated: one failure never skips the rest.
- Cleanup exceptions never trigger catch rules and never re-enter
  evaluation (FR3).
- `FinalizationInfo.is_clean` is false iff any finalizer raised, was
  cancelled, or exceeded its budget.

## Merge

`Flow.merge` concatenates finalizers; outer-flow finalizers run after
inner ones per LIFO ordering (SPEC 10.7).
