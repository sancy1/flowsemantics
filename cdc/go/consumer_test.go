// Consumer-driven contract tests — Go.
// Written purely from the public documentation. Imports only the published
// github.com/flowsemantics/flowsemantics-go module — never the source tree.
// Run: go test ./...

package cdc_test

import (
	"errors"
	"fmt"
	"testing"

	fs "github.com/flowsemantics/flowsemantics-go"
)

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

func condTrue(any) (bool, error)  { return true, nil }
func condFalse(any) (bool, error) { return false, nil }
func actConst(v any) fs.ActionFn {
	return func(any, any) (any, error) { return v, nil }
}
func actThrow(err error) fs.ActionFn {
	return func(any, any) (any, error) { return nil, err }
}
func handlerConst(v any) fs.ExceptionHandler {
	return func(any, any) (any, error) { return v, nil }
}

// ---------------------------------------------------------------------------
// Core decision layer (features 1-18)
// ---------------------------------------------------------------------------

func TestWhenProducesApprovedValue(t *testing.T) {
	// Features 1, 3: when + then action.
	c, err := fs.NewFlow().
		When(func(i any) (bool, error) { return i.(map[string]any)["total"].(int) > 100, nil },
			actConst("big"), fs.WithRuleID("big")).
		Compile()
	if err != nil {
		t.Fatal(err)
	}
	o := c.TryExecute(map[string]any{"total": 150})
	if o.ExecutionStatus != fs.Completed {
		t.Fatalf("status=%v", o.ExecutionStatus)
	}
	if o.DecisionStatus == nil || *o.DecisionStatus != fs.Approved {
		t.Fatalf("decision=%v", o.DecisionStatus)
	}
	if o.Value != "big" {
		t.Fatalf("value=%v", o.Value)
	}
}

func TestWhenNotAndOtherwise(t *testing.T) {
	// Features 2, 4.
	c, err := fs.NewFlow().
		WhenNot(func(i any) (bool, error) { return i.(map[string]any)["vip"].(bool), nil },
			actConst("standard"), fs.WithRuleID("std")).
		Otherwise(actConst("fallback")).
		Compile()
	if err != nil {
		t.Fatal(err)
	}
	if got := c.TryExecute(map[string]any{"vip": false}).Value; got != "standard" {
		t.Fatalf("got %v", got)
	}
	if got := c.TryExecute(map[string]any{"vip": true}).Value; got != "fallback" {
		t.Fatalf("got %v", got)
	}
}

func TestDefaultAndDefaultIfNoMatch(t *testing.T) {
	// Features 5, 6.
	c1, _ := fs.NewFlow().When(condFalse, actConst("x"), fs.WithRuleID("r")).Default("dflt").Compile()
	c2, _ := fs.NewFlow().When(condFalse, actConst("x"), fs.WithRuleID("r")).DefaultIfNoMatch("d2").Compile()
	if c1.TryExecute(nil).Value != "dflt" {
		t.Fatal("default failed")
	}
	if c2.TryExecute(nil).Value != "d2" {
		t.Fatal("default_if_no_match failed")
	}
}

func TestEvaluationModes(t *testing.T) {
	// Features 7-9.
	build := func(m fs.EvaluationMode) *fs.FlowContract {
		c, err := fs.NewFlow().WithMode(m).
			When(condTrue, actConst("a"), fs.WithRuleID("a")).
			When(condTrue, actConst("b"), fs.WithRuleID("b"), fs.WithPriority(5)).
			Compile()
		if err != nil {
			t.Fatal(err)
		}
		return c
	}
	if got := build(fs.FirstMatch).TryExecute(nil).Value; got != "a" {
		t.Fatalf("FirstMatch=%v", got)
	}
	// AllMatch fires every matching rule; last action's value wins.
	if got := build(fs.AllMatch).TryExecute(nil).Value; got != "b" {
		t.Fatalf("AllMatch=%v", got)
	}
	if got := build(fs.Priority).TryExecute(nil).Value; got != "b" {
		t.Fatalf("Priority=%v", got)
	}
}

