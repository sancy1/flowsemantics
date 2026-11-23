package flowsemantics

import (
	"strings"
	"testing"
)

func TestWhenMatch(t *testing.T) {
	c, err := NewFlow().When(func(i any) (bool, error) { return true, nil },
		func(i, p any) (any, error) { return "ok", nil }, WithRuleID("r1")).Compile()
	if err != nil { t.Fatal(err) }
	o := c.TryExecute(map[string]any{})
	if o.ExecutionStatus != Completed || o.Value != "ok" {
		t.Fatalf("got %+v", o)
	}
	if o.DecisionStatus == nil || *o.DecisionStatus != Approved { t.Fatal("expected APPROVED") }
}

func TestNoMatch(t *testing.T) {
	c, _ := NewFlow().When(func(i any) (bool, error) { return false, nil },
		func(i, p any) (any, error) { return "x", nil }).Compile()
	o := c.TryExecute(nil)
	if o.DecisionStatus == nil || *o.DecisionStatus != NoMatch { t.Fatal("expected NO_MATCH") }
}

func TestFirstMatchShortCircuit(t *testing.T) {
	second := 0
	c, _ := NewFlow().
		When(func(i any) (bool, error) { return true, nil }, func(i, p any) (any, error) { return "first", nil }).
		When(func(i any) (bool, error) { second++; return true, nil }, func(i, p any) (any, error) { return "second", nil }).
		Compile()
	if c.TryExecute(nil).Value != "first" { t.Fatal("expected first") }
	if second != 0 { t.Fatal("second condition evaluated") }
}

func TestAllMatchLastWins(t *testing.T) {
	c, _ := NewFlow().WithMode(AllMatch).
		When(func(i any) (bool, error) { return true, nil }, func(i, p any) (any, error) { return "a", nil }).
		When(func(i any) (bool, error) { return true, nil }, func(i, p any) (any, error) { return "b", nil }).
		Compile()
	if c.TryExecute(nil).Value != "b" { t.Fatal("expected b") }
}

func TestPriorityOrder(t *testing.T) {
	c, _ := NewFlow().WithMode(Priority).
		When(func(i any) (bool, error) { return true, nil }, func(i, p any) (any, error) { return "low", nil }, WithPriority(1)).
		When(func(i any) (bool, error) { return true, nil }, func(i, p any) (any, error) { return "high", nil }, WithPriority(10)).
		Compile()
	if c.TryExecute(nil).Value != "high" { t.Fatal("expected high") }
}

func TestThenReceivesPrevious(t *testing.T) {
	c, _ := NewFlow().
		When(func(i any) (bool, error) { return true, nil }, func(i, p any) (any, error) { return 1, nil }).
		Then(func(i, prev any) (any, error) { return prev.(int) + 1, nil }).
		Compile()
	if c.TryExecute(nil).Value != 2 { t.Fatal("expected 2") }
}

func TestGuardVetoes(t *testing.T) {
	c, _ := NewFlow().
		When(func(i any) (bool, error) { return true, nil }, func(i, p any) (any, error) { return "x", nil }, WithGuard(func(i any) (bool, error) { return false, nil })).
		Compile()
	if *c.TryExecute(nil).DecisionStatus != NoMatch { t.Fatal("expected NO_MATCH") }
}

func TestTypedCatchRecovers(t *testing.T) {
	c, _ := NewFlow().
		When(func(i any) (bool, error) { return true, nil }, func(i, p any) (any, error) { return nil, NewKindValueError("boom") }).
		Catch("Kind.ValueError", func(i, exc any) (any, error) { return "recovered", nil }).
		Compile()
	o := c.TryExecute(nil)
	if o.ExecutionStatus != Completed || o.Value != "recovered" { t.Fatalf("got %+v", o) }
	if o.Recovery == nil { t.Fatal("expected recovery") }
}

func TestUncaughtIsFailed(t *testing.T) {
	c, _ := NewFlow().
		When(func(i any) (bool, error) { return true, nil }, func(i, p any) (any, error) { return nil, NewKindValueError("x") }).
		Compile()
	if c.TryExecute(nil).ExecutionStatus != Failed { t.Fatal("expected FAILED") }
}

