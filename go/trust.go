package flowsemantics

// Trust layer — SPEC 12.4-12.10: contract versioning, explain,
// validate, replay (4 modes), shadow.

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"strings"
)

// SpecVersion is the SPEC version this implementation conforms to.
const SpecVersion = "0.1.0"

// ContractVersion computes the structural contract version (SPEC 12.9,
// algorithm v2): SHA-256 of canonical JSON, truncated to 32 hex chars.
// The payload covers portable rule bodies (condition/guard/transform
// expressions and effects) so that rule-body changes invalidate replay
// records; native (func) rule bodies are marked "native": true because
// callables are not serializable. Effective dates are epoch
// milliseconds, matching the Python/C#/Java/TS reference payloads.
func ContractVersion(rules []Rule, fallback *Fallback, mode EvaluationMode,
	catches []CatchRule, finalizerCount int, policy FinallyFailurePolicy,
	finallyTimeoutMs int64, traceEnabled bool, portableRules []PortableRule) string {
	ruleList := make([]map[string]any, 0, len(rules))
	for i, r := range rules {
		var ef, eu any
		if r.EffectiveFrom != nil { ef = *r.EffectiveFrom }
		if r.EffectiveUntil != nil { eu = *r.EffectiveUntil }
		var pr *PortableRule
		if i < len(portableRules) { pr = &portableRules[i] }
		entry := map[string]any{
			"id": r.ID, "kind": r.Kind, "priority": r.Priority,
			"effective_from": ef, "effective_until": eu,
			"native": pr == nil,
		}
		if pr != nil {
			entry["condition"] = ExprToDict(pr.Condition)
			entry["guard"] = ExprToDict(pr.Guard)
			entry["transform"] = ExprToDict(pr.Transform)
		} else {
			entry["condition"] = nil
			entry["guard"] = nil
			entry["transform"] = nil
		}
		effects := make([]map[string]any, 0, len(r.Effects))
		for _, e := range r.Effects {
			effects = append(effects, map[string]any{
				"name": e.Name, "payload": jsonSafe(e.Payload),
			})
		}
		entry["effects"] = effects
		ruleList = append(ruleList, entry)
	}
	var fb any
	if fallback != nil { fb = fallback.Kind }
	catchKinds := make([]string, 0, len(catches))
	for _, c := range catches { catchKinds = append(catchKinds, c.Kind) }
	payload := map[string]any{
		"algorithm":          "flowsemantics-contract-v2",
		"rules":              ruleList,
		"fallback":           fb,
		"mode":               string(mode),
		"catches":            catchKinds,
		"finalizer_count":    finalizerCount,
		"finally_policy":     string(policy),
		"finally_timeout_ms": finallyTimeoutMs,
		"trace_enabled":      traceEnabled,
	}
	canonical, _ := json.Marshal(payload) // Go marshals map keys sorted
	sum := sha256.Sum256(canonical)
	return hex.EncodeToString(sum[:])[:32]
}

// jsonSafe returns v if it is JSON-marshalable, otherwise a stable string
// form, so contract hashing never fails on exotic effect payloads.
func jsonSafe(v any) any {
	if v == nil { return nil }
	if _, err := json.Marshal(v); err != nil {
		return fmt.Sprint(v)
	}
	return v
}

// ValidationIssue — SPEC 12.8.
type ValidationIssue struct {
	Severity string // "error" | "warning"
	Code     string
	Message  string
	RuleID   string
}