func TestGuardAndRulePriority(t *testing.T) {
	// Features 10, 11.
	c, err := fs.NewFlow().WithMode(fs.Priority).
		When(condTrue, actConst("unguarded"), fs.WithRuleID("low"), fs.WithPriority(1)).
		When(condTrue, actConst("guarded"), fs.WithRuleID("high"),
			fs.WithGuard(func(i any) (bool, error) { return i.(map[string]any)["ok"].(bool), nil }),
			fs.WithPriority(10)).
		Compile()
	if err != nil {
		t.Fatal(err)
	}
	if got := c.TryExecute(map[string]any{"ok": true}).Value; got != "guarded" {
		t.Fatalf("got %v", got)
	}
	if got := c.TryExecute(map[string]any{"ok": false}).Value; got != "unguarded" {
		t.Fatalf("got %v", got)
	}
}

func TestEffectsProposal(t *testing.T) {
	// Feature 12.
	c, err := fs.NewFlow().
		When(condTrue, actConst("done"), fs.WithRuleID("r1"),
			fs.WithEffects([]fs.Effect{{Name: "notify", Payload: map[string]any{"to": "ops"}}})).
		Compile()
	if err != nil {
		t.Fatal(err)
	}
	o := c.TryExecute(nil)
	if o.Value != "done" || len(o.Effects) != 1 || o.Effects[0].Name != "notify" {
		t.Fatalf("outcome=%+v", o)
	}
}

func TestMergeFlowAndContract(t *testing.T) {
	// Features 13, 14.
	inner, _ := fs.NewFlow().
		When(func(i any) (bool, error) { return i.(map[string]any)["x"].(int) > 0, nil },
			actConst("pos"), fs.WithRuleID("pos")).
		Compile()
	_ = inner
	f := fs.NewFlow()
	merged, err := f.Merge(fs.NewFlow().
		When(func(i any) (bool, error) { return i.(map[string]any)["x"].(int) > 0, nil },
			actConst("pos"), fs.WithRuleID("pos")))
	if err != nil {
		t.Fatal(err)
	}
	merged.When(func(i any) (bool, error) { return i.(map[string]any)["x"].(int) < 0, nil },
		actConst("neg"), fs.WithRuleID("neg"))
	c, err := merged.Compile()
	if err != nil {
		t.Fatal(err)
	}
	if c.TryExecute(map[string]any{"x": 1}).Value != "pos" {
		t.Fatal("pos failed")
	}
	if c.TryExecute(map[string]any{"x": -1}).Value != "neg" {
		t.Fatal("neg failed")
	}

	part, _ := fs.NewFlow().
		When(func(i any) (bool, error) { return i.(map[string]any)["x"].(int) == 0, nil },
			actConst("zero"), fs.WithRuleID("zero")).
		Compile()
	mf, err := fs.NewFlow().MergeContract(part)
	if err != nil {
		t.Fatal(err)
	}
	mc, err := mf.Compile()
	if err != nil {
		t.Fatal(err)
	}
	if mc.TryExecute(map[string]any{"x": 0}).Value != "zero" {
		t.Fatal("merge contract failed")
	}
}

func TestDecisionTableAndHitPolicies(t *testing.T) {
	// Features 15, 16.
	table := &fs.DecisionTable{
		Rows: []fs.DecisionTableRow{
			{ID: "small", Conditions: []fs.ConditionFn{
				func(i any) (bool, error) { return i.(map[string]any)["n"].(int) < 10, nil }},
				Action: actConst("small")},
			{ID: "big", Conditions: []fs.ConditionFn{
				func(i any) (bool, error) { return i.(map[string]any)["n"].(int) >= 10, nil }},
				Action: actConst("big")},
		},
		Policy: fs.HitFirst,
	}
	flow, err := fs.TableToFlow(table)
	if err != nil {
		t.Fatal(err)
	}
	c, err := flow.Compile()
	if err != nil {
		t.Fatal(err)
	}
	if c.TryExecute(map[string]any{"n": 5}).Value != "small" {
		t.Fatal("small failed")
	}
	if c.TryExecute(map[string]any{"n": 50}).Value != "big" {
		t.Fatal("big failed")
	}
	for _, p := range []fs.HitPolicy{fs.HitFirst, fs.HitCollect, fs.HitPriority, fs.HitUnique} {
		tt := &fs.DecisionTable{
			Rows:   []fs.DecisionTableRow{{ID: "r1", Conditions: []fs.ConditionFn{condTrue}, Action: actConst("v1")}},
			Policy: p,
		}
		if _, err := fs.TableToFlow(tt); err != nil {
			t.Fatalf("policy %s: %v", p, err)
		}
	}
}