func TestTimeoutBypassesCatch(t *testing.T) {
	c, _ := NewFlow().
		When(func(i any) (bool, error) { return true, nil }, func(i, p any) (any, error) { return nil, NewKindTimeout("t") }).
		CatchAny(func(i, exc any) (any, error) { return "no", nil }).
		Compile()
	o := c.TryExecute(nil)
	if o.ExecutionStatus != TimedOut { t.Fatalf("expected TIMED_OUT, got %s", o.ExecutionStatus) }
	if o.Interruption == nil || o.Interruption.Kind != InterruptedTimedOut { t.Fatal("expected timed_out interruption") }
}

func TestCancelledBypassesCatch(t *testing.T) {
	c, _ := NewFlow().
		When(func(i any) (bool, error) { return true, nil }, func(i, p any) (any, error) { return nil, NewKindCancelled("c") }).
		CatchAny(func(i, exc any) (any, error) { return "no", nil }).
		Compile()
	o := c.TryExecute(nil)
	if o.ExecutionStatus != Cancelled { t.Fatalf("expected CANCELLED, got %s", o.ExecutionStatus) }
}

func TestFinallyOnSuccess(t *testing.T) {
	ran := false
	c, _ := NewFlow().
		When(func(i any) (bool, error) { return true, nil }, func(i, p any) (any, error) { return "v", nil }).
		Finally(func(ctx *FinallyContext) error { ran = true; return nil }).
		Compile()
	o := c.TryExecute(nil)
	if !ran || o.Finalization == nil || !o.Finalization.IsClean { t.Fatal("finalizer did not run clean") }
}

func TestFinallyPreservePrimary(t *testing.T) {
	c, _ := NewFlow().
		When(func(i any) (bool, error) { return true, nil }, func(i, p any) (any, error) { return nil, NewKindValueError("primary") }).
		Finally(func(ctx *FinallyContext) error { return NewKindTimeout("cleanup") }).
		Compile()
	o := c.TryExecute(nil)
	if _, ok := o.PrimaryException.(*KindValueError); !ok { t.Fatal("primary not preserved") }
	if o.Finalization == nil || o.Finalization.IsClean { t.Fatal("expected is_clean false") }
}

func TestFinallyReplacePrimary(t *testing.T) {
	c, _ := NewFlow().WithFinallyPolicy(ReplacePrimary).
		When(func(i any) (bool, error) { return true, nil }, func(i, p any) (any, error) { return nil, NewKindValueError("primary") }).
		Finally(func(ctx *FinallyContext) error { return NewKindTimeout("cleanup") }).
		Compile()
	o := c.TryExecute(nil)
	if _, ok := o.PrimaryException.(*KindTimeout); !ok { t.Fatal("primary not replaced") }
}

func TestEffectsOrder(t *testing.T) {
	c, _ := NewFlow().WithMode(AllMatch).
		When(func(i any) (bool, error) { return true, nil }, func(i, p any) (any, error) { return "a", nil }, WithEffects([]Effect{{Name: "e1"}})).
		When(func(i any) (bool, error) { return true, nil }, func(i, p any) (any, error) { return "b", nil }, WithEffects([]Effect{{Name: "e2"}})).
		Compile()
	o := c.TryExecute(nil)
	if len(o.Effects) != 2 || o.Effects[0].Name != "e1" || o.Effects[1].Name != "e2" {
		t.Fatalf("effects: %+v", o.Effects)
	}
}

func TestTraceEvents(t *testing.T) {
	c, _ := NewFlow().
		When(func(i any) (bool, error) { return false, nil }, func(i, p any) (any, error) { return "x", nil }, WithRuleID("r1")).
		When(func(i any) (bool, error) { return true, nil }, func(i, p any) (any, error) { return "y", nil }, WithRuleID("r2")).
		Compile()
	o := c.TryExecuteWithClock(nil, NewFakeClock(0, 0), true)
	if o.Trace == nil { t.Fatal("no trace") }
	found := map[string]bool{}
	for _, e := range o.Trace.Events { found[string(e.Type)] = true }
	if !found[string(EvRuleSkipped)] || !found[string(EvActionExecuted)] {
		t.Fatalf("missing events: %+v", o.Trace.Events)
	}
}

