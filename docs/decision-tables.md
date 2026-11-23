# Decision tables

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


`DecisionTable` (SPEC.md Section 10.8): a column-based table of
condition→action rows that compiles to the same rule list as the fluent
API. Hit policies are DMN-aligned.

> **Status**: implemented (Phase 1) with unit and integration coverage.
> Conformance-vector representation is deferred — the vector schema
> cannot yet express tables (see `conformance/coverage.md`).

## When to use

Decision tables suit classification problems: many rows, each a
conjunction of column predicates mapping to an outcome. They are data,
not code — inspectable and diffable.

## API

```python
from flowsemantics import DecisionTable, DecisionTableRow, Flow

table = DecisionTable(
    rows=(
        DecisionTableRow(
            id="eu-review",
            conditions=(
                lambda o: o["total"] > 100,
                lambda o: o.get("region") == "EU",
            ),
            action=lambda o: "eu-review",
        ),
        DecisionTableRow(
            id="standard",
            conditions=(lambda o: o["total"] > 100,),
            action=lambda o: "standard",
        ),
        DecisionTableRow(
            id="reject",
            conditions=(lambda o: True,),
            action=lambda o: "reject",
        ),
    ),
    hit_policy="FIRST",
)

flow = Flow.from_table(table)
contract = flow.compile()
```

- Each row's `conditions` are ANDed; rows evaluate in order.
- `hit_policy`: `FIRST` → FirstMatch, `COLLECT` → AllMatch,
  `PRIORITY` → Priority, `UNIQUE` → FirstMatch plus a compile-time
  exclusivity check where statically provable (a validation warning is
  recorded for opaque callables — SPEC 10.8).
- `table_to_flow(table)` is also exported for direct use.

## Merge and portability

- `Flow.merge` requires matching evaluation modes; the outer fallback
  wins over the inner (SPEC 10.7).
- Table-backed contracts classify as NATIVE for portable IR purposes
  until the IR gains a table construct (SPEC 14.2 subset is rule-list
  only today).