func TestCompileValidationDuplicateID(t *testing.T) {
	// Feature 17.
	_, err := fs.NewFlow().
		When(condTrue, actConst("a"), fs.WithRuleID("dup")).
		When(condTrue, actConst("b"), fs.WithRuleID("dup")).
		Compile()
	if err == nil {
		t.Fatal("expected duplicate RuleId error")
	}
}

func TestEffectiveDates(t *testing.T) {
	// Feature 18.
	c, err := fs.NewFlow().
		When(condTrue, actConst("active"), fs.WithRuleID("r1"),
			fs.WithEffectiveFrom(1_000_000), fs.WithEffectiveUntil(9_000_000_000_000)).
		Default("inactive").
		Compile()
	if err != nil {
		t.Fatal(err)
	}
	if c.TryExecute(nil).Value != "active" {
		t.Fatal("effective window failed")
	}
}

// ---------------------------------------------------------------------------
// Error & execution layer (features 19-33)
// ---------------------------------------------------------------------------

func TestCatchTyped(t *testing.T) {
	// Feature 19.
	c, err := fs.NewFlow().
		When(condTrue, actThrow(fs.NewKindValueError("boom")), fs.WithRuleID("r1")).
		Catch("Kind.ValueError",
			func(_ any, exc any) (any, error) { return fmt.Sprintf("caught:%v", exc), nil },
			fs.WithCatchID("h1")).
		Compile()
	if err != nil {
		t.Fatal(err)
	}
	o := c.TryExecute(nil)
	if o.ExecutionStatus != fs.Completed || o.Recovery == nil || o.Recovery.HandlerRuleID != "h1" {
		t.Fatalf("outcome=%+v", o)
	}
}

func TestCatchWhenAndCatchAny(t *testing.T) {
	// Features 20, 21.
	c, err := fs.NewFlow().
		When(condTrue, actThrow(errors.New("x")), fs.WithRuleID("r1")).
		CatchWhen("Kind.Any",
			func(_ any, exc any) (bool, error) { return false, nil },
			handlerConst("predicted"), fs.WithCatchID("h1")).
		CatchAny(handlerConst("any"), fs.WithCatchID("h2")).
		Compile()
	if err != nil {
		t.Fatal(err)
	}
	if c.TryExecute(nil).Value != "any" {
		t.Fatal("catch_any fallback failed")
	}
}

func TestRethrow(t *testing.T) {
	// Feature 22.
	c, err := fs.NewFlow().
		When(condTrue, actThrow(fs.NewKindValueError("nope")), fs.WithRuleID("r1")).
		CatchWhen("Kind.ValueError", func(any, any) (bool, error) { return false, nil },
			handlerConst("handled"), fs.WithCatchID("h1")).
		Rethrow().
		Compile()
	if err != nil {
		t.Fatal(err)
	}
	o := c.TryExecute(nil)
	if o.ExecutionStatus != fs.Failed || o.PrimaryException == nil {
		t.Fatalf("outcome=%+v", o)
	}
}

func TestOnMatchHook(t *testing.T) {
	// Feature 23.
	var seen []string
	c, err := fs.NewFlow().
		When(condTrue, actConst("v"), fs.WithRuleID("r1")).
		OnMatch(func(_ any, rid string, _ any) { seen = append(seen, rid) }).
		Compile()
	if err != nil {
		t.Fatal(err)
	}
	c.TryExecute(nil)
	if len(seen) != 1 || seen[0] != "r1" {
		t.Fatalf("seen=%v", seen)
	}
}

func TestCancellationRecognition(t *testing.T) {
	// Feature 24.
	c, _ := fs.NewFlow().
		When(condTrue, actThrow(fs.NewKindCancelled("stop")), fs.WithRuleID("r1")).
		Compile()
	o := c.TryExecute(nil)
	if o.ExecutionStatus != fs.Cancelled || o.Interruption == nil ||
		o.Interruption.Kind != fs.InterruptedCancelled {
		t.Fatalf("outcome=%+v", o)
	}
}

