// Conformance runner — conformance/runner-protocol.md.
// Usage: go run ./cmd/runner --vectors <dir>
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	fs "github.com/sancy1/flowsemantics/go"
)

type Vector struct {
	ID          string                     `json:"id"`
	SpecVersion string                     `json:"spec_version"`
	SpecSection string                     `json:"spec_section"`
	Pipeline    map[string]json.RawMessage `json:"pipeline"`
	Input       map[string]json.RawMessage `json:"input"`
	Expected    map[string]any             `json:"expected"`
	Trace       []map[string]any           `json:"trace"`
	TraceSubset bool                       `json:"trace_subset"`
	ExpectedError string                   `json:"expected_error"`
}

type Result struct {
	ID      string
	Passed  bool
	Reason  string
}

func discover(dir string) ([]string, error) {
	var out []string
	err := filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil { return err }
		if !info.IsDir() && strings.HasSuffix(path, ".json") { out = append(out, path) }
		return nil
	})
	sort.Strings(out)
	return out, err
}

func unmarshal(v any, raw json.RawMessage) error {
	if len(raw) == 0 { return nil }
	return json.Unmarshal(raw, v)
}

func buildFlow(v *Vector) (*fs.Flow, string) {
	// portable_ir path
	if raw, ok := v.Pipeline["portable_ir"]; ok {
		var ir any
		if err := json.Unmarshal(raw, &ir); err != nil {
			return nil, "portable_ir parse: " + err.Error()
		}
		flow, err := fs.FlowFromIR(ir)
		if err != nil { return nil, "portable_ir rejected: " + err.Error() }
		return flow, ""
	}

	flow := fs.NewFlow()
	ctx := fs.NewFixtureContext()

	var mode string
	if raw, ok := v.Pipeline["mode"]; ok { _ = json.Unmarshal(raw, &mode) }
	if mode != "" { flow.WithMode(fs.EvaluationMode(mode)) }

	var rules []map[string]json.RawMessage
	if raw, ok := v.Pipeline["rules"]; ok {
		if err := json.Unmarshal(raw, &rules); err != nil { return nil, "rules parse: " + err.Error() }
	}
	for _, r := range rules {
		var kind, id string
		_ = json.Unmarshal(r["kind"], &kind)
		_ = json.Unmarshal(r["id"], &id)
		if kind == "" { kind = "when" }

		var actionRef map[string]any
		if raw, ok := r["action"]; ok { _ = json.Unmarshal(raw, &actionRef) }
		actionFV, err := fs.ResolveFixture(actionRef, ctx)
		if err != nil { return nil, "action fixture: " + err.Error() }
		action := actionFV.(fs.FixtureValue).Action

		var effects []fs.Effect
		if raw, ok := r["effects"]; ok {
			var es []struct {
				Name    string `json:"name"`
				Payload any    `json:"payload"`
			}
			_ = json.Unmarshal(raw, &es)
			for _, e := range es { effects = append(effects, fs.Effect{Name: e.Name, Payload: e.Payload}) }
		}

		opts := []fs.RuleOpt{fs.WithRuleID(id)}
		if len(effects) > 0 { opts = append(opts, fs.WithEffects(effects)) }
		if raw, ok := r["priority"]; ok {
			var p float64
			_ = json.Unmarshal(raw, &p)
			opts = append(opts, fs.WithPriority(int(p)))
		}
		if raw, ok := r["guard"]; ok {
			var gref map[string]any
			_ = json.Unmarshal(raw, &gref)
			gfv, err := fs.ResolveFixture(gref, ctx)
			if err != nil { return nil, "guard fixture: " + err.Error() }
			opts = append(opts, fs.WithGuard(gfv.(fs.FixtureValue).Guard))
		}

		if kind == "then" {
			flow.Then(action, opts...)
			continue
		}
		var cref map[string]any
		if raw, ok := r["condition"]; ok { _ = json.Unmarshal(raw, &cref) }
		cfv, err := fs.ResolveFixture(cref, ctx)
		if err != nil { return nil, "condition fixture: " + err.Error() }
		cond := cfv.(fs.FixtureValue).Cond
		if kind == "when_not" {
			flow.WhenNot(cond, action, opts...)
		} else {
			flow.When(cond, action, opts...)
		}
	}

	// catches
	var catches []map[string]json.RawMessage
	if raw, ok := v.Pipeline["catches"]; ok {
		_ = json.Unmarshal(raw, &catches)
	}
	for _, c := range catches {
		var ckind, cid, excKind string
		_ = json.Unmarshal(c["kind"], &ckind)
		_ = json.Unmarshal(c["id"], &cid)
		_ = json.Unmarshal(c["exc_kind"], &excKind)
		copts := []fs.CatchOpt{}
		if cid != "" { copts = append(copts, fs.WithCatchID(cid)) }
		switch ckind {
		case "rethrow":
			flow.Rethrow()
		case "any":
			var href map[string]any
			if raw, ok := c["handler"]; ok { _ = json.Unmarshal(raw, &href) }
			hfv, err := fs.ResolveFixture(href, ctx)
			if err != nil { return nil, "catch handler: " + err.Error() }
			flow.CatchAny(hfv.(fs.FixtureValue).Handler, copts...)
		case "typed", "when":
			var href map[string]any
			if raw, ok := c["handler"]; ok { _ = json.Unmarshal(raw, &href) }
			hfv, err := fs.ResolveFixture(href, ctx)
			if err != nil { return nil, "catch handler: " + err.Error() }
			handler := hfv.(fs.FixtureValue).Handler
			if ckind == "typed" {
				flow.Catch(excKind, handler, copts...)
			} else {
				var pref map[string]any
				if raw, ok := c["predicate"]; ok { _ = json.Unmarshal(raw, &pref) }
				pfv, err := fs.ResolveFixture(pref, ctx)
				if err != nil { return nil, "catch predicate: " + err.Error() }
				predCond := pfv.(fs.FixtureValue).Cond
				pred := func(input any, exc any) (bool, error) { return predCond(input) }
				flow.CatchWhen(excKind, pred, handler, copts...)
			}
		default:
			return nil, "unknown catch kind: " + ckind
		}
	}

	// hooks
	var hooks []map[string]json.RawMessage
	if raw, ok := v.Pipeline["on_match"]; ok {
		_ = json.Unmarshal(raw, &hooks)
	}
	for _, h := range hooks {
		var href map[string]any
		b, _ := json.Marshal(h)
		_ = json.Unmarshal(b, &href)
		hfv, err := fs.ResolveFixture(href, ctx)
		if err != nil { return nil, "hook fixture: " + err.Error() }
		flow.OnMatch(hfv.(fs.FixtureValue).Hook)
	}

	// finalizer — may be a bare fixture-name string or a FixtureRef object
	if raw, ok := v.Pipeline["finally"]; ok {
		var fref map[string]any
		var fname string
		if err := json.Unmarshal(raw, &fname); err == nil {
			fref = map[string]any{"fixture": fname}
		} else if err := json.Unmarshal(raw, &fref); err != nil {
			return nil, "finally parse: " + err.Error()
		}
		ffv, err := fs.ResolveFixture(fref, ctx)
		if err != nil { return nil, "finally fixture: " + err.Error() }
		flow.Finally(ffv.(fs.FixtureValue).Cleanup)
	}
	if raw, ok := v.Pipeline["finally_policy"]; ok {
		var p string
		_ = json.Unmarshal(raw, &p)
		flow.WithFinallyPolicy(fs.FinallyFailurePolicy(p))
	}
	if raw, ok := v.Pipeline["finally_timeout_ms"]; ok {
		var ms float64
		_ = json.Unmarshal(raw, &ms)
		flow.WithFinallyTimeout(int64(ms))
	}

	// fallback
	if raw, ok := v.Pipeline["fallback"]; ok {
		var fb map[string]json.RawMessage
		_ = json.Unmarshal(raw, &fb)
		var fkind string
		_ = json.Unmarshal(fb["kind"], &fkind)
		if fkind == "otherwise" {
			var aref map[string]any
			if raw, ok := fb["action"]; ok { _ = json.Unmarshal(raw, &aref) }
			afv, err := fs.ResolveFixture(aref, ctx)
			if err != nil { return nil, "fallback action: " + err.Error() }
			flow.Otherwise(afv.(fs.FixtureValue).Action)
		} else if fkind == "default_if_no_match" {
			var val any
			if raw, ok := fb["value"]; ok { _ = json.Unmarshal(raw, &val) }
			flow.DefaultIfNoMatch(val)
		} else {
			return nil, "unknown fallback kind: " + fkind
		}
	}
	return flow, ""
}

