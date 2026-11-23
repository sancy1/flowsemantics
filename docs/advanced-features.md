# Advanced features

Cross-language reference for the advanced FlowSemantics surface: flow
composition, decision tables, effective dates, cooperative cancellation,
batch simulation, portability reporting, deep validation, and finalization
budgets. Every feature is implemented identically in all five languages
(Python, TypeScript, Go, Java, C#/.NET) and covered by unit tests plus the
shared conformance vectors.

## Feature matrix

| Feature | SPEC | Python | TypeScript | Go | Java | C# |
|---|---|---|---|---|---|---|
| Merge flows | 10.7 | `Flow.merge` | `flow.merge` | `flow.Merge` | `Advanced.merge` | `Advanced.Merge` |
| Decision table | 10.8 | `table_to_flow` / `DecisionTable` | `tableToFlow` / `DecisionTable` | `TableToFlow` | `Advanced.tableToFlow` | `Advanced.TableToFlow` |
| Effective dates | 12.9 | `effective_from`/`effective_until` kwargs | `effectiveFrom`/`effectiveUntil` opts | `WithEffectiveFrom`/`WithEffectiveUntil` | `when(..., effFrom, effUntil)` params | `When(..., effectiveFrom, effectiveUntil)` params |
| Cancel check | 11.6 | `with_cancel_check` | `withCancelCheck` | `WithCancelCheck` | `withCancelCheck` | `WithCancelCheck` |
| Finally timeout | 11.8/16.4 | `with_finally_timeout` | `withFinallyTimeout` | `WithFinallyTimeout` | `withFinallyTimeout` | `WithFinallyTimeout` |
| Simulate batch | 12.5 | `contract.simulate_batch` | `contract.simulateBatch` | `contract.SimulateBatch` | `Advanced.simulateBatch` | `Advanced.SimulateBatch` |
| Portability report | 4.4 | `contract.portability_report` | `contract.portability` | `contract.Portability` | `Advanced.portability` | `Advanced.Portability` |
| Validate depth | 12.8 | `contract.validate` | `contract.validate` | `contract.Validate` | `Trust.validate` | `Trust.Validate` |
| Default alias | 10.4 | `default` | `default` | `Default` | `defaultValue` | `DefaultValue` |

## Merge (SPEC 10.7)

Splices another flow's rules, catches, hooks, and finalizers at the call
site. Modes must match; RuleIds must be unique across the merged result;
the outer flow's fallback wins when both flows define one.

```python
inner = Flow().when(...).default_if_no_match("inner-fb")
outer = Flow().when(...).default_if_no_match("outer-fb")
outer.merge(inner)          # outer fallback wins
contract = outer.compile()
```

```typescript
outer.merge(inner);         // returns this
const contract = outer.compile();
```

```go
merged, err := outer.Merge(inner)   // returns (*Flow, error)
contract, err := merged.Compile()
```

```java
Flow merged = Advanced.merge(outer, inner);   // returns Flow
Flow.FlowContract contract = merged.compile();
```

```csharp
var merged = Advanced.Merge(outer, inner);    // returns Flow
var contract = merged.Compile();
```

## Decision tables (SPEC 10.8)

A `DecisionTable` is an ordered list of rows; each row pairs a RuleId, a
list of conditions (ANDed), and an action. Hit policies map to evaluation
modes: `FIRST` → FirstMatch, `COLLECT` → AllMatch, `PRIORITY` → Priority,
`UNIQUE` → FirstMatch with overlap validation.

```python
from flowsemantics.configuration.table import DecisionTable, DecisionTableRow, table_to_flow

table = DecisionTable(rows=[
    DecisionTableRow(id="big", conditions=[lambda i: i["total"] > 100], action=lambda i: "bulk"),
    DecisionTableRow(id="std", conditions=[lambda i: True], action=lambda i: "standard"),
], hit_policy="FIRST")
flow = table_to_flow(table)
```

```typescript
import { tableToFlow } from "flowsemantics/table";

const flow = tableToFlow({
  hitPolicy: "FIRST",
  rows: [
    { id: "big", conditions: [(i) => i.total > 100], action: () => "bulk" },
    { id: "std", conditions: [() => true], action: () => "standard" },
  ],
});
```

```go
flow, err := TableToFlow(&DecisionTable{Rows: rows, Policy: HitFirst})
```

```java
Flow flow = Advanced.tableToFlow(new Advanced.DecisionTable(rows, HitPolicy.FIRST));
```

```csharp
var flow = Advanced.TableToFlow(new Advanced.DecisionTable {
  Rows = rows,                       // List<Advanced.DecisionTableRow>
  Policy = Advanced.HitPolicy.FIRST,
});
```

## Effective dates (SPEC 12.9)

Rules may carry `effective_from` (inclusive) and `effective_until`
(exclusive) windows evaluated against the contract's injected wall clock.
Outside the window the rule is skipped with a `rule_skipped` /
`not_effective` trace event. Inverted windows fail `compile()`.

- Python: `datetime` objects via `when(..., effective_from=..., effective_until=...)`.
- TypeScript: epoch-ms numbers via `when(cond, act, { effectiveFrom, effectiveUntil })`.
- Go: epoch-ms via `WithEffectiveFrom(ms)` / `WithEffectiveUntil(ms)` rule options.
- Java: `Long` epoch-ms via the extended `when(cond, action, id, guard, priority, effects, effFrom, effUntil)` overload.
- C#: `long?` epoch-ms via `When(cond, action, id, guard, priority, effects, effectiveFrom, effectiveUntil)`.

Portable IR carries the window as ISO-8601 strings; all engines parse and
validate them identically.

## Cooperative cancellation (SPEC 11.6)

`with_cancel_check` / `WithCancelCheck` installs a predicate polled before
each rule evaluation. When it returns true the contract produces a
`CANCELLED` outcome with an `InterruptionInfo(kind="cancelled")` — an
interruption, not an exception, so catch rules never see it.

```python
Flow().with_cancel_check(lambda: token.cancelled) ...
```

```typescript
new Flow().withCancelCheck(() => token.cancelled) ...
```

```go
NewFlow().WithCancelCheck(func() bool { return token.Cancelled() }) ...
```

```java
Flow.create().withCancelCheck(token::isCancelled) ...
```

```csharp
Flow.Create().WithCancelCheck(() => token.IsCancellationRequested) ...
```

## Finally timeout budget (SPEC 11.8, 16.4)

`with_finally_timeout(ms)` bounds each finalizer's wall-clock budget. The
outcome's `FinalizationInfo` reports `cleanup_budget_exceeded` and
`cleanup_budget_used_ms`. Finalizers always run to completion — the budget
is reported, not enforced by interruption.

## Simulate batch (SPEC 12.5)

Runs `simulate()` over a list of inputs and aggregates a firing
distribution: totals by execution status, decision status, and produced
value, plus the individual outcomes.

```python
report = contract.simulate_batch(inputs)   # dict with by_status/by_decision/by_value
```

```typescript
const report = contract.simulateBatch(inputs);
```

```go
report := contract.SimulateBatch(inputs)    // *SimulateReport
```

```java
Advanced.SimulateReport report = Advanced.simulateBatch(contract, inputs);
```

```csharp
var report = Advanced.SimulateBatch(contract, inputs);
```

## Portability report (SPEC 4.4)

Classifies a compiled contract as `PORTABLE` or `NATIVE` and lists the
offending components (native rules, catches, finalizers, hooks) that keep
it out of the Portable IR.

```python
rep = contract.portability_report()        # {"classification": ..., "offenders": [...]}
```

```typescript
const rep = contract.portability();         // { classification, offenders }
```

```go
class, offenders := contract.Portability()  // (string, []string)
```

```java
String[] rep = Advanced.portability(contract);   // [classification, offendersCsv]
```

```csharp
var (cls, offenders) = Advanced.Portability(contract);
```

## Validate depth (SPEC 12.8)

`validate()` performs static analysis without execution. Beyond the base
checks (empty flow, duplicate RuleIds, catch_any ordering, effective-window
inversion), deep mode adds:

- `unreachable_rule` — a rule that cannot match because an earlier
  unconditional portable rule always matches first (FirstMatch/AllMatch
  short-circuit modes only; provable only for portable const-true).
- `overlapping_rules` — two same-kind rules with structurally identical
  portable conditions.
- `possible_gap` — no fallback configured, so some inputs may produce
  NO_MATCH.

Unreachable/overlap analysis applies only to PORTABLE contracts; native
conditions are opaque callables and cannot be proven equivalent.

## Default alias (SPEC 10.4)

`default(value)` is a convenience alias for `default_if_no_match(value)`
in every language: `default` (Python/TypeScript), `Default` (Go),
`defaultValue` (Java), `DefaultValue` (C#).

## Flow identity, clock injection, and diagnostics (SPEC 4.1.3, 6.1, 12.2)

Every language supports naming a flow and injecting a deterministic clock
at build time; the clock is used for all timestamps and effective-date
checks:

- Python: `Flow().with_flow_id("id").with_clock(clock)`
- TypeScript: `flow.withFlowId("id").withClock(clock)`
- Go: `flow.WithFlowID("id").WithClock(clock)`
- Java: `Flow.create().withFlowId("id").withClock(clock)`
- C#: `Flow.Create().WithFlowId("id").WithClock(clock)`

`flow_id` and `contract_version` are carried into Portable IR export.

A diagnostic hook can be attached via `with_trace(hook)` /
`withTrace(hook)` / `WithTrace(hook)`; each emitted `TraceEvent` gains a
`contract_version` field and an optional `diagnostics` map produced by
the hook (opt-in — no data is captured without it).

```python
from flowsemantics.configuration.flow import Flow
from flowsemantics.execution.clock import FakeClock

flow = (
    Flow()
    .with_flow_id("order-approval")
    .with_clock(FakeClock(wall=..., monotonic=0.0))
    .with_trace(diagnostic_hook=lambda event: {"tag": event.type})
    .when(lambda i: i["total"] > 100, then=lambda i: "bulk", id="big")
)
contract = flow.compile()
```

```typescript
import { Flow } from "flowsemantics";
import { FakeClock } from "flowsemantics/clock";

const flow = new Flow()
  .withFlowId("order-approval")
  .withClock(new FakeClock(0, 0))
  .withTrace((event) => ({ tag: event.type }))
  .when((i) => i.total > 100, () => "bulk", { id: "big" });
const contract = flow.compile();
```

```go
flow := NewFlow().
    WithFlowID("order-approval").
    WithClock(NewFakeClock(0, 0)).
    WithTrace(func(e *TraceEvent) map[string]any { return map[string]any{"tag": string(e.Type)} }).
    When(func(i any) (bool, error) { return i.(map[string]any)["total"].(int) > 100, nil },
        func(i, p any) (any, error) { return "bulk", nil }, WithRuleID("big"))
contract, _ := flow.Compile()
```

```java
Flow.FlowContract contract = Flow.create()
    .withFlowId("order-approval")
    .withClock(new FakeClock(0, 0))
    .withTrace(e -> Map.of("tag", e.type))
    .when(i -> ((Map<?,?>) i).get("total") instanceof Integer t && t > 100,
          (i, p) -> "bulk", "big")
    .compile();
```

```csharp
var contract = Flow.Create()
    .WithFlowId("order-approval")
    .WithClock(new FakeClock(0, 0))
    .WithTrace(e => new Dictionary<string, object?> { ["tag"] = e.Type })
    .When(i => ((IDictionary<string, object?>)i)["total"] is int t && t > 100,
          (i, p) => "bulk", "big")
    .Compile();
```

## Execute variants (SPEC 11.4, 11.7)

- `try_execute` / `tryExecute` / `TryExecute` — never throws; returns a
  `FlowOutcome` with `execution_status=FAILED` on unrecovered errors.
- `execute` / `executeAsync` / `Execute` / `ExecuteAsync` — async parity
  variants (identical semantics; awaits are host-side in C#/Java).
- `execute` (propagating) — rethrows the unrecovered primary exception:
  Python `contract.execute(input)`, TypeScript `contract.execute(input)`,
  Go `contract.Execute(input)`, Java `contract.execute(input)` (throws
  `Exception`), C# `contract.Execute(input)`.

```python
outcome = contract.try_execute(input)   # never raises
value = contract.execute(input)         # raises on unrecovered error
await contract.try_execute_async(input) # async parity
```

```typescript
const outcome = contract.tryExecute(input);
const value = contract.execute(input);          // throws on unrecovered error
const ao = await contract.tryExecuteAsync(input);
```

```go
outcome := contract.TryExecute(input)      // never panics
value, err := contract.Execute(input)      // err on unrecovered error
asyncOutcome := contract.ExecuteAsync(input)
```

```java
Outcome.FlowOutcome outcome = contract.tryExecute(input);
Object value = contract.execute(input);    // throws Exception on unrecovered error
```

```csharp
var outcome = contract.TryExecute(input);
var value = contract.Execute(input);       // throws on unrecovered error
var asyncOutcome = contract.ExecuteAsync(input);
```

## Simulate with clock (SPEC 12.5)

`simulate` runs decision semantics without hooks or finalizers.
Python `contract.simulate(input, clock=clk)`, TypeScript
`contract.simulate(input, { clock: clk })`, Go
`contract.SimulateWithClock(input, clk)`, Java
`contract.simulateWithClock(input, clk)`, C#
`contract.SimulateWithClock(input, clk)` — an explicit clock gives
deterministic effective-date and timestamp behavior.

```python
outcome = contract.simulate(input, clock=FakeClock(...))
```

```typescript
const outcome = contract.simulate(input, { clock: new FakeClock(0, 0) });
```

```go
outcome := contract.SimulateWithClock(input, NewFakeClock(0, 0))
```

```java
Outcome.FlowOutcome outcome = contract.simulateWithClock(input, new FakeClock(0, 0));
```

```csharp
var outcome = contract.SimulateWithClock(input, new FakeClock(0, 0));
```

## Merge a compiled contract (SPEC 10.7)

In addition to merging `Flow` builders, every language can splice a
compiled `FlowContract`'s rules, catches, hooks, and finalizers into a
builder: Python `flow.merge(contract)`, TypeScript `flow.merge(contract)`,
Go `flow.MergeContract(contract)`, Java `Advanced.mergeContract(flow,
contract)`, C# `Advanced.MergeContract(flow, contract)`. Same mode and
RuleId-uniqueness rules as builder merge.

```python
outer = Flow().when(...).default_if_no_match("outer-fb")
outer.merge(inner_contract)   # splices compiled contract's rules
```

```typescript
outer.merge(innerContract);   // accepts Flow | FlowContract
```

```go
merged, err := outer.MergeContract(innerContract)
```

```java
Flow merged = Advanced.mergeContract(outer, innerContract);
```

```csharp
var merged = Advanced.MergeContract(outer, innerContract);
```

## FlowContext (SPEC 4.1.3, 6.2)

An isolated per-invocation context carrying `input`, `clock`, and a
mutable `state` map: Python `FlowContext`, TypeScript `FlowContext`,
Go `FlowContext`, Java `FlowContext`, C# `FlowContext`.

```python
from flowsemantics.execution.context import FlowContext
ctx = FlowContext(input={"a": 1}, clock=FakeClock(...))
ctx.state["seen"] = True          # per-invocation only
```

```typescript
import { FlowContext } from "flowsemantics";
const ctx = new FlowContext({ a: 1 }, new FakeClock(0, 0));
ctx.state["seen"] = true;   // plain record, per-invocation only
```

```go
ctx := &FlowContext{Input: map[string]any{"a": 1}, Clock: NewFakeClock(0, 0)}
ctx.State["seen"] = true
```

```java
FlowContext ctx = new FlowContext(Map.of("a", 1), new FakeClock(0, 0));
ctx.state.put("seen", true);
```

```csharp
var ctx = new FlowContext(new Dictionary<string, object?> { ["a"] = 1 }, new FakeClock(0, 0));
ctx.State["seen"] = true;
```

## Portable IR serialization (SPEC 14.2, 9.2)

Every language exports PExpr builders (`pField`/`PField`/`PField` etc.),
the closed `OPS` operator set, `exprToDict`/`ExprToNode`/`ExprToNode`,
and full `PortableFlow` serialization:
`portableFlowToDict`/`PortableFlowToNode`/`PortableFlowToNode`,
`portableFlowToJSON`/`PortableFlowToJSON`/`PortableFlowToJSON`, and
`portableFlowFromJSON`/`PortableFlowFromJSON`/`PortableFlowFromJSON`
(enforcing the SPEC 9.2 size limit). `contract_version` is parsed and
emitted; `toIRJSON` uses the canonical serializer in all languages.

```python
from flowsemantics.configuration.portable import (
    pfield, pgt, pconst, pand, pnot, pis_not_null, expr_to_dict,
)
expr = pand(pgt(pfield("total"), pconst(100)), pnot(pis_not_null(pfield("sku"))))
d = expr_to_dict(expr)
json_text = contract.to_ir_json()
```

```typescript
import { pfield, pgt, pconst, pand, pnot, pis_not_null, exprToDict } from "flowsemantics/portable";
const expr = pand(pgt(pfield("total"), pconst(100)), pnot(pis_not_null(pfield("sku"))));
const d = exprToDict(expr);
const json = contract.toIRJSON();
```

```go
expr := PAnd(PGt(PField("total"), PConst(100)), PNot(PIsNotNull(PField("sku"))))
d := ExprToDict(expr)
jsonText, _ := contract.ToIRJSON()
```

```java
Portable.PExpr expr = Portable.pAnd(
    Portable.pGt(Portable.pField("total"), Portable.pConst(100)),
    Portable.pNot(Portable.pIsNotNull(Portable.pField("sku"))));
var d = Portable.exprToDict(expr);
String json = Trust.toIRJSON(contract);
```

```csharp
var expr = Portable.PAnd(
    Portable.PGt(Portable.PField("total"), Portable.PConst(100)),
    Portable.PNot(Portable.PIsNotNull(Portable.PField("sku"))));
var d = Portable.ExprToNode(expr);
var json = Trust.ToIRJSON(contract);
```

## Trust-layer clock parity (SPEC 12.6, 12.7)

`replay` reconstructs a `FakeClock` from the record's wall/monotonic
timestamps and re-simulates with it; `shadow` accepts an optional clock
for deterministic comparison in every language.

```python
from flowsemantics.trust import record, replay, shadow, ReplayMode
rec = record(contract, input, clock=FakeClock(...))
result = replay(rec, contract, mode=ReplayMode.DECISION)
report = shadow(current, candidate, inputs, clock=FakeClock(...))
```

```typescript
import { record, replay, shadow, ReplayMode } from "flowsemantics/trust";
const rec = record(contract, input, { clock: new FakeClock(0, 0) });
const result = replay(rec, contract, { mode: ReplayMode.DECISION });
const report = shadow(current, candidate, inputs, { clock: new FakeClock(0, 0) });
```

```go
rec := Record(contract, input, NewFakeClock(0, 0))
result, _ := Replay(rec, contract, ReplayDecision, nil, nil, false)
report := Shadow(current, candidate, inputs, NewFakeClock(0, 0))
```

```java
Trust.ReplayRecord rec = Trust.record(contract, input, new FakeClock(0, 0));
Trust.ReplayResult result = Trust.replay(rec, contract, Trust.ReplayMode.DECISION, null, null, false);
Trust.ShadowReport report = Trust.shadow(current, candidate, inputs, new FakeClock(0, 0));
```

```csharp
var rec = Trust.Record(contract, input, new FakeClock(0, 0));
var result = Trust.Replay(rec, contract, Trust.ReplayMode.Decision, null, null, false);
var report = Trust.Shadow(current, candidate, inputs, new FakeClock(0, 0));
```