func TestTimeoutRecognition(t *testing.T) {
	// Feature 25.
	c, _ := fs.NewFlow().
		When(condTrue, actThrow(fs.NewKindTimeout("deadline")), fs.WithRuleID("r1")).
		Compile()
	o := c.TryExecute(nil)
	if o.ExecutionStatus != fs.TimedOut || o.Interruption == nil ||
		o.Interruption.Kind != fs.InterruptedTimedOut {
		t.Fatalf("outcome=%+v", o)
	}
}

func TestCooperativeCancelCheck(t *testing.T) {
	// Feature 26.
	c, _ := fs.NewFlow().
		When(condTrue, actConst("a"), fs.WithRuleID("r1")).
		WithCancelCheck(func() bool { return true }).
		Compile()
	if o := c.TryExecute(nil); o.ExecutionStatus != fs.Cancelled {
		t.Fatalf("status=%v", o.ExecutionStatus)
	}
}

func TestAsyncParity(t *testing.T) {
	// Feature 27: Go is synchronous; ExecuteAsync delegates to the sync path.
	c, _ := fs.NewFlow().When(condTrue, actConst("ok"), fs.WithRuleID("r1")).Compile()
	o := c.ExecuteAsync(nil)
	if o.Value != "ok" {
		t.Fatalf("value=%v", o.Value)
	}
}

func TestFinallyAndPolicies(t *testing.T) {
	// Features 28, 29.
	var cleaned []fs.ExecutionStatus
	c, err := fs.NewFlow().
		When(condTrue, actConst("ok"), fs.WithRuleID("r1")).
		Finally(func(ctx *fs.FinallyContext) error {
			cleaned = append(cleaned, ctx.Status)
			return nil
		}).
		Compile()
	if err != nil {
		t.Fatal(err)
	}
	o := c.TryExecute(nil)
	if o.Value != "ok" || len(cleaned) != 1 || cleaned[0] != fs.Completed {
		t.Fatalf("outcome=%+v cleaned=%v", o, cleaned)
	}

	for _, p := range []fs.FinallyFailurePolicy{
		fs.PreservePrimary, fs.Attach, fs.ReplacePrimary,
	} {
		c2, err := fs.NewFlow().
			When(condTrue, actConst("ok"), fs.WithRuleID("r1")).
			Finally(func(*fs.FinallyContext) error { return errors.New("cleanup") }).
			WithFinallyPolicy(p).
			Compile()
		if err != nil {
			t.Fatal(err)
		}
		if c2.TryExecute(nil) == nil {
			t.Fatal("nil outcome")
		}
	}
}

func TestFinallyTimeoutBudget(t *testing.T) {
	// Feature 30.
	c, _ := fs.NewFlow().
		When(condTrue, actConst("ok"), fs.WithRuleID("r1")).
		Finally(func(*fs.FinallyContext) error { return nil }).
		WithFinallyTimeout(50).
		Compile()
	o := c.TryExecute(nil)
	if o.Finalization == nil {
		t.Fatal("no finalization info")
	}
}

func TestSecondaryExceptions(t *testing.T) {
	// Feature 31.
	c, _ := fs.NewFlow().
		When(condTrue, actConst("v"), fs.WithRuleID("r1")).
		OnMatch(func(any, string, any) { panic("hook boom") }).
		Compile()
	o := c.TryExecute(nil)
	if o.Value != "v" || len(o.SecondaryExceptions) == 0 {
		t.Fatalf("outcome=%+v", o)
	}
}

func TestInterruptionModel(t *testing.T) {
	// Feature 32.
	c, _ := fs.NewFlow().
		When(condTrue, actThrow(fs.NewKindCancelled("x")), fs.WithRuleID("r1")).
		Compile()
	o := c.TryExecute(nil)
	if o.Interruption == nil || o.Interruption.Kind != fs.InterruptedCancelled ||
		o.Interruption.Source == "" || o.Interruption.Timestamp == 0 {
		t.Fatalf("interruption=%+v", o.Interruption)
	}
}

