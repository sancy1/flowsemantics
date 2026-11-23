# Getting started with FlowSemantics

> Part of the [feature catalog](features.md) — all 62 features.

FlowSemantics expresses decision-and-error flows as a compiled, inspectable
contract. You build a `Flow`, `compile()` it into an immutable
`FlowContract`, and `execute()` / `try_execute()` it. The same semantics are
available in **five languages** — Python, TypeScript, Go, Java, and C# —
with idiomatic APIs in each.

## Install

Pick your language:

```bash
pip install flow-semantics          # Python
npm install flow-semantics-ts       # TypeScript (Node 22.18+)
go get github.com/sancy1/flowsemantics/go   # Go 1.23+
dotnet add package FlowSemantics    # C# / .NET 10
# Java: Maven Central publication in progress — see java/README.md
```

## Your first flow

The same example — approve orders over 100, reject the rest — in every
language. All five produce the identical outcome.

### Python

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

### TypeScript

```typescript
import { Flow, ExecutionStatus, DecisionStatus } from "flow-semantics-ts";

const totalAbove100 = (order: any) => order.total > 100;
const approve = (order: any) => "approved:" + order.total;
const reject = (_order: any) => "rejected";

const contract = new Flow()
  .when(totalAbove100, approve, { id: "large-order" })
  .whenNot(totalAbove100, reject, { id: "small-order" })
  .compile();

const outcome = contract.execute({ total: 250 });
console.log(outcome.execution_status);  // ExecutionStatus.COMPLETED
console.log(outcome.decision_status);   // DecisionStatus.APPROVED
console.log(outcome.value);             // 'approved:250'
```

### Go

```go
package main

import (
	"fmt"

	fs "github.com/sancy1/flowsemantics/go"
)

func main() {
	contract, err := fs.NewFlow().
		When(func(i any) (bool, error) {
			return i.(map[string]any)["total"].(int) > 100, nil
		}, func(_ any, _ any) (any, error) {
			return "approved", nil
		}, fs.WithRuleID("large-order")).
		WhenNot(func(i any) (bool, error) {
			return i.(map[string]any)["total"].(int) > 100, nil
		}, func(_ any, _ any) (any, error) {
			return "rejected", nil
		}, fs.WithRuleID("small-order")).
		Compile()
	if err != nil {
		panic(err)
	}

	outcome := contract.TryExecute(map[string]any{"total": 250})
	fmt.Println(outcome.ExecutionStatus) // fs.Completed
	fmt.Println(outcome.DecisionStatus)  // *fs.Approved
	fmt.Println(outcome.Value)           // approved
}
```

### Java

```java
import flowsemantics.*;
import java.util.*;

public class Main {
    public static void main(String[] args) throws Exception {
        var contract = Flow.create()
            .when(i -> ((Number) ((Map<?,?>) i).get("total")).intValue() > 100,
                  (i, p) -> "approved", "large-order")
            .whenNot(i -> ((Number) ((Map<?,?>) i).get("total")).intValue() > 100,
                    (i, p) -> "rejected", "small-order")
            .compile();

        var outcome = contract.tryExecute(Map.of("total", 250));
        System.out.println(outcome.executionStatus); // COMPLETED
        System.out.println(outcome.decisionStatus);  // APPROVED
        System.out.println(outcome.value);           // approved
    }
}
```

### C#

```csharp
using FlowSemantics;

var contract = Flow.Create()
    .When(i => (int)((Dictionary<string, object?>)i!)["total"]! > 100,
          (_, _) => "approved", "large-order")
    .WhenNot(i => (int)((Dictionary<string, object?>)i!)["total"]! > 100,
            (_, _) => "rejected", "small-order")
    .Compile();

var outcome = contract.TryExecute(
    new Dictionary<string, object?> { ["total"] = 250 });
Console.WriteLine(outcome.ExecutionStatus); // Completed
Console.WriteLine(outcome.DecisionStatus);  // Approved
Console.WriteLine(outcome.Value);           // approved
```

## The outcome model

Every execution returns a `FlowOutcome` (named idiomatically per language —
`FlowOutcome`, `Outcome`, etc.):

| Concept | Meaning |
|---|---|
| `execution_status` | `COMPLETED`, `FAILED`, `CANCELLED`, `TIMED_OUT` |
| `decision_status` | `APPROVED`, `REJECTED`, or `NO_MATCH` (absent on failure) |
| `value` | the produced value, if any |
| `recovery`, `interruption`, `finalization` | metadata, populated only when applicable |
| `primary_exception`, `secondary_exceptions` | never silently dropped |
| `effects` | proposed side effects; the library never executes them |
| `trace` | populated when tracing is enabled |

`execute()` raises an unrecovered exception to the caller; `try_execute()`
always returns the outcome object. Choose per call site. (Go returns
`(value, error)` tuples; Java/C#/TypeScript throw typed exceptions; Python
raises — all idiomatic.)

## Rules

The core vocabulary is identical across languages:

- **`when(condition, then=action, id=...)`** — match when condition is true.
- **`when_not(condition, then=action, id=...)`** — match when false.
- **`then(stage, id=...)`** — sequential stage after a match; receives
  `(input, previous_output)`.
- **`otherwise(action)`** — dynamic fallback when nothing matched.
- **`default(value)` / `default_if_no_match(value)`** — constant fallback.
- **`with_mode(EvaluationMode.X)`** — `FIRST_MATCH` (default), `ALL_MATCH`,
  `PRIORITY`.
- **`merge(other)`** — splice another flow's rules at the call site.
- **`Flow.from_table(table)`** — build from a `DecisionTable`.

There is deliberately no `unless()` in v0.1: `when_not()` expresses the same
logic unambiguously (see
[when-not-to-use](when-not-to-use.md) and ADR-0001, O5).

## Conditions and actions are pure

Conditions and transformations MUST be pure: no I/O, no mutation, same input
→ same output. Side effects are proposed as `Effect` data and applied only
by your own executor. The library cannot enforce purity for arbitrary
callables — it is your contract to honor (SPEC.md section 5).

## Compile once, execute many

`compile()` validates the flow (unique rule IDs, fallback rules, `then`
placement) and returns a structurally immutable contract that is safe to
share across threads. Each `execute()` gets an isolated context. User
callbacks are not guaranteed thread-safe — that is on you.

## Next steps

- [Cookbook](cookbook.md) — canonical patterns
- [Error handling](error-handling.md) — catch rules
- [Finalization](finalization.md) — guaranteed cleanup
- [Feature catalog](features.md) — all 62 features described
- [SPEC.md](https://github.com/sancy1/flowsemantics/blob/main/SPEC.md) — the
  normative specification