// Validate performs static analysis without execution (SPEC 12.8).
func (c *FlowContract) Validate() []ValidationIssue {
	var issues []ValidationIssue
	if len(c.rules) == 0 && c.fallback == nil {
		issues = append(issues, ValidationIssue{"error", "empty_flow",
			"flow has neither rules nor a fallback", ""})
	}
	seen := map[string]bool{}
	for _, r := range c.rules {
		if seen[r.ID] {
			issues = append(issues, ValidationIssue{"error", "duplicate_rule_id",
				"duplicate RuleId: " + r.ID, r.ID})
		}
		seen[r.ID] = true
	}
	seenAny := false
	for _, cr := range c.catches {
		if cr.Kind == "any" {
			seenAny = true
		} else if seenAny && (cr.Kind == "typed" || cr.Kind == "when") {
			issues = append(issues, ValidationIssue{"error", "catch_any_ordering",
				"typed catch registered after catch_any", ""})
		}
	}
	// effective date inversion (SPEC 12.9)
	for _, r := range c.rules {
		if r.EffectiveFrom != nil && r.EffectiveUntil != nil && *r.EffectiveFrom >= *r.EffectiveUntil {
			issues = append(issues, ValidationIssue{"error", "invalid_effective_window",
				"effective_from must be before effective_until", r.ID})
		}
	}
	// unreachable rules: in FirstMatch/Priority, a rule after an
	// unconditional match can never fire (SPEC 12.8). Unconditional is
	// provable only for portable const-true conditions.
	if c.mode != AllMatch {
		unconditional := false
		for i, r := range c.rules {
			if r.Kind == "then" { continue }
			if unconditional {
				issues = append(issues, ValidationIssue{"warning", "unreachable_rule",
					"rule cannot match: an earlier unconditional rule always matches first", r.ID})
				continue
			}
			if c.hasPortable && i < len(c.portableRules) &&
				c.portableRules[i].Condition != nil &&
				c.portableRules[i].Condition.Op == "const" &&
				truthy(c.portableRules[i].Condition.Value) {
				unconditional = true
			}
		}
	}
	// overlap warning: identical portable conditions. O(n) grouping by
	// (kind, canonical condition JSON); pairwise compare only within
	// each group (SPEC 12.8).
	if c.hasPortable {
		groups := map[string][]int{}
		for i, pr := range c.portableRules {
			var condJSON string
			if pr.Condition != nil {
				if b, err := json.Marshal(ExprToDict(pr.Condition)); err == nil {
					condJSON = string(b)
				}
			}
			key := pr.Kind + "\x00" + condJSON
			groups[key] = append(groups[key], i)
		}
		for _, idxs := range groups {
			for a := 0; a < len(idxs); a++ {
				for b := a + 1; b < len(idxs); b++ {
					issues = append(issues, ValidationIssue{"warning", "overlapping_rules",
						"rules have structurally identical conditions", c.portableRules[idxs[b]].RuleID})
				}
			}
		}
	}
	// gap warning: no fallback means some inputs may produce NO_MATCH.
	if c.fallback == nil && len(c.rules) > 0 {
		issues = append(issues, ValidationIssue{"warning", "possible_gap",
			"no fallback configured; some inputs may produce NO_MATCH", ""})
	}
	return issues
}

// exprEqual compares two portable expressions structurally.
func exprEqual(a, b *PExpr) bool {
	if a == nil || b == nil { return a == b }
	if a.Op != b.Op { return false }
	if fmt.Sprint(a.Value) != fmt.Sprint(b.Value) { return false }
	if len(a.Args) != len(b.Args) { return false }
	for i := range a.Args {
		if !exprEqual(a.Args[i], b.Args[i]) { return false }
	}
	return true
}

// Explain renders a trace as human-readable lines (SPEC 12.4).
func (c *FlowContract) Explain(trace *ExecutionTrace) string {
	var b strings.Builder
	fmt.Fprintf(&b, "FlowContract %s: %d event(s)\n", c.ContractVersion, len(trace.Events))
	for _, e := range trace.Events {
		rid := e.RuleID
		if rid == "" { rid = "-" }
		reason := ""
		if e.Reason != "" { reason = " (" + string(e.Reason) + ")" }
		fmt.Fprintf(&b, "  [%s] rule=%s%s\n", e.Type, rid, reason)
	}
	return strings.TrimRight(b.String(), "\n")
}

// ToIR exports the contract as a PortableFlow IR document (SPEC 14.2).
// Only PORTABLE contracts carry an IR; NATIVE contracts error.
func (c *FlowContract) ToIR() (*PortableFlow, error) {
	if !c.hasPortable {
		return nil, NewStructureError("contract is NATIVE; only PORTABLE contracts can be exported to the Portable IR (SPEC 14.2)")
	}
	flowID := c.flowID
	if flowID == "" { flowID = "flow" }
	return &PortableFlow{
		SpecVersion: SpecVersion, FlowID: flowID, Portability: "PORTABLE",
		Mode: c.mode, Rules: c.portableRules, Fallback: nil,
		ContractVersion: c.ContractVersion,
	}, nil
}

// ToIRJSON exports canonical Portable IR JSON.
func (c *FlowContract) ToIRJSON() (string, error) {
	pf, err := c.ToIR()
	if err != nil { return "", err }
	return PortableFlowToJSON(pf)
}

func exprJSON(e *PExpr) string {
	if e == nil { return "null" }
	var b strings.Builder
	b.WriteString(`{"op":"` + e.Op + `"`)
	if len(e.Args) > 0 {
		b.WriteString(`,"args":[`)
		for i, a := range e.Args {
			if i > 0 { b.WriteString(",") }
			b.WriteString(exprJSON(a))
		}
		b.WriteString(`]`)
	}
	if e.Value != nil {
		v, _ := json.Marshal(e.Value)
		b.WriteString(`,"value":` + string(v))
	}
	b.WriteString(`}`)
	return b.String()
}

