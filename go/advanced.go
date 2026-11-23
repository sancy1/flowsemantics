package flowsemantics

import (
	"fmt"
	"strings"
	"time"
)

// Advanced composition & analysis — SPEC 10.7 (merge), 10.8 (decision
// table), 12.9 (effective dates), 12.8 (validate depth), 12.5
// (simulate batch), 4.4 (portability report).

// --- Merge (SPEC 10.7) ---------------------------------------------------

// Merge splices another flow's rules, catches, and finalizers at the
// call site. Both flows must share the same EvaluationMode; RuleIds
// must be unique across the combined flow; the outer (self) fallback
// wins when both flows define one.
func (f *Flow) Merge(other *Flow) (*Flow, error) {
	if other.mode != f.mode {
		return nil, NewStructureError(fmt.Sprintf(
			"cannot merge flows with different EvaluationMode: %s vs %s (SPEC 10.7)", f.mode, other.mode))
	}
	existing := map[string]bool{}
	for _, r := range f.rules { existing[r.ID] = true }
	for _, r := range other.rules {
		if existing[r.ID] {
			return nil, NewStructureError(fmt.Sprintf(
				"merge would produce duplicate RuleId: %s (SPEC 10.7)", r.ID))
		}
		existing[r.ID] = true
	}
	f.rules = append(f.rules, other.rules...)
	f.catches = append(f.catches, other.catches...)
	f.finalizers = append(f.finalizers, other.finalizers...)
	f.hooks = append(f.hooks, other.hooks...)
	if f.fallback == nil && other.fallback != nil {
		f.fallback = other.fallback
	}
	return f, nil
}

// MergeContract splices a compiled FlowContract's rules, catches, and
// finalizers at the call site (SPEC 10.7). Same mode/uniqueness rules
// as Merge.
func (f *Flow) MergeContract(c *FlowContract) (*Flow, error) {
	if c.mode != f.mode {
		return nil, NewStructureError(fmt.Sprintf(
			"cannot merge flows with different EvaluationMode: %s vs %s (SPEC 10.7)", f.mode, c.mode))
	}
	existing := map[string]bool{}
	for _, r := range f.rules { existing[r.ID] = true }
	for _, r := range c.rules {
		if existing[r.ID] {
			return nil, NewStructureError(fmt.Sprintf(
				"merge would produce duplicate RuleId: %s (SPEC 10.7)", r.ID))
		}
		existing[r.ID] = true
	}
	f.rules = append(f.rules, c.rules...)
	f.catches = append(f.catches, c.catches...)
	f.finalizers = append(f.finalizers, c.finalizers...)
	f.hooks = append(f.hooks, c.hooks...)
	if f.fallback == nil && c.fallback != nil {
		f.fallback = c.fallback
	}
	return f, nil
}

// --- DecisionTable (SPEC 10.8) -------------------------------------------

// HitPolicy is the hit policy for a decision table (SPEC 10.8).
type HitPolicy string

const (
	// HitFirst returns the first matching row.
	HitFirst     HitPolicy = "FIRST"
	// HitCollect returns all matching rows.
	HitCollect   HitPolicy = "COLLECT"
	// HitPriority returns the highest-priority matching row.
	HitPriority  HitPolicy = "PRIORITY"
	// HitUnique requires exactly one matching row.
	HitUnique    HitPolicy = "UNIQUE"
)

// DecisionTableRow is one row of a decision table (SPEC 10.8).
type DecisionTableRow struct {
	ID         string
	Conditions []ConditionFn // ALL must be true
	Action     ActionFn
	Priority   int
}

// DecisionTable is a decision table: rows of conditions + action with a
// hit policy (SPEC 10.8).
type DecisionTable struct {
	Rows        []DecisionTableRow
	Policy      HitPolicy
	InputFields []string
	Warnings    []string
}

func hitPolicyToMode(p HitPolicy) (EvaluationMode, error) {
	switch p {
	case HitFirst, HitUnique:
		return FirstMatch, nil
	case HitCollect:
		return AllMatch, nil
	case HitPriority:
		return Priority, nil
	default:
		return "", NewStructureError(fmt.Sprintf("unknown hit policy: %q", p))
	}
}

