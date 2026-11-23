# Getting started with FlowSemantics

FlowSemantics expresses decision-and-error flows as a compiled,
inspectable contract. You build a `Flow`, `compile()` it into an
immutable `FlowContract`, and `execute()` or `try_execute()` it.

## Install

```bash
pip install flow-semantics
```

## Your first flow

```python
from flowsemantics import Flow

def total_above_100(order):
    return order["total"] > 100

def approve(order):
    return "approved:" + str(order["total"])

def reject(order):
    return "rejected"

flow = (
    Flow()
    .when(total_above_100, then=approve, id="large-order")
    .when_not(total_above_100, then=reject, id="small-order")
)
contract = flow.compile()

outcome = contract.try_execute({"total": 250})
print(outcome.execution_status)   # ExecutionStatus.COMPLETED
print(outcome.decision_status)    # DecisionStatus.APPROVED
print(outcome.value)              # 'approved:250'
```

This exact example runs in `python/samples/scratch_consumer/main.py`.

## The outcome model

Every execution returns a `FlowOutcome`:

- `execution_status` — `COMPLETED`, `FAILED`, `CANCELLED`, `TIMED_OUT`
- `decision_status` — `APPROVED`, `REJECTED`, or `NO_MATCH` (absent on failure)
- `value` — the produced value, if any
- `recovery`, `interruption`, `finalization` — metadata, populated only
  when applicable
- `primary_exception`, `secondary_exceptions` — never silently dropped
- `effects` — proposed side effects; the library never executes them
- `trace` — populated when `with_trace()` is enabled (Phase 3.0)

`execute()` raises an unrecovered exception to the caller;
`try_execute()` always returns the `FlowOutcome`. Choose per call site.

## Rules

- `when(condition, then=action, id=...)` — match when condition is true.
- `when_not(condition, then=action, id=...)` — match when false.
- `then(stage, id=...)` — sequential stage after a match; receives
  `(input, previous_output)`.
- `otherwise(action)` — dynamic fallback when nothing matched.
- `default(value)` / `default_if_no_match(value)` — constant fallback.
- `with_mode(EvaluationMode.X)` — `FIRST_MATCH` (default), `ALL_MATCH`,
  `PRIORITY`.
- `merge(other)` — splice another flow's rules at the call site.
- `Flow.from_table(table)` — build from a `DecisionTable`.

There is deliberately no `unless()` in v0.1: `when_not()` expresses the
same logic unambiguously (see `docs/when-not-to-use.md` and ADR-0001, O5).

## Conditions and actions are pure

Conditions and transformations MUST be pure: no I/O, no mutation, same
input → same output. Side effects are proposed as `Effect` data and
applied only by your own executor. The library cannot enforce purity for
arbitrary callables — it is your contract to honor (SPEC.md section 5).

## Compile once, execute many

`compile()` validates the flow (unique RuleIds, fallback rules, then
placement) and returns a structurally immutable `FlowContract` that is
safe to share across threads. Each `execute()` gets an isolated context.
User callbacks are not guaranteed thread-safe — that is on you.

## Next steps

- `docs/cookbook.md` — canonical patterns
- `docs/error-handling.md` — catch rules (Phase 2)
- `docs/finalization.md` — guaranteed cleanup (Phase 2)
- `SPEC.md` — the normative specification