// --- Replay (SPEC 12.6, 12.10, 9.5) ---

// ReplayMode is the replay operation to perform (SPEC 12.6).
type ReplayMode string

const (
	// ReplaySimulation re-executes the decision and compares outcomes.
	ReplaySimulation ReplayMode = "simulation"
	// ReplayHistorical returns the recorded outcome without re-execution.
	ReplayHistorical ReplayMode = "historical"
	// ReplayDecision re-executes and reports semantic equivalence.
	ReplayDecision   ReplayMode = "decision"
	// ReplayEffects re-applies recorded effects (requires authorization).
	ReplayEffects    ReplayMode = "effects"
)

// ReplayError is raised when a replay record cannot be safely replayed.
type ReplayError struct{ msg string }

// Error returns the error message.
func (e *ReplayError) Error() string { return e.msg }
func replayErr(format string, a ...any) *ReplayError {
	return &ReplayError{fmt.Sprintf(format, a...)}
}

// ReplayRecord is a recorded decision tuple (SPEC 12.6, 12.10).
type ReplayRecord struct {
	SpecVersion     string
	ContractVersion string
	Input           any
	ClockWall       int64
	ClockMonotonic  int64
	Outcome         *FlowOutcome
	Trace           *ExecutionTrace
	Effects         []Effect
	Integrity       string
}

// ReplayResult is the result of a replay operation (SPEC 12.6).
type ReplayResult struct {
	Mode           ReplayMode
	Outcome        *FlowOutcome
	Equivalent     *bool
	EffectsApplied int
}

func canonicalPayload(rec *ReplayRecord) string {
	payload := map[string]any{
		"spec_version":     rec.SpecVersion,
		"contract_version": rec.ContractVersion,
		"input":            rec.Input,
		"clock_wall":       rec.ClockWall,
		"clock_monotonic":  rec.ClockMonotonic,
		"outcome": map[string]any{
			"execution_status": string(rec.Outcome.ExecutionStatus),
			"decision_status":  decisionStr(rec.Outcome.DecisionStatus),
			"value":            rec.Outcome.Value,
			"has_recovery":     rec.Outcome.Recovery != nil,
			"interruption_kind": interruptionKind(rec.Outcome.Interruption),
		},
		"effects": rec.Effects,
	}
	b, _ := json.Marshal(payload)
	return string(b)
}

func decisionStr(d *DecisionStatus) any {
	if d == nil { return nil }
	return string(*d)
}

func interruptionKind(i *InterruptionInfo) any {
	if i == nil { return nil }
	return string(i.Kind)
}

// Sign returns a copy of the record with an HMAC-SHA256 integrity tag.
func Sign(rec *ReplayRecord, key []byte) *ReplayRecord {
	mac := hmac.New(sha256.New, key)
	mac.Write([]byte(canonicalPayload(rec)))
	cp := *rec
	cp.Integrity = hex.EncodeToString(mac.Sum(nil))
	return &cp
}

// Record executes with tracing and captures a ReplayRecord (SPEC 12.6).
func Record(c *FlowContract, input any, clock Clock) *ReplayRecord {
	if clock == nil { clock = c.clock }
	outcome := c.TryExecuteWithClock(input, clock, true)
	return &ReplayRecord{
		SpecVersion: SpecVersion, ContractVersion: c.ContractVersion,
		Input: input, ClockWall: clock.Wall(), ClockMonotonic: clock.Monotonic(),
		Outcome: outcome, Trace: outcome.Trace, Effects: outcome.Effects,
	}
}

func verifyIntegrity(rec *ReplayRecord, key []byte) error {
	if rec.Integrity == "" { return nil }
	if key == nil {
		return replayErr("record carries an integrity tag; an integrity_key is required")
	}
	mac := hmac.New(sha256.New, key)
	mac.Write([]byte(canonicalPayload(rec)))
	expected := hex.EncodeToString(mac.Sum(nil))
	if !hmac.Equal([]byte(expected), []byte(rec.Integrity)) {
		return replayErr("replay record integrity check failed")
	}
	return nil
}

func checkVersions(rec *ReplayRecord, c *FlowContract) error {
	if rec.SpecVersion != SpecVersion {
		return replayErr("record spec_version %q does not match current %q; replay fails closed (SPEC 9.5)", rec.SpecVersion, SpecVersion)
	}
	if rec.ContractVersion != c.ContractVersion {
		return replayErr("record contract_version does not match the current contract; replay fails closed (SPEC 12.6)")
	}
	return nil
}

