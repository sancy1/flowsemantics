# Cookbook

> Part of the [feature catalog](features.md) - all 62 features.


Canonical before/after patterns. Every snippet here is exercised by a
sample or a conformance vector.

## Approve or reject by threshold

```python
from flowsemantics import Flow

flow = (
    Flow()
    .when(lambda o: o["total"] > 100, then=lambda o: "approved", id="large")
    .when_not(lambda o: o["total"] > 100, then=lambda o: "rejected", id="small")
)
outcome = flow.compile().try_execute({"total": 250})
# outcome.value == "approved"
```

## No-match fallback

```python
flow = (
    Flow()
    .when(lambda o: o["total"] > 100, then=lambda o: "approved", id="large")
    .default_if_no_match("no-decision")
)
outcome = flow.compile().try_execute({"total": 10})
# outcome.decision_status == NO_MATCH, outcome.value == "no-decision"
```

`otherwise(action)` is the dynamic variant: the action runs on the input
when nothing matched. `default(value)` is an alias of
`default_if_no_match(value)`.

## Sequential stages with then

```python
flow = (
    Flow()
    .when(lambda o: o["total"] > 0, then=lambda o: o["total"], id="has-total")
    .then(lambda i, prev: prev * 2, id="double")
)
outcome = flow.compile().try_execute({"total": 21})
# outcome.value == 42
```

`then` runs only when the preceding rule matched, and receives
`(input, previous_output)`. If nothing matched, `then` is skipped.

## Multiple matches with AllMatch

```python
from flowsemantics import EvaluationMode

flow = (
    Flow()
    .with_mode(EvaluationMode.ALL_MATCH)
    .when(lambda o: o["total"] > 0, then=lambda o: "positive", id="p")
    .when(lambda o: o["total"] < 1000, then=lambda o: "small", id="s")
)
outcome = flow.compile().try_execute({"total": 50})
# Both rules match; the last match determines the value: "small"
```

## Priority ordering

```python
flow = (
    Flow()
    .with_mode(EvaluationMode.PRIORITY)
    .when(lambda o: True, then=lambda o: "low", id="low", priority=1)
    .when(lambda o: True, then=lambda o: "high", id="high", priority=10)
)
outcome = flow.compile().try_execute({})
# outcome.value == "high" — highest priority wins regardless of order
```

## Composing flows with merge

```python
fraud = Flow().when(lambda o: o.get("fraud"), then=lambda o: "fraud", id="fraud")
limits = Flow().when(lambda o: o["total"] > 1000, then=lambda o: "over-limit", id="limit")

flow = Flow().merge(fraud).merge(limits)
```

Merge splices rules at the call site. Both flows must share the same
`EvaluationMode`, and RuleIds must be unique across the combined flow.
If both flows define a fallback, the outer flow's fallback wins.

## Decision tables

```python
from flowsemantics import DecisionTable, DecisionTableRow, Flow

table = DecisionTable(
    rows=(
        DecisionTableRow(id="vip", conditions=(lambda o: o.get("vip"),), action=lambda o: "vip"),
        DecisionTableRow(id="big", conditions=(lambda o: o["total"] > 100,), action=lambda o: "big"),
    ),
    hit_policy="FIRST",
)
contract = Flow.from_table(table).compile()
```

Hit policies: `FIRST` → FirstMatch, `COLLECT` → AllMatch,
`PRIORITY` → Priority, `UNIQUE` → FirstMatch with exclusivity validation.

## execute vs try_execute

```python
contract = flow.compile()

try:
    contract.execute(order)          # raises unrecovered exceptions
except ValueError:
    ...

outcome = contract.try_execute(order)  # always returns FlowOutcome
if outcome.execution_status.name == "FAILED":
    ...
```

## What this cookbook does not cover yet

Exception recovery (`catch`), cancellation, finalization, tracing, and
replay arrive in Phases 2-3. See `docs/error-handling.md` and
`docs/finalization.md` when they ship.