func TestPortableIR(t *testing.T) {
	ir := map[string]any{
		"spec_version": "0.1.0", "flow_id": "f", "portability": "PORTABLE", "mode": "FirstMatch",
		"rules": []any{map[string]any{
			"rule_id": "r1", "kind": "when",
			"condition": map[string]any{"op": "gt", "args": []any{
				map[string]any{"op": "field", "value": "x"},
				map[string]any{"op": "const", "value": float64(0)},
			}},
			"transform": map[string]any{"op": "const", "value": "pos"},
		}},
		"fallback": map[string]any{"kind": "default_if_no_match", "value": "neg"},
	}
	flow, err := FlowFromIR(ir)
	if err != nil { t.Fatal(err) }
	c, err := flow.Compile()
	if err != nil { t.Fatal(err) }
	if c.TryExecute(map[string]any{"x": float64(5)}).Value != "pos" { t.Fatal("expected pos") }
	if c.TryExecute(map[string]any{"x": float64(-1)}).Value != "neg" { t.Fatal("expected neg") }
}

func TestIRRejectsDuplicateIDs(t *testing.T) {
	rule := map[string]any{"rule_id": "d", "kind": "when",
		"condition": map[string]any{"op": "const", "value": true},
		"transform": map[string]any{"op": "const", "value": float64(1)}}
	_, err := PortableFlowFromDict(map[string]any{
		"spec_version": "0.1.0", "flow_id": "f", "portability": "PORTABLE", "mode": "FirstMatch",
		"rules": []any{rule, rule},
	})
	if err == nil { t.Fatal("expected duplicate rejection") }
}

func TestIRRejectsDeepNesting(t *testing.T) {
	expr := map[string]any{"op": "const", "value": true}
	for i := 0; i < MaxExprDepth+2; i++ {
		expr = map[string]any{"op": "not", "args": []any{expr}}
	}
	_, err := PortableFlowFromDict(map[string]any{
		"spec_version": "0.1.0", "flow_id": "f", "portability": "PORTABLE", "mode": "FirstMatch",
		"rules": []any{map[string]any{"rule_id": "r", "kind": "when", "condition": expr,
			"transform": map[string]any{"op": "const", "value": float64(1)}}},
	})
	if err == nil { t.Fatal("expected depth rejection") }
}

func TestSimulateSkipsHooks(t *testing.T) {
	hooked := 0
	c, _ := NewFlow().
		When(func(i any) (bool, error) { return true, nil }, func(i, p any) (any, error) { return "v", nil }).
		OnMatch(func(i any, id string, v any) { hooked++ }).
		Compile()
	c.Simulate(nil)
	if hooked != 0 { t.Fatal("simulate invoked hook") }
}

func TestContractVersionStable(t *testing.T) {
c1, _ := NewFlow().When(func(i any) (bool, error) { return true, nil },
func(i, p any) (any, error) { return "x", nil }, WithRuleID("r1")).Compile()
c2, _ := NewFlow().When(func(i any) (bool, error) { return true, nil },
func(i, p any) (any, error) { return "x", nil }, WithRuleID("r1")).Compile()
if c1.ContractVersion == "" || c1.ContractVersion != c2.ContractVersion {
t.Fatal("contract version unstable")
}
c3, _ := NewFlow().When(func(i any) (bool, error) { return true, nil },
func(i, p any) (any, error) { return "y", nil }, WithRuleID("r2")).Compile()
if c1.ContractVersion == c3.ContractVersion { t.Fatal("different contracts share version") }
}

func TestValidate(t *testing.T) {
c, _ := NewFlow().Compile()
issues := c.Validate()
if len(issues) != 1 || issues[0].Code != "empty_flow" { t.Fatalf("expected empty_flow, got %+v", issues) }
}