func deepEqualJSON(a, b any) bool {
	aj, _ := json.Marshal(a)
	bj, _ := json.Marshal(b)
	return string(aj) == string(bj)
}

func compareExpected(o *fs.FlowOutcome, exp map[string]any) string {
	if got, want := string(o.ExecutionStatus), exp["execution_status"]; got != fmt.Sprint(want) {
		return fmt.Sprintf("execution_status: expected %v, got %s", want, got)
	}
	var gotDecision any
	if o.DecisionStatus != nil { gotDecision = string(*o.DecisionStatus) }
	if exp["decision_status"] != nil && gotDecision != exp["decision_status"] {
		return fmt.Sprintf("decision_status: expected %v, got %v", exp["decision_status"], gotDecision)
	}
	if exp["decision_status"] == nil && gotDecision != nil {
		return fmt.Sprintf("decision_status: expected null, got %v", gotDecision)
	}
	if v, ok := exp["value"]; ok && !deepEqualJSON(o.Value, v) {
		return fmt.Sprintf("value: expected %v, got %v", v, o.Value)
	}
	if b, ok := exp["has_recovery"].(bool); ok && b != (o.Recovery != nil) {
		return "has_recovery mismatch"
	}
	if b, ok := exp["has_interruption"].(bool); ok && b != (o.Interruption != nil) {
		return "has_interruption mismatch"
	}
	var gotKind any
	if o.Interruption != nil { gotKind = string(o.Interruption.Kind) }
	if exp["interruption_kind"] != nil && gotKind != exp["interruption_kind"] {
		return fmt.Sprintf("interruption_kind: expected %v, got %v", exp["interruption_kind"], gotKind)
	}
	if exp["interruption_kind"] == nil && gotKind != nil {
		return fmt.Sprintf("interruption_kind: expected null, got %v", gotKind)
	}
	if b, ok := exp["has_finalization"].(bool); ok && b != (o.Finalization != nil) {
		return "has_finalization mismatch"
	}
	var gotClean any
	if o.Finalization != nil { gotClean = o.Finalization.IsClean }
	if exp["is_clean"] != nil && gotClean != exp["is_clean"] {
		return fmt.Sprintf("is_clean: expected %v, got %v", exp["is_clean"], gotClean)
	}
	if exp["is_clean"] == nil && gotClean != nil {
		return fmt.Sprintf("is_clean: expected null, got %v", gotClean)
	}
	if n, ok := exp["secondary_exceptions_count"].(float64); ok {
		if int(n) != len(o.SecondaryExceptions) {
			return fmt.Sprintf("secondary_exceptions_count: expected %v, got %d", n, len(o.SecondaryExceptions))
		}
	}
	var gotPrimary any
	if o.PrimaryException != nil { gotPrimary = fs.KindOfException(o.PrimaryException) }
	if exp["primary_exception_kind"] != nil && gotPrimary != exp["primary_exception_kind"] {
		return fmt.Sprintf("primary_exception_kind: expected %v, got %v", exp["primary_exception_kind"], gotPrimary)
	}
	if exp["primary_exception_kind"] == nil && gotPrimary != nil {
		return fmt.Sprintf("primary_exception_kind: expected null, got %v", gotPrimary)
	}
	if raw, ok := exp["effects"]; ok {
		var want []map[string]any
		b, _ := json.Marshal(raw)
		_ = json.Unmarshal(b, &want)
		// normalize: omit nil payloads, treat empty as equal
		norm := func(effects []map[string]any) []map[string]any {
			out := []map[string]any{}
			for _, e := range effects {
				m := map[string]any{"name": e["name"]}
				if p, ok := e["payload"]; ok && p != nil { m["payload"] = p }
				out = append(out, m)
			}
			return out
		}
		var gotRaw []map[string]any
		for _, e := range o.Effects {
			gotRaw = append(gotRaw, map[string]any{"name": e.Name, "payload": e.Payload})
		}
		got := norm(gotRaw)
		wn := norm(want)
		if len(got) == 0 && len(wn) == 0 { return "" }
		if !deepEqualJSON(got, wn) {
			return fmt.Sprintf("effects: expected %v, got %v", wn, got)
		}
	}
	return ""
}