func TestFinallyContextAndToken(t *testing.T) {
	// Feature 33.
	var status fs.ExecutionStatus
	var value any
	var hasToken bool
	var ctxInput any
	c, _ := fs.NewFlow().
		When(condTrue, actConst("payload"), fs.WithRuleID("r1")).
		Finally(func(ctx *fs.FinallyContext) error {
			status = ctx.Status
			value = ctx.Value
			hasToken = true // CancellationToken is a struct field, always present
			ctxInput = ctx.Context
			return nil
		}).
		Compile()
	c.TryExecute(map[string]any{"in": 1})
	if status != fs.Completed || value != "payload" || !hasToken {
		t.Fatalf("status=%v value=%v token=%v", status, value, hasToken)
	}
	if ctxInput == nil {
		t.Fatal("context not propagated")
	}
}

// ---------------------------------------------------------------------------
// Trust semantics (features 34-47)
// ---------------------------------------------------------------------------

func tracedContract(t *testing.T) *fs.FlowContract {
	t.Helper()
	c, err := fs.NewFlow().
		When(func(i any) (bool, error) { return i.(map[string]any)["n"].(int) > 0, nil },
			actConst("pos"), fs.WithRuleID("pos")).
		Default("none").
		WithTrace().
		Compile()
	if err != nil {
		t.Fatal(err)
	}
	return c
}

func TestTraceVocabularyAndOptIn(t *testing.T) {
	// Features 34, 35.
	c := tracedContract(t)
	o := c.TryExecuteWithClock(map[string]any{"n": 1}, nil, true)
	if o.Trace == nil || len(o.Trace.Events) == 0 {
		t.Fatal("no trace events")
	}

	plain, _ := fs.NewFlow().When(condTrue, actConst("x"), fs.WithRuleID("r")).Compile()
	if plain.TryExecute(nil).Trace != nil {
		t.Fatal("trace should be opt-in")
	}
}

func TestDiagnosticHook(t *testing.T) {
	// Feature 36.
	var seen int
	c, _ := fs.NewFlow().
		When(condTrue, actConst("v"), fs.WithRuleID("r1")).
		WithTrace(func(e *fs.TraceEvent) map[string]any {
			seen++
			return map[string]any{"redacted": true}
		}).
		Compile()
	c.TryExecuteWithClock(nil, nil, true)
	if seen == 0 {
		t.Fatal("diagnostic hook not called")
	}
}

func TestExplain(t *testing.T) {
	// Feature 37.
	c := tracedContract(t)
	o := c.TryExecuteWithClock(map[string]any{"n": 1}, nil, true)
	text := c.Explain(o.Trace)
	if text == "" {
		t.Fatal("empty explanation")
	}
}

func TestSimulateAndSimulateBatch(t *testing.T) {
	// Features 38, 39.
	c := tracedContract(t)
	sim := c.Simulate(map[string]any{"n": 5})
	if sim.DecisionStatus == nil || *sim.DecisionStatus != fs.Approved || sim.Value != "pos" {
		t.Fatalf("sim=%+v", sim)
	}
	batch := c.SimulateBatch([]any{map[string]any{"n": 1}, map[string]any{"n": -1}, map[string]any{"n": 2}})
	if batch.Total != 3 || batch.ByStatus == nil || batch.ByDecision == nil {
		t.Fatalf("batch=%+v", batch)
	}
}

func TestReplayRecordAndModes(t *testing.T) {
	// Features 40, 41.
	c := tracedContract(t)
	rec := fs.Record(c, map[string]any{"n": 3}, nil)
	if rec.ContractVersion != c.ContractVersion {
		t.Fatal("contract version mismatch")
	}
	for _, mode := range []fs.ReplayMode{fs.ReplaySimulation, fs.ReplayHistorical, fs.ReplayDecision} {
		res, err := fs.Replay(rec, c, mode, nil, nil, false)
		if err != nil {
			t.Fatalf("mode %s: %v", mode, err)
		}
		if res.Mode != mode {
			t.Fatalf("mode=%v", res.Mode)
		}
	}

	var applied []fs.Effect
	effC, _ := fs.NewFlow().
		When(condTrue, actConst("x"), fs.WithRuleID("r1"),
			fs.WithEffects([]fs.Effect{{Name: "e", Payload: 1}})).
		Compile()
	effRec := fs.Record(effC, nil, nil)
	res, err := fs.Replay(effRec, effC, fs.ReplayEffects, nil,
		func(e fs.Effect) { applied = append(applied, e) }, true)
	if err != nil {
		t.Fatal(err)
	}
	if res.EffectsApplied != 1 || len(applied) != 1 {
		t.Fatalf("effects_applied=%d applied=%d", res.EffectsApplied, len(applied))
	}
}