func TestExplain(t *testing.T) {
c, _ := NewFlow().When(func(i any) (bool, error) { return false, nil },
func(i, p any) (any, error) { return "x", nil }, WithRuleID("r1")).Compile()
o := c.TryExecuteWithClock(nil, NewFakeClock(0, 0), true)
s := c.Explain(o.Trace)
if !strings.Contains(s, "FlowContract") || !strings.Contains(s, "rule_skipped") {
t.Fatalf("bad explain: %s", s)
}
}

func TestReplaySimulation(t *testing.T) {
c, _ := NewFlow().When(func(i any) (bool, error) { return true, nil },
func(i, p any) (any, error) { return "v", nil }).Compile()
rec := Record(c, nil, NewFakeClock(0, 0))
res, err := Replay(rec, c, ReplaySimulation, nil, nil, false)
if err != nil { t.Fatal(err) }
if res.Equivalent == nil || !*res.Equivalent { t.Fatal("expected equivalent") }
}

func TestReplayHistorical(t *testing.T) {
c, _ := NewFlow().When(func(i any) (bool, error) { return true, nil },
func(i, p any) (any, error) { return "v", nil }).Compile()
rec := Record(c, nil, NewFakeClock(0, 0))
res, _ := Replay(rec, c, ReplayHistorical, nil, nil, false)
if res.Outcome != rec.Outcome { t.Fatal("historical should return recorded outcome") }
}

func TestReplayFailsClosedOnVersionMismatch(t *testing.T) {
c, _ := NewFlow().When(func(i any) (bool, error) { return true, nil },
func(i, p any) (any, error) { return "v", nil }).Compile()
rec := Record(c, nil, NewFakeClock(0, 0))
rec.ContractVersion = "tampered"
_, err := Replay(rec, c, ReplaySimulation, nil, nil, false)
if err == nil { t.Fatal("expected fail-closed") }
}

func TestReplayIntegrity(t *testing.T) {
c, _ := NewFlow().When(func(i any) (bool, error) { return true, nil },
func(i, p any) (any, error) { return "v", nil }).Compile()
rec := Record(c, nil, NewFakeClock(0, 0))
signed := Sign(rec, []byte("key"))
if _, err := Replay(signed, c, ReplaySimulation, []byte("key"), nil, false); err != nil {
t.Fatal(err)
}
if _, err := Replay(signed, c, ReplaySimulation, []byte("wrong"), nil, false); err == nil {
t.Fatal("expected integrity failure")
}
if _, err := Replay(signed, c, ReplaySimulation, nil, nil, false); err == nil {
t.Fatal("expected key-required failure")
}
}

func TestReplayEffectsRequiresAuth(t *testing.T) {
c, _ := NewFlow().When(func(i any) (bool, error) { return true, nil },
func(i, p any) (any, error) { return "v", nil }, WithEffects([]Effect{{Name: "e1"}})).Compile()
rec := Record(c, nil, NewFakeClock(0, 0))
if _, err := Replay(rec, c, ReplayEffects, nil, nil, false); err == nil {
t.Fatal("expected authorization failure")
}
applied := 0
res, err := Replay(rec, c, ReplayEffects, nil, func(e Effect) { applied++ }, true)
if err != nil || res.EffectsApplied != 1 || applied != 1 { t.Fatalf("effects: %+v %v", res, err) }
}

func TestShadow(t *testing.T) {
cur, _ := NewFlow().When(func(i any) (bool, error) { return true, nil },
func(i, p any) (any, error) { return "a", nil }).Compile()
cand, _ := NewFlow().When(func(i any) (bool, error) { return true, nil },
func(i, p any) (any, error) { return "b", nil }).Compile()
rep := Shadow(cur, cand, []any{nil, nil})
if rep.Total != 2 || rep.Differences != 2 { t.Fatalf("shadow: %+v", rep) }
if len(rep.Entries[0].DifferingFields) == 0 { t.Fatal("expected differing fields") }
}

func TestToIRNativeRejected(t *testing.T) {
c, _ := NewFlow().When(func(i any) (bool, error) { return true, nil },
func(i, p any) (any, error) { return "x", nil }).Compile()
if _, err := c.ToIR(); err == nil { t.Fatal("expected NATIVE rejection") }
}