func semanticallyEquivalent(a, b *FlowOutcome) bool {
	if a.ExecutionStatus != b.ExecutionStatus { return false }
	if !decisionEq(a.DecisionStatus, b.DecisionStatus) { return false }
	if fmt.Sprint(a.Value) != fmt.Sprint(b.Value) { return false }
	if (a.Recovery == nil) != (b.Recovery == nil) { return false }
	if a.Recovery != nil && b.Recovery != nil && a.Recovery.HandlerRuleID != b.Recovery.HandlerRuleID {
		return false
	}
	return interruptionKind(a.Interruption) == interruptionKind(b.Interruption)
}

func decisionEq(a, b *DecisionStatus) bool {
	if a == nil || b == nil { return a == b }
	return *a == *b
}

// Replay replays a recorded decision (SPEC 12.6).
func Replay(rec *ReplayRecord, c *FlowContract, mode ReplayMode,
	key []byte, effectExecutor func(Effect), authorizeEffects bool) (*ReplayResult, error) {
	if err := verifyIntegrity(rec, key); err != nil { return nil, err }
	if err := checkVersions(rec, c); err != nil { return nil, err }

	switch mode {
	case ReplayHistorical:
		return &ReplayResult{Mode: mode, Outcome: rec.Outcome}, nil
	case ReplaySimulation, ReplayDecision:
		clock := &FakeClock{wallMs: rec.ClockWall, monoMs: rec.ClockMonotonic}
		outcome := c.SimulateWithClock(rec.Input, clock)
		eq := semanticallyEquivalent(outcome, rec.Outcome)
		return &ReplayResult{Mode: mode, Outcome: outcome, Equivalent: &eq}, nil
	case ReplayEffects:
		if !authorizeEffects {
			return nil, replayErr("effect re-execution requires explicit authorization (authorize_effects=true)")
		}
		if effectExecutor == nil {
			return nil, replayErr("EFFECTS mode requires an effect_executor")
		}
		applied := 0
		for _, e := range rec.Effects { effectExecutor(e); applied++ }
		return &ReplayResult{Mode: mode, EffectsApplied: applied}, nil
	}
	return nil, replayErr("unknown replay mode: %s", mode)
}

// --- Shadow (SPEC 12.7) ---

// ShadowEntry is one shadow-comparison entry (SPEC 12.7).
type ShadowEntry struct {
	Index            int
	Input            any
	Current          *FlowOutcome
	Candidate        *FlowOutcome
	Differs          bool
	DifferingFields  []string
}

// ShadowReport is the shadow comparison report (SPEC 12.7).
type ShadowReport struct {
	Entries     []ShadowEntry
	Total       int
	Differences int
}

func diffFields(a, b *FlowOutcome) []string {
	var fields []string
	if a.ExecutionStatus != b.ExecutionStatus { fields = append(fields, "execution_status") }
	if !decisionEq(a.DecisionStatus, b.DecisionStatus) { fields = append(fields, "decision_status") }
	if fmt.Sprint(a.Value) != fmt.Sprint(b.Value) { fields = append(fields, "value") }
	if (a.Recovery == nil) != (b.Recovery == nil) { fields = append(fields, "recovery") }
	if interruptionKind(a.Interruption) != interruptionKind(b.Interruption) {
		fields = append(fields, "interruption")
	}
	return fields
}

// Shadow compares a candidate flow against the current flow (SPEC 12.7).
// Both flows are simulated (no effects, hooks, or finalizers).
// An optional clock may be supplied for deterministic comparison.
func Shadow(current, candidate *FlowContract, inputs []any, clock ...Clock) *ShadowReport {
	var clk Clock
	if len(clock) > 0 { clk = clock[0] }
	report := &ShadowReport{}
	for i, inp := range inputs {
		var co, cand *FlowOutcome
		if clk != nil {
			co = current.SimulateWithClock(inp, clk)
			cand = candidate.SimulateWithClock(inp, clk)
		} else {
			co = current.Simulate(inp)
			cand = candidate.Simulate(inp)
		}
		fields := diffFields(co, cand)
		report.Entries = append(report.Entries, ShadowEntry{
			Index: i, Input: inp, Current: co, Candidate: cand,
			Differs: len(fields) > 0, DifferingFields: fields,
		})
	}
	report.Total = len(report.Entries)
	for _, e := range report.Entries {
		if e.Differs { report.Differences++ }
	}
	return report
}

// sortedKeys helper retained for deterministic payloads.