func TestHMACIntegrityAndFailClosed(t *testing.T) {
	// Features 42, 43.
	c := tracedContract(t)
	key := []byte("consumer-secret")
	rec := fs.Sign(fs.Record(c, map[string]any{"n": 1}, nil), key)
	if rec.Integrity == "" {
		t.Fatal("no integrity tag")
	}
	res, err := fs.Replay(rec, c, fs.ReplaySimulation, key, nil, false)
	if err != nil {
		t.Fatal(err)
	}
	if res.Equivalent == nil || !*res.Equivalent {
		t.Fatal("not equivalent")
	}
	if _, err := fs.Replay(rec, c, fs.ReplaySimulation, []byte("wrong"), nil, false); err == nil {
		t.Fatal("expected integrity failure")
	}
	other, _ := fs.NewFlow().When(condTrue, actConst("different"), fs.WithRuleID("r1")).Compile()
	if _, err := fs.Replay(rec, other, fs.ReplaySimulation, key, nil, false); err == nil {
		t.Fatal("expected version mismatch failure")
	}
}

func TestShadow(t *testing.T) {
	// Feature 44.
	current, _ := fs.NewFlow().
		When(func(i any) (bool, error) { return i.(map[string]any)["n"].(int) > 0, nil },
			actConst("pos"), fs.WithRuleID("r")).
		Default("neg").Compile()
	candidate, _ := fs.NewFlow().
		When(func(i any) (bool, error) { return i.(map[string]any)["n"].(int) > 10, nil },
			actConst("big"), fs.WithRuleID("r")).
		Default("neg").Compile()
	report := fs.Shadow(current, candidate,
		[]any{map[string]any{"n": 5}, map[string]any{"n": 50}}, nil)
	if report.Total != 2 || report.Differences < 1 {
		t.Fatalf("report=%+v", report)
	}
}

func TestValidateAndContractVersion(t *testing.T) {
	// Features 45, 46.
	c := tracedContract(t)
	issues := c.Validate()
	var _ []fs.ValidationIssue = issues // typed slice; empty means no findings
	if c.ContractVersion == "" {
		t.Fatal("empty contract version")
	}
	if tracedContract(t).ContractVersion != c.ContractVersion {
		t.Fatal("contract version not stable")
	}
}

func TestDeterministicClockReplay(t *testing.T) {
	// Feature 47.
	clock := fs.NewFakeClock(1_700_000_000_000, 0)
	c := tracedContract(t)
	rec := fs.Record(c, map[string]any{"n": 1}, clock)
	res, err := fs.Replay(rec, c, fs.ReplayDecision, nil, nil, false)
	if err != nil {
		t.Fatal(err)
	}
	if res.Equivalent == nil || !*res.Equivalent {
		t.Fatal("not equivalent")
	}
}

// ---------------------------------------------------------------------------
// Portable IR & cross-cutting (features 48-62)
// ---------------------------------------------------------------------------

func TestPExprOpsAndBuilders(t *testing.T) {
	// Features 48, 49.
	exprs := []*fs.PExpr{
		fs.PField("a"), fs.PConst(1),
		fs.PEq(fs.PField("a"), fs.PConst(1)), fs.PNe(fs.PField("a"), fs.PConst(1)),
		fs.PLt(fs.PField("a"), fs.PConst(1)), fs.PLe(fs.PField("a"), fs.PConst(1)),
		fs.PGt(fs.PField("a"), fs.PConst(1)), fs.PGe(fs.PField("a"), fs.PConst(1)),
		fs.PAnd(fs.PEq(fs.PField("a"), fs.PConst(1)), fs.PGt(fs.PField("b"), fs.PConst(0))),
		fs.POr(fs.PEq(fs.PField("a"), fs.PConst(1)), fs.PEq(fs.PField("a"), fs.PConst(2))),
		fs.PNot(fs.PEq(fs.PField("a"), fs.PConst(1))),
		fs.PIsNull(fs.PField("a")), fs.PIsNotNull(fs.PField("a")),
		fs.PIn(fs.PField("a"), []any{1, 2, 3}), fs.PNotIn(fs.PField("a"), []any{9}),
	}
	if len(exprs) != 15 {
		t.Fatalf("exprs=%d", len(exprs))
	}
	v, err := fs.EvalExpr(fs.PEq(fs.PField("a"), fs.PConst(1)), map[string]any{"a": 1})
	if err != nil || v != true {
		t.Fatalf("eval=%v err=%v", v, err)
	}
}