func TestMerge(t *testing.T) {
f1 := NewFlow().WithMode(FirstMatch)
f1.When(func(i any) (bool, error) { return true, nil }, func(i, p any) (any, error) { return "a", nil }, WithRuleID("r1"))
f2 := NewFlow().WithMode(FirstMatch)
f2.When(func(i any) (bool, error) { return false, nil }, func(i, p any) (any, error) { return "b", nil }, WithRuleID("r2"))
f2.DefaultIfNoMatch("fb")
merged, err := f1.Merge(f2)
if err != nil { t.Fatal(err) }
c, _ := merged.Compile()
o := c.TryExecute(nil)
if o.Value != "a" { t.Fatalf("got %v", o.Value) }
// mode mismatch
f3 := NewFlow().WithMode(AllMatch)
if _, err := f1.Merge(f3); err == nil { t.Fatal("expected mode mismatch error") }
// dup id
f4 := NewFlow().WithMode(FirstMatch)
f4.When(func(i any) (bool, error) { return true, nil }, func(i, p any) (any, error) { return "x", nil }, WithRuleID("r1"))
if _, err := f1.Merge(f4); err == nil { t.Fatal("expected dup id error") }
}

func TestDecisionTable(t *testing.T) {
table := &DecisionTable{
Policy: HitFirst,
Rows: []DecisionTableRow{
{ID: "big", Conditions: []ConditionFn{func(i any) (bool, error) { return true, nil }}, Action: func(i, p any) (any, error) { return "big", nil }},
{ID: "small", Conditions: []ConditionFn{func(i any) (bool, error) { return false, nil }}, Action: func(i, p any) (any, error) { return "small", nil }},
},
}
f, err := TableToFlow(table)
if err != nil { t.Fatal(err) }
c, _ := f.Compile()
o := c.TryExecute(nil)
if o.Value != "big" { t.Fatalf("got %v", o.Value) }
if _, err := TableToFlow(&DecisionTable{Policy: "BOGUS", Rows: table.Rows}); err == nil { t.Fatal("expected bad policy error") }
}

func TestEffectiveDates(t *testing.T) {
from, _ := ParseEffective("2026-01-01T00:00:00Z")
until, _ := ParseEffective("2026-06-01T00:00:00Z")
c, err := NewFlow().When(func(i any) (bool, error) { return true, nil },
func(i, p any) (any, error) { return "v", nil },
WithRuleID("r1"), WithEffectiveFrom(*from), WithEffectiveUntil(*until)).Compile()
if err != nil { t.Fatal(err) }
// before window
o1 := c.TryExecuteWithClock(nil, NewFakeClock(0, 0), true)
if o1.DecisionStatus == nil || *o1.DecisionStatus != NoMatch { t.Fatal("expected NO_MATCH before window") }
// inside window
mid := (*from + *until) / 2
o2 := c.TryExecuteWithClock(nil, NewFakeClock(mid, 0), true)
if o2.Value != "v" { t.Fatalf("expected match inside window, got %v", o2.Value) }
// after window
o3 := c.TryExecuteWithClock(nil, NewFakeClock(*until+1, 0), true)
if o3.DecisionStatus == nil || *o3.DecisionStatus != NoMatch { t.Fatal("expected NO_MATCH after window") }
// inverted window rejected
_, err = NewFlow().When(func(i any) (bool, error) { return true, nil },
func(i, p any) (any, error) { return "v", nil },
WithEffectiveFrom(*until), WithEffectiveUntil(*from)).Compile()
if err == nil { t.Fatal("expected inverted window error") }
}

func TestCancelCheck(t *testing.T) {
cancelled := false
c, _ := NewFlow().WithCancelCheck(func() bool { return cancelled }).
When(func(i any) (bool, error) { return true, nil }, func(i, p any) (any, error) { return "v", nil }).Compile()
cancelled = true
o := c.TryExecute(nil)
if o.ExecutionStatus != Cancelled { t.Fatalf("expected CANCELLED, got %s", o.ExecutionStatus) }
if o.Interruption == nil || o.Interruption.Kind != InterruptedCancelled { t.Fatal("expected cancelled interruption") }
}