func compareTrace(v *Vector, o *fs.FlowOutcome) string {
	if len(v.Trace) == 0 { return "" }
	if o.Trace == nil { return "trace expected but not collected" }
	type ev struct{ Type, RuleID, Reason string }
	var observed []ev
	for _, e := range o.Trace.Events {
		observed = append(observed, ev{string(e.Type), e.RuleID, string(e.Reason)})
	}
	matches := func(o ev, e map[string]any) bool {
		if o.Type != fmt.Sprint(e["type"]) { return false }
		if rid, ok := e["rule_id"]; ok && rid != nil && o.RuleID != fmt.Sprint(rid) { return false }
		if r, ok := e["reason"]; ok && r != nil && o.Reason != fmt.Sprint(r) { return false }
		return true
	}
	if v.TraceSubset {
		pos := 0
		for _, e := range v.Trace {
			found := false
			for pos < len(observed) {
				if matches(observed[pos], e) { found = true; pos++; break }
				pos++
			}
			if !found { return fmt.Sprintf("trace subset: missing %v", e) }
		}
		return ""
	}
	if len(observed) != len(v.Trace) {
		return fmt.Sprintf("trace length: expected %d, got %d", len(v.Trace), len(observed))
	}
	for i, e := range v.Trace {
		if !matches(observed[i], e) {
			return fmt.Sprintf("trace[%d]: expected %v, got %v", i, e, observed[i])
		}
	}
	return ""
}

