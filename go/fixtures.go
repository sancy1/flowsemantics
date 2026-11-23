package flowsemantics

// Fixture vocabulary — spec/fixtures.md, Go adapter.

import (
	"encoding/json"
	"fmt"
)

// FixtureContext is the mutable context shared across fixture resolutions
// within one vector run.
type FixtureContext struct {
	Records []map[string]any
}

// NewFixtureContext creates an empty FixtureContext.
func NewFixtureContext() *FixtureContext { return &FixtureContext{} }

var inputFixtures = map[string]any{
	"input.empty":       map[string]any{},
	"input.order_50":    map[string]any{"total": float64(50)},
	"input.order_0":     map[string]any{"total": float64(0)},
	"input.order_large": map[string]any{"total": float64(10000)},
}

func condTrue(input any) (bool, error)  { return true, nil }
func condFalse(input any) (bool, error) { return false, nil }
func guardTrue(input any) (bool, error) { return true, nil }
func guardFalse(input any) (bool, error) { return false, nil }

func makeCondReturns(v bool) ConditionFn {
	return func(input any) (bool, error) { return v, nil }
}
func makeCondThrows(kind string) ConditionFn {
	return func(input any) (bool, error) { return false, ExceptionForKind(kind) }
}
func makeCondReturnsPerCall(values []bool) ConditionFn {
	i := 0
	return func(input any) (bool, error) {
		v := values[len(values)-1]
		if i < len(values) { v = values[i] }
		i++
		return v, nil
	}
}

func makeActionConst(v any) ActionFn {
	return func(input any, prev any) (any, error) { return v, nil }
}
func makeActionThrows(kind string) ActionFn {
	return func(input any, prev any) (any, error) { return nil, ExceptionForKind(kind) }
}
func makeActionPrev() ActionFn {
	return func(input any, prev any) (any, error) { return prev, nil }
}

func makeCatchHandles(v any) ExceptionHandler {
	return func(input any, exc any) (any, error) { return v, nil }
}
func makeCatchThrows(kind string) ExceptionHandler {
	return func(input any, exc any) (any, error) { return nil, ExceptionForKind(kind) }
}

func makeHookRecords(ctx *FixtureContext) HookFn {
	return func(input any, ruleID string, value any) {
		ctx.Records = append(ctx.Records, map[string]any{"rule_id": ruleID, "value": value})
	}
}
func makeHookThrows(kind string) HookFn {
	return func(input any, ruleID string, value any) { panic(ExceptionForKind(kind)) }
}

func makeCleanupThrows(kind string) CleanupFn {
	return func(ctx *FinallyContext) error { return ExceptionForKind(kind) }
}
func makeCleanupDelays(ms int64) CleanupFn {
	return func(ctx *FinallyContext) error { return nil }
}
func makeEnrichmentDelayed(ms int64) ActionFn {
	return func(input any, prev any) (any, error) {
		return map[string]any{"delayed_ms": float64(ms)}, nil
	}
}

// ResolveFixture resolves a fixture reference {"fixture": name, "params": {...}}.
// Returns the resolved value (input data, or a callable wrapped in FixtureValue).
func ResolveFixture(ref map[string]any, ctx *FixtureContext) (any, error) {
	name, _ := ref["fixture"].(string)
	params, _ := ref["params"].(map[string]any)
	req := func(k string) any {
		v, ok := params[k]
		if !ok { panic("missing fixture param: " + k) }
		return v
	}

	if v, ok := inputFixtures[name]; ok { return v, nil }

	switch name {
	case "cond.true": return FixtureValue{Cond: condTrue}, nil
	case "cond.false": return FixtureValue{Cond: condFalse}, nil
	case "cond.returns": return FixtureValue{Cond: makeCondReturns(toBool(req("value")))}, nil
	case "cond.throws": return FixtureValue{Cond: makeCondThrows(toStr(req("kind")))}, nil
	case "cond.returns_per_call":
		raw, _ := req("values").([]any)
		var vals []bool
		for _, v := range raw { vals = append(vals, toBool(v)) }
		return FixtureValue{Cond: makeCondReturnsPerCall(vals)}, nil
	case "action.const": return FixtureValue{Action: makeActionConst(req("v"))}, nil
	case "action.throws": return FixtureValue{Action: makeActionThrows(toStr(req("kind")))}, nil
	case "action.prev": return FixtureValue{Action: makeActionPrev()}, nil
	case "action.returns":
		sub, _ := req("ref").(map[string]any)
		if sub == nil { sub, _ = req("fixture_ref").(map[string]any) }
		return ResolveFixture(sub, ctx)
	case "guard.true": return FixtureValue{Guard: guardTrue}, nil
	case "guard.false": return FixtureValue{Guard: guardFalse}, nil
	case "catch.handles": return FixtureValue{Handler: makeCatchHandles(params["v"])}, nil
	case "catch.throws": return FixtureValue{Handler: makeCatchThrows(toStr(req("kind")))}, nil
	case "hook.records": return FixtureValue{Hook: makeHookRecords(ctx)}, nil
	case "hook.throws": return FixtureValue{Hook: makeHookThrows(toStr(req("kind")))}, nil
	case "cleanup.succeeds": return FixtureValue{Cleanup: func(ctx *FinallyContext) error { return nil }}, nil
	case "cleanup.throws": return FixtureValue{Cleanup: makeCleanupThrows(toStr(req("kind")))}, nil
	case "cleanup.cooperative": return FixtureValue{Cleanup: func(ctx *FinallyContext) error { return nil }}, nil
	case "cleanup.ignores_token": return FixtureValue{Cleanup: func(ctx *FinallyContext) error { return nil }}, nil
	case "cleanup.delays": return FixtureValue{Cleanup: makeCleanupDelays(toInt(req("ms")))}, nil
	case "enrichment.delayed": return FixtureValue{Action: makeEnrichmentDelayed(toInt(req("ms")))}, nil
	}
	return nil, NewStructureError("unknown fixture: " + name)
}

// FixtureValue wraps a resolved callable so the runner can type-assert.
type FixtureValue struct {
	Cond    ConditionFn
	Action  ActionFn
	Guard   GuardFn
	Handler ExceptionHandler
	Hook    HookFn
	Cleanup CleanupFn
}

// AsFixture casts a resolved fixture value to FixtureValue.
func AsFixture(v any) (*FixtureValue, error) {
	if fv, ok := v.(*FixtureValue); ok { return fv, nil }
	if fv, ok := v.(FixtureValue); ok { return &fv, nil }
	return nil, NewStructureError(fmt.Sprintf("expected FixtureValue, got %T", v))
}

func toBool(v any) bool {
	b, _ := v.(bool)
	return b
}
func toStr(v any) string { s, _ := v.(string); return s }
func toInt(v any) int64 {
	switch n := v.(type) {
	case float64: return int64(n)
	case int64: return n
	case int: return int64(n)
	case json.Number: i, _ := n.Int64(); return i
	}
	return 0
}