func TestSimulateBatch(t *testing.T) {
c, _ := NewFlow().When(func(i any) (bool, error) { return true, nil },
func(i, p any) (any, error) { return "v", nil }).Compile()
rep := c.SimulateBatch([]any{nil, nil, nil})
if rep.Total != 3 || rep.ByDecision["APPROVED"] != 3 { t.Fatalf("batch: %+v", rep) }
}

func TestValidateDepth(t *testing.T) {
// gap warning
c1, _ := NewFlow().When(func(i any) (bool, error) { return true, nil },
func(i, p any) (any, error) { return "v", nil }).Compile()
issues := c1.Validate()
found := false
for _, i := range issues { if i.Code == "possible_gap" { found = true } }
if !found { t.Fatal("expected possible_gap warning") }
// unreachable via portable const-true
ir1 := map[string]any{"spec_version":"0.1.0","flow_id":"f","portability":"PORTABLE","mode":"FirstMatch","rules":[]any{map[string]any{"rule_id":"a","kind":"when","condition":map[string]any{"op":"const","value":true},"transform":map[string]any{"op":"const","value":1}},map[string]any{"rule_id":"b","kind":"when","condition":map[string]any{"op":"const","value":false},"transform":map[string]any{"op":"const","value":2}}}}
f2, err := FlowFromIR(ir1)
if err != nil { t.Fatal(err) }
c2, _ := f2.Compile()
found = false
for _, i := range c2.Validate() { if i.Code == "unreachable_rule" && i.RuleID == "b" { found = true } }
if !found { t.Fatal("expected unreachable_rule warning for b") }
// overlap
ir2 := map[string]any{"spec_version":"0.1.0","flow_id":"f","portability":"PORTABLE","mode":"FirstMatch","rules":[]any{map[string]any{"rule_id":"a","kind":"when","condition":map[string]any{"op":"const","value":true},"transform":map[string]any{"op":"const","value":1}},map[string]any{"rule_id":"b","kind":"when","condition":map[string]any{"op":"const","value":true},"transform":map[string]any{"op":"const","value":2}}}}
f3, _ := FlowFromIR(ir2)
c3, _ := f3.Compile()
found = false
for _, i := range c3.Validate() { if i.Code == "overlapping_rules" { found = true } }
if !found { t.Fatal("expected overlapping_rules warning") }
}

func TestPortabilityReport(t *testing.T) {
c, _ := NewFlow().When(func(i any) (bool, error) { return true, nil },
func(i, p any) (any, error) { return "v", nil }).Compile()
class, offenders := c.Portability()
if class != "NATIVE" || len(offenders) == 0 { t.Fatal("expected NATIVE with offenders") }
}

func TestExecutePropagates(t *testing.T) {
c, _ := NewFlow().When(func(any) (bool, error) { return true, nil },
func(any, any) (any, error) { return nil, NewKindValueError("boom") }).Compile()
_, err := c.Execute(nil)
if err == nil { t.Fatal("expected error") }
o := c.TryExecute(nil)
if o.ExecutionStatus != Failed { t.Fatalf("got %s", o.ExecutionStatus) }
}

func TestWithFlowIDAndClock(t *testing.T) {
fc := NewFakeClock(1000, 5)
c, _ := NewFlow().WithFlowID("my-flow").WithClock(fc).
WhenExpr(PConst(true), PConst("v"), WithPRuleID("p1")).Compile()
ir, err := c.ToIR()
if err != nil { t.Fatal(err) }
if ir.FlowID != "my-flow" { t.Fatalf("flow_id=%s", ir.FlowID) }
if ir.ContractVersion == "" { t.Fatal("missing contract_version") }
if c.Clock() != fc { t.Fatal("clock not injected") }
}