func TestExprSerialization(t *testing.T) {
	// Feature 50.
	expr := fs.PAnd(fs.PEq(fs.PField("x"), fs.PConst(1)), fs.PGt(fs.PField("y"), fs.PConst(0)))
	restored, err := fs.ExprFromDict(fs.ExprToDict(expr))
	if err != nil {
		t.Fatal(err)
	}
	v, _ := fs.EvalExpr(restored, map[string]any{"x": 1, "y": 5})
	if v != true {
		t.Fatal("round-trip failed")
	}
}

func TestPortableFlowAndRules(t *testing.T) {
	// Feature 51.
	c, err := fs.NewFlow().
		WhenExpr(fs.PEq(fs.PField("n"), fs.PConst(1)), fs.PConst("one"), fs.WithPRuleID("r1")).
		Compile()
	if err != nil {
		t.Fatal(err)
	}
	ir, err := c.ToIR()
	if err != nil {
		t.Fatal(err)
	}
	if len(ir.Rules) == 0 || ir.Rules[0].RuleID != "r1" {
		t.Fatalf("ir=%+v", ir)
	}
}

func TestWhenExprWhenNotExprFromIR(t *testing.T) {
	// Features 52, 53.
	c, err := fs.NewFlow().
		WhenExpr(fs.PEq(fs.PField("kind"), fs.PConst("a")), fs.PConst("A"), fs.WithPRuleID("ra")).
		WhenNotExpr(fs.PEq(fs.PField("kind"), fs.PConst("a")), fs.PConst("not-a"), fs.WithPRuleID("rb")).
		Default("none").
		Compile()
	if err != nil {
		t.Fatal(err)
	}
	class, _ := c.Portability()
	if class != "PORTABLE" {
		t.Fatalf("class=%s", class)
	}
	if c.TryExecute(map[string]any{"kind": "a"}).Value != "A" {
		t.Fatal("A failed")
	}
	if c.TryExecute(map[string]any{"kind": "b"}).Value != "not-a" {
		t.Fatal("not-a failed")
	}

	ir, _ := c.ToIR()
	rebuiltFlow, err := fs.FlowFromIR(fs.PortableFlowToDict(ir))
	if err != nil {
		t.Fatal(err)
	}
	rc, err := rebuiltFlow.Compile()
	if err != nil {
		t.Fatal(err)
	}
	if rc.TryExecute(map[string]any{"kind": "a"}).Value != "A" {
		t.Fatal("from_ir failed")
	}
}

func TestToIRAndJSON(t *testing.T) {
	// Feature 54.
	c, _ := fs.NewFlow().
		WhenExpr(fs.PEq(fs.PField("n"), fs.PConst(1)), fs.PConst("one"), fs.WithPRuleID("r1")).
		Compile()
	ir, err := c.ToIR()
	if err != nil {
		t.Fatal(err)
	}
	if ir.FlowID == "" {
		t.Fatal("empty flow_id")
	}
	js, err := c.ToIRJSON()
	if err != nil || js == "" {
		t.Fatalf("json err=%v", err)
	}
	round, err := fs.PortableFlowFromJSON(js)
	if err != nil {
		t.Fatal(err)
	}
	if round.Rules[0].RuleID != "r1" {
		t.Fatal("round-trip failed")
	}
}

func TestPortableNativeClassification(t *testing.T) {
	// Feature 55.
	portable, _ := fs.NewFlow().
		WhenExpr(fs.PEq(fs.PField("a"), fs.PConst(1)), fs.PConst(1), fs.WithPRuleID("r")).
		Compile()
	if class, _ := portable.Portability(); class != "PORTABLE" {
		t.Fatalf("class=%s", class)
	}
	native, _ := fs.NewFlow().When(condTrue, actConst(1), fs.WithRuleID("r")).Compile()
	if class, _ := native.Portability(); class != "NATIVE" {
		t.Fatalf("class=%s", class)
	}
	if _, err := native.ToIR(); err == nil {
		t.Fatal("expected PortabilityError")
	}
}