// TableToFlow compiles a DecisionTable into a Flow builder. Each row
// becomes a when rule whose condition is the conjunction of the row's
// column predicates (SPEC 10.8).
func TableToFlow(t *DecisionTable) (*Flow, error) {
	if len(t.Rows) == 0 {
		return nil, NewStructureError("decision table must have at least one row")
	}
	mode, err := hitPolicyToMode(t.Policy)
	if err != nil { return nil, err }
	flow := NewFlow().WithMode(mode)
	for i, row := range t.Rows {
		id := row.ID
		if id == "" { id = fmt.Sprintf("row%d", i) }
		conds := append([]ConditionFn(nil), row.Conditions...)
		cond := func(input any) (bool, error) {
			for _, c := range conds {
				ok, err := c(input)
				if err != nil || !ok { return ok, err }
			}
			return true, nil
		}
		flow.When(cond, row.Action, WithRuleID(id), WithPriority(row.Priority))
	}
	return flow, nil
}

// --- Effective dates (SPEC 12.9) -----------------------------------------

// ParseEffective parses an ISO-8601 timestamp into epoch ms for use with
// WithEffectiveFrom/WithEffectiveUntil. Empty string means unset.
func ParseEffective(s string) (*int64, error) {
	if s == "" { return nil, nil }
	t, err := time.Parse(time.RFC3339, s)
	if err != nil { return nil, fmt.Errorf("invalid effective date %q: %w", s, err) }
	ms := t.UnixMilli()
	return &ms, nil
}

// WithEffectiveFrom gates a rule to inputs evaluated at or after the
// given epoch-ms timestamp (inclusive).
func WithEffectiveFrom(ms int64) RuleOpt {
	return func(r *Rule) { r.EffectiveFrom = &ms }
}

// WithEffectiveUntil gates a rule to inputs evaluated before the given
// epoch-ms timestamp (exclusive).
func WithEffectiveUntil(ms int64) RuleOpt {
	return func(r *Rule) { r.EffectiveUntil = &ms }
}

// isEffective reports whether the rule is active at wall-clock ms.
// Inclusive of EffectiveFrom, exclusive of EffectiveUntil (SPEC 12.9).
func (r *Rule) isEffective(now int64) bool {
	if r.EffectiveFrom != nil && now < *r.EffectiveFrom { return false }
	if r.EffectiveUntil != nil && now >= *r.EffectiveUntil { return false }
	return true
}

// --- Cooperative cancellation (SPEC 11.6.1) ------------------------------

// CancelCheck is polled between rules; returning true produces a
// CANCELLED outcome with InterruptionInfo (cooperative cancellation).
type CancelCheck func() bool

// WithCancelCheck installs a cooperative cancellation poll on the flow.
func (f *Flow) WithCancelCheck(check CancelCheck) *Flow {
	f.cancelCheck = check
	return f
}

// --- Simulate batch (SPEC 12.5) ------------------------------------------

// SimulateReport is the firing-distribution report from batch simulation (SPEC 12.5).
type SimulateReport struct {
	Total        int
	ByStatus     map[string]int
	ByDecision   map[string]int
	ByValue      map[string]int
	Outcomes     []*FlowOutcome
}

// SimulateBatch evaluates representative inputs with no side effects,
// producing a firing distribution report (SPEC 12.5).
func (c *FlowContract) SimulateBatch(inputs []any) *SimulateReport {
	rep := &SimulateReport{
		Total: len(inputs),
		ByStatus: map[string]int{}, ByDecision: map[string]int{}, ByValue: map[string]int{},
		Outcomes: make([]*FlowOutcome, 0, len(inputs)),
	}
	for _, in := range inputs {
		o := c.Simulate(in)
		rep.Outcomes = append(rep.Outcomes, o)
		rep.ByStatus[string(o.ExecutionStatus)]++
		d := "null"
		if o.DecisionStatus != nil { d = string(*o.DecisionStatus) }
		rep.ByDecision[d]++
		rep.ByValue[fmt.Sprint(o.Value)]++
	}
	return rep
}

// --- Portability report (SPEC 4.4) ---------------------------------------

// Portability returns the contract's classification ("PORTABLE" or
// "NATIVE") plus the list of components that make it NATIVE.
func (c *FlowContract) Portability() (string, []string) {
	if !c.hasPortable { return "NATIVE", []string{"native rules"} }
	var offenders []string
	if len(c.catches) > 0 { offenders = append(offenders, "catches") }
	if len(c.finalizers) > 0 { offenders = append(offenders, "finalizers") }
	if len(c.hooks) > 0 { offenders = append(offenders, "hooks") }
	if len(offenders) == 0 { return "PORTABLE", nil }
	return "NATIVE", offenders
}

// parseEffectivePtr parses an ISO-8601 effective-date string (as carried
// by PortableRule) into epoch ms.
func parseEffectivePtr(s *string) *int64 {
	if s == nil || *s == "" { return nil }
	t, err := time.Parse(time.RFC3339, *s)
	if err != nil { return nil }
	ms := t.UnixMilli()
	return &ms
}

var _ = strings.TrimSpace // keep strings import if unused elsewhere