func TestDiagnosticHook(t *testing.T) {
c, _ := NewFlow().WithTrace(func(e *TraceEvent) map[string]any {
return map[string]any{"tag": string(e.Type)}
}).When(func(any) (bool, error) { return true, nil },
func(any, any) (any, error) { return "v", nil }).Compile()
o := c.TryExecute(nil)
if o.Trace == nil || len(o.Trace.Events) == 0 { t.Fatal("no trace") }
if o.Trace.Events[0].Diagnostics["tag"] == nil { t.Fatal("no diagnostics") }
if o.Trace.Events[0].ContractVersion == "" { t.Fatal("no contract_version on event") }
}

func TestPExprBuildersAndDict(t *testing.T) {
e := PAnd(PGt(PField("total"), PConst(100)), PNot(PIsNull(PField("sku"))))
d := ExprToDict(e)
back, err := ExprFromDict(d)
if err != nil { t.Fatal(err) }
if back.Op != "and" { t.Fatal("round trip failed") }
v, err := EvalExpr(PNotIn(PField("s"), []any{"a", "b"}), map[string]any{"s": "c"})
if err != nil || v != true { t.Fatalf("eval=%v err=%v", v, err) }
if !PExprOps["field"] { t.Fatal("PExprOps missing field") }
}

func TestPortableFlowJSONRoundTrip(t *testing.T) {
c, _ := NewFlow().WithFlowID("f").
WhenExpr(PEq(PField("x"), PConst(1)), PConst("one"), WithPRuleID("r1")).Compile()
ir, _ := c.ToIR()
js, err := PortableFlowToJSON(ir)
if err != nil { t.Fatal(err) }
back, err := PortableFlowFromJSON(js)
if err != nil { t.Fatal(err) }
if back.FlowID != "f" || len(back.Rules) != 1 { t.Fatalf("round trip: %+v", back) }
irJSON, err := c.ToIRJSON()
if err != nil { t.Fatal(err) }
if _, err := PortableFlowFromJSON(irJSON); err != nil { t.Fatal(err) }
}

func TestMergeContract(t *testing.T) {
inner, _ := NewFlow().When(func(any) (bool, error) { return false, nil },
func(any, any) (any, error) { return "inner", nil }, WithRuleID("i1")).
DefaultIfNoMatch("ifb").Compile()
outer := NewFlow().When(func(any) (bool, error) { return true, nil },
func(any, any) (any, error) { return "outer", nil }, WithRuleID("o1")).
DefaultIfNoMatch("ofb")
if _, err := outer.MergeContract(inner); err != nil { t.Fatal(err) }
oc, _ := outer.Compile()
if oc.TryExecute(nil).Value != "outer" { t.Fatal("merge failed") }
}

func TestSimulateWithClockAndShadowClock(t *testing.T) {
clk := NewFakeClock(100, 0)
c, _ := NewFlow().When(func(any) (bool, error) { return true, nil },
func(any, any) (any, error) { return "v", nil }).Compile()
o := c.SimulateWithClock(nil, clk)
if o.Value != "v" { t.Fatal("simulate failed") }
c2, _ := NewFlow().When(func(any) (bool, error) { return true, nil },
func(any, any) (any, error) { return "w", nil }).Compile()
rep := Shadow(c, c2, []any{nil}, clk)
if rep.Differences != 1 { t.Fatalf("differences=%d", rep.Differences) }
if rep.Entries[0].DifferingFields[0] != "value" { t.Fatal("wrong fields") }
}

func TestFlowContext(t *testing.T) {
clk := NewFakeClock(0, 0)
ctx := NewFlowContext(map[string]any{"a": 1}, clk)
if ctx.Input == nil || ctx.Clock != clk || ctx.State == nil { t.Fatal("bad context") }
}

func TestReplayUsesRecordedClock(t *testing.T) {
clk := NewFakeClock(5000, 3)
c, _ := NewFlow().WithClock(clk).
When(func(any) (bool, error) { return true, nil },
func(any, any) (any, error) { return "v", nil }).Compile()
rec := Record(c, nil, clk)
res, err := Replay(rec, c, ReplayDecision, nil, nil, false)
if err != nil { t.Fatal(err) }
if res.Equivalent == nil || !*res.Equivalent { t.Fatal("not equivalent") }
}