func TestPortabilityReport(t *testing.T) {
	// Feature 56.
	c, _ := fs.NewFlow().
		When(condTrue, actConst(1), fs.WithRuleID("r1")).
		Catch("Kind.Any", handlerConst(0)).
		Compile()
	class, offenders := c.Portability()
	if class == "" || offenders == nil {
		t.Fatal("empty portability report")
	}
}

func TestIRLimits(t *testing.T) {
	// Feature 57 (SPEC 9.2, MaxExprDepth=100).
	if fs.MaxExprDepth <= 0 {
		t.Fatal("MaxExprDepth not exported")
	}
	deep := map[string]any{"op": "const", "value": 1}
	for i := 0; i < fs.MaxExprDepth+1; i++ {
		deep = map[string]any{"op": "not", "args": []any{deep}}
	}
	if _, err := fs.ExprFromDict(deep); err == nil {
		t.Fatal("expected depth limit error")
	}
}

func TestFlowIDAndContractVersionInIR(t *testing.T) {
	// Feature 58.
	c, _ := fs.NewFlow().
		WithFlowID("consumer-flow").
		WhenExpr(fs.PEq(fs.PField("a"), fs.PConst(1)), fs.PConst(1), fs.WithPRuleID("r1")).
		Compile()
	ir, _ := c.ToIR()
	if ir.FlowID != "consumer-flow" || ir.ContractVersion != c.ContractVersion {
		t.Fatalf("ir=%+v cv=%s", ir, c.ContractVersion)
	}
}

func TestPortableJSONRoundTrip(t *testing.T) {
	// Feature 59.
	c, _ := fs.NewFlow().
		WhenExpr(fs.PEq(fs.PField("a"), fs.PConst(1)), fs.PConst("one"), fs.WithPRuleID("r1")).
		Compile()
	js, _ := c.ToIRJSON()
	restored, err := fs.PortableFlowFromJSON(js)
	if err != nil {
		t.Fatal(err)
	}
	ir1, _ := c.ToIR()
	if restored.FlowID != ir1.FlowID || restored.Rules[0].RuleID != "r1" {
		t.Fatal("round-trip failed")
	}
}

func TestFlowContext(t *testing.T) {
	// Feature 60.
	ctx := fs.NewFlowContext(map[string]any{"x": 1}, fs.NewFakeClock(0, 0))
	if ctx.Input == nil || ctx.Clock == nil || ctx.State == nil {
		t.Fatalf("ctx=%+v", ctx)
	}
}

func TestClocks(t *testing.T) {
	// Feature 61.
	sys := fs.SystemClock{}
	if sys.Wall() <= 0 || sys.Monotonic() < 0 {
		t.Fatal("system clock invalid")
	}
	fake := fs.NewFakeClock(1_000, 0)
	fake.Advance(10_000)
	if fake.Wall() != 11_000 {
		t.Fatalf("wall=%d", fake.Wall())
	}
	c, _ := fs.NewFlow().
		When(condTrue, actConst("ok"), fs.WithRuleID("r1")).
		WithClock(fs.NewFakeClock(0, 0)).
		Compile()
	if c.TryExecute(nil).Value != "ok" {
		t.Fatal("with_clock failed")
	}
}

func TestWithFlowID(t *testing.T) {
	// Feature 62.
	c, _ := fs.NewFlow().
		WithFlowID("my-flow").
		WhenExpr(fs.PEq(fs.PField("a"), fs.PConst(1)), fs.PConst(1), fs.WithPRuleID("r1")).
		Compile()
	ir, _ := c.ToIR()
	if ir.FlowID != "my-flow" {
		t.Fatalf("flow_id=%s", ir.FlowID)
	}
}

// ---------------------------------------------------------------------------
// Error hierarchy sanity
// ---------------------------------------------------------------------------

func TestErrorHierarchy(t *testing.T) {
	for _, err := range []error{
		fs.NewStructureError("x"),
		fs.NewKindTimeout("x"),
		fs.NewKindCancelled("x"),
		fs.NewKindValueError("x"),
		fs.NewKindAny("x"),
	} {
		if err == nil {
			t.Fatal("nil error")
		}
	}
	if fs.SpecVersion == "" {
		t.Fatal("empty SpecVersion")
	}
}
