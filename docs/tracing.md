# Tracing

> Part of the [feature catalog](features.md) - all 62 features.

> **Language coverage**: examples on this page are shown in Python. The
> semantics are identical in all five languages; only the API spelling
> differs. See [getting-started](getting-started.md) for the same example
> in Python, TypeScript, Go, Java, and C#.
>
> | Concept | Python | TypeScript | Go | Java | C# |
> |---|---|---|---|---|---|
> | Build flow | `Flow()` | `new Flow()` | `fs.NewFlow()` | `Flow.create()` | `Flow.Create()` |
> | Add rule | `.when(cond, then=act, id=...)` | `.when(cond, act, { id })` | `.When(cond, act, fs.WithRuleID(id))` | `.when(cond, act, id)` | `.When(cond, act, id)` |
> | Compile | `.compile()` | `.compile()` | `.Compile()` | `.compile()` | `.Compile()` |
> | Execute | `.try_execute(x)` | `.execute(x)` | `.TryExecute(x)` | `.tryExecute(x)` | `.TryExecute(x)` |


Execution traces (SPEC.md Sections 3.8, 12.1–12.3): an ordered,
immutable record of what the engine did — zero cost when disabled.

## Enabling

```python
contract = flow.compile()
outcome = contract.try_execute(input, trace=True)
# or permanently on the builder:
flow.with_trace()
```

`outcome.trace` is an `ExecutionTrace` with `.events`, each a
`TraceEvent(type, rule_id, reason, timestamp)`.

## Event vocabulary

Closed set of 22 event types (SPEC 12.1): `condition_evaluated`,
`condition_raised`, `guard_evaluated`, `action_executed`,
`action_raised`, `catch_matched`, `catch_predicate_evaluated`,
`catch_predicate_raised`, `catch_handled`, `catch_declined`,
`rethrow_reached`, `hook_invoked`, `hook_raised`, `effect_proposed`,
`skipped_by_short_circuit`, `skipped_by_mode`, `finally_started`,
`finally_completed`, `finally_raised`, `cancelled_observed`,
`timed_out_observed`, `rule_skipped`.

Skip events carry a `reason`: `condition_false`, `guard_blocked`,
`not_effective`, `earlier_match`, `mode_excluded`.

## Privacy

Traces may contain rule ids and values. `with_trace(diagnostic_hook=fn)`
and `try_execute(..., diagnostic_hook=fn)` let the application attach
redacted diagnostics; the library defers redaction to the application
(SPEC 12.2).

## explain()

```python
text = contract.explain(outcome.trace)
print(text)
```

`FlowContract.explain(trace)` renders the trace as human-readable lines
— no invented reasons (SPEC 12.4).