func runVector(path string) Result {
	data, err := os.ReadFile(path)
	if err != nil { return Result{path, false, "read: " + err.Error()} }
	var v Vector
	if err := json.Unmarshal(data, &v); err != nil {
		return Result{path, false, "parse: " + err.Error()}
	}
	id := v.ID
	if id == "" { id = path }
	if _, hasRules := v.Pipeline["rules"]; !hasRules {
		if _, hasIR := v.Pipeline["portable_ir"]; !hasIR {
			return Result{id, false, "pipeline.rules or portable_ir missing"}
		}
	}
	expectedError := v.ExpectedError
	flow, reason := buildFlow(&v)
	if reason != "" {
		if expectedError != "" { return Result{id, strings.Contains(reason, expectedError), reason} }
		return Result{id, false, reason}
	}

	// input is {"fixture": name, "params": {...}}
	var inputMap map[string]any
	if err := json.Unmarshal(mustRaw(v.Input), &inputMap); err != nil {
		return Result{id, false, "input parse: " + err.Error()}
	}
	inputVal, err := fs.ResolveFixture(inputMap, fs.NewFixtureContext())
	if err != nil {
		reason := "input fixture: " + err.Error()
		if expectedError != "" { return Result{id, strings.Contains(reason, expectedError), reason} }
		return Result{id, false, reason}
	}

	contract, err := flow.Compile()
	if err != nil {
		reason := "compile: " + err.Error()
		if expectedError != "" { return Result{id, strings.Contains(reason, expectedError), reason} }
		return Result{id, false, reason}
	}

	clock := fs.NewFakeClock(1700000000000, 0)
	traceEnabled := len(v.Trace) > 0
	var outcome *fs.FlowOutcome
	if raw, ok := v.Pipeline["execution"]; ok {
		var mode string
		_ = json.Unmarshal(raw, &mode)
		if mode == "async" {
			outcome = contract.TryExecuteWithClock(inputVal, clock, traceEnabled)
		} else {
			outcome = contract.TryExecuteWithClock(inputVal, clock, traceEnabled)
		}
	} else {
		outcome = contract.TryExecuteWithClock(inputVal, clock, traceEnabled)
	}

	if expectedError != "" {
		return Result{id, false, fmt.Sprintf("expected rejection containing %q but execution completed", expectedError)}
	}
	if mismatch := compareExpected(outcome, v.Expected); mismatch != "" {
		return Result{id, false, mismatch}
	}
	if terr := compareTrace(&v, outcome); terr != "" {
		return Result{id, false, terr}
	}
	return Result{id, true, ""}
}

func mustRaw(m map[string]json.RawMessage) json.RawMessage {
	// input is a single object; re-marshal the map
	b, _ := json.Marshal(m)
	return b
}

func main() {
	dir := flag.String("vectors", "", "vectors directory")
	flag.Parse()
	if *dir == "" {
		fmt.Fprintln(os.Stderr, "usage: runner --vectors <dir>")
		os.Exit(2)
	}
	paths, err := discover(*dir)
	if err != nil {
		fmt.Fprintln(os.Stderr, "discover:", err)
		os.Exit(2)
	}
	if len(paths) == 0 {
		fmt.Println("RESULT: 0/0 passed (no vectors discovered)")
		return
	}
	passed := 0
	for _, p := range paths {
		r := runVector(p)
		if r.Passed {
			passed++
			fmt.Printf("PASS %s\n", r.ID)
		} else {
			fmt.Printf("FAIL %s: %s\n", r.ID, r.Reason)
		}
	}
	fmt.Printf("RESULT: %d/%d passed\n", passed, len(paths))
	if passed != len(paths) { os.Exit(1) }
}
