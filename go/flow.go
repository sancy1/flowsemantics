package flowsemantics

import "fmt"

// ConditionFn returns true when the rule holds (SPEC 10.2).
type ConditionFn func(input any) (bool, error)
// ActionFn produces the rule's value (SPEC 10.2).
type ActionFn func(input any, previous any) (any, error)
// GuardFn is an additional gate evaluated after the condition (SPEC 10.1).
type GuardFn func(input any) (bool, error)
// ExceptionHandler receives (input, exception) and returns a recovery value (SPEC 11.1).
type ExceptionHandler func(input any, exc any) (any, error)
// ExceptionPredicate decides whether a catch rule applies (SPEC 11.2).
type ExceptionPredicate func(input any, exc any) (bool, error)
// HookFn is invoked after each when/when_not action (SPEC 11.5).
type HookFn func(input any, ruleID string, value any)
// CleanupFn is a finalizer invoked for every outcome (SPEC 11.8, 16.1).
type CleanupFn func(ctx *FinallyContext) error

// FinallyContext is passed to a finalizer (SPEC 16.1).
type FinallyContext struct {
	Result            *FlowOutcome
	Status            ExecutionStatus
	Value             any
	Exception         any
	Context           any
	CancellationToken struct{ Cancelled bool }
}

// Rule is one rule in a flow (SPEC 10.2).
type Rule struct {
	ID            string
	Kind          string // when | when_not | then
	Condition     ConditionFn
	Guard         GuardFn
	Action        ActionFn
	Priority      int
	Effects       []Effect
	EffectiveFrom *int64 // epoch ms, inclusive (SPEC 12.9)
	EffectiveUntil *int64 // epoch ms, exclusive
}

// CatchRule is one exception handler in a flow (SPEC 11.1).
type CatchRule struct {
	Kind      string // typed | when | any | rethrow
	ExcType   any    // error type marker: "Kind.Timeout" etc or Go type
	Predicate ExceptionPredicate
	Handler   ExceptionHandler
	ID        string
}

// Fallback is the no-match fallback (SPEC 10.4).
type Fallback struct {
	Kind   string // otherwise | default_if_no_match
	Action ActionFn
	Value  any
}

// Flow is the flow builder (SPEC 7, 10, 11, 16).
type Flow struct {
	rules           []Rule
	catches         []CatchRule
	hooks           []HookFn
	finalizers      []CleanupFn
	mode            EvaluationMode
	fallback        *Fallback
	finallyPolicy   FinallyFailurePolicy
	finallyTimeout  int64
	traceEnabled    bool
	portableRules   []PortableRule
	hasPortable     bool
	portableFlow    *PortableFlow
	cancelCheck     CancelCheck
	flowID          string
	clock           Clock
	diagnosticHook  DiagnosticHook
}

// NewFlow creates a new empty flow builder (FirstMatch mode).
func NewFlow() *Flow {
	return &Flow{mode: FirstMatch, finallyPolicy: PreservePrimary}
}

// WithMode sets the evaluation mode (SPEC 10.6).
func (f *Flow) WithMode(m EvaluationMode) *Flow { f.mode = m; return f }
// WithFlowID sets the flow identifier carried into Portable IR export (SPEC 14.2).
func (f *Flow) WithFlowID(id string) *Flow { f.flowID = id; return f }
// WithClock injects a deterministic clock used for all timestamps (SPEC 6.2).
func (f *Flow) WithClock(clock Clock) *Flow { f.clock = clock; return f }

// When registers a positive condition rule (SPEC 10.2).
func (f *Flow) When(cond ConditionFn, action ActionFn, opts ...RuleOpt) *Flow {
	r := Rule{ID: fmt.Sprintf("r%d", len(f.rules)), Kind: "when", Condition: cond, Action: action}
	for _, o := range opts { o(&r) }
	f.rules = append(f.rules, r)
	return f
}

// WhenNot registers a negated condition rule (SPEC 10.2).
func (f *Flow) WhenNot(cond ConditionFn, action ActionFn, opts ...RuleOpt) *Flow {
	r := Rule{ID: fmt.Sprintf("r%d", len(f.rules)), Kind: "when_not", Condition: cond, Action: action}
	for _, o := range opts { o(&r) }
	f.rules = append(f.rules, r)
	return f
}

// Then registers a sequential transformation stage (SPEC 10.5).
func (f *Flow) Then(action ActionFn, opts ...RuleOpt) *Flow {
	r := Rule{ID: fmt.Sprintf("t%d", len(f.rules)), Kind: "then", Action: action}
	for _, o := range opts { o(&r) }
	f.rules = append(f.rules, r)
	return f
}

// Otherwise registers an otherwise fallback action (SPEC 10.4).
func (f *Flow) Otherwise(action ActionFn) *Flow {
	f.fallback = &Fallback{Kind: "otherwise", Action: action}
	return f
}

// Default is a convenience alias for DefaultIfNoMatch (SPEC 10.4).
func (f *Flow) Default(value any) *Flow { return f.DefaultIfNoMatch(value) }

// DefaultIfNoMatch registers a default_if_no_match fallback value (SPEC 10.4).
func (f *Flow) DefaultIfNoMatch(value any) *Flow {
	f.fallback = &Fallback{Kind: "default_if_no_match", Value: value}
	return f
}

// Catch registers a typed catch rule (SPEC 11.1).
func (f *Flow) Catch(excKind string, handler ExceptionHandler, opts ...CatchOpt) *Flow {
	c := CatchRule{Kind: "typed", ExcType: excKind, Handler: handler}
	for _, o := range opts { o(&c) }
	f.catches = append(f.catches, c)
	return f
}

// CatchWhen registers a catch rule with a predicate (SPEC 11.2).
func (f *Flow) CatchWhen(excKind string, pred ExceptionPredicate, handler ExceptionHandler, opts ...CatchOpt) *Flow {
	c := CatchRule{Kind: "when", ExcType: excKind, Predicate: pred, Handler: handler}
	for _, o := range opts { o(&c) }
	f.catches = append(f.catches, c)
	return f
}

// CatchAny registers a catch-all rule; must follow typed catches (SPEC 11.3).
func (f *Flow) CatchAny(handler ExceptionHandler, opts ...CatchOpt) *Flow {
	c := CatchRule{Kind: "any", Handler: handler}
	for _, o := range opts { o(&c) }
	f.catches = append(f.catches, c)
	return f
}

// Rethrow registers a rethrow marker that stops catch routing (SPEC 11.4).
func (f *Flow) Rethrow() *Flow {
	f.catches = append(f.catches, CatchRule{Kind: "rethrow"})
	return f
}

// OnMatch registers a match hook invoked after each when/when_not action (SPEC 11.5).
func (f *Flow) OnMatch(hook HookFn) *Flow { f.hooks = append(f.hooks, hook); return f }

// Finally registers a finalizer invoked for every outcome (SPEC 11.8, 16.1).
func (f *Flow) Finally(cleanup CleanupFn) *Flow { f.finalizers = append(f.finalizers, cleanup); return f }

// WithFinallyPolicy sets the finalizer failure policy (SPEC 16.3).
func (f *Flow) WithFinallyPolicy(p FinallyFailurePolicy) *Flow { f.finallyPolicy = p; return f }
// WithFinallyTimeout sets the finalizer cleanup budget in milliseconds (SPEC 16.7).
func (f *Flow) WithFinallyTimeout(ms int64) *Flow { f.finallyTimeout = ms; return f }
// WithTrace enables trace collection, optionally with a diagnostic hook (SPEC 12.2, 12.3).
func (f *Flow) WithTrace(hook ...DiagnosticHook) *Flow {
	f.traceEnabled = true
	if len(hook) > 0 { f.diagnosticHook = hook[0] }
	return f
}

// Portable IR builders.
// WhenExpr registers a portable when rule (SPEC 14.2).
func (f *Flow) WhenExpr(cond, transform *PExpr, opts ...PortableRuleOpt) *Flow {
	f.hasPortable = true
	pr := PortableRule{
		RuleID: fmt.Sprintf("p%d", len(f.portableRules)), Kind: "when",
		Condition: cond, Transform: transform,
	}
	for _, o := range opts { o(&pr) }
	f.portableRules = append(f.portableRules, pr)
	return f
}

// WhenNotExpr registers a portable when_not rule (SPEC 14.2).
func (f *Flow) WhenNotExpr(cond, transform *PExpr, opts ...PortableRuleOpt) *Flow {
	f.hasPortable = true
	pr := PortableRule{
		RuleID: fmt.Sprintf("p%d", len(f.portableRules)), Kind: "when_not",
		Condition: cond, Transform: transform,
	}
	for _, o := range opts { o(&pr) }
	f.portableRules = append(f.portableRules, pr)
	return f
}

// PortableRuleOpt configures a portable-IR rule (SPEC 14.2).
type PortableRuleOpt func(*PortableRule)

// WithPRuleID sets the rule ID for a portable rule.
func WithPRuleID(id string) PortableRuleOpt { return func(r *PortableRule) { r.RuleID = id } }
// WithPEffects sets the proposed effects for a portable rule.
func WithPEffects(effects []Effect) PortableRuleOpt { return func(r *PortableRule) { r.Effects = effects } }
// WithPPriority sets the evaluation priority for a portable rule.
func WithPPriority(p int) PortableRuleOpt { return func(r *PortableRule) { r.Priority = p } }

// FlowFromIR builds a Flow from a Portable IR document (SPEC 14.2).
func FlowFromIR(ir any) (*Flow, error) {
	pf, err := PortableFlowFromDict(ir)
	if err != nil { return nil, err }
	f := NewFlow().WithMode(pf.Mode)
	f.portableFlow = pf
	f.hasPortable = true
	for _, pr := range pf.Rules {
		cond := pr.Condition
		tr := pr.Transform
		if pr.Kind == "when" {
			f.WhenExpr(cond, tr)
		} else {
			f.WhenNotExpr(cond, tr)
		}
		// copy id/effects onto last portable rule
		last := &f.portableRules[len(f.portableRules)-1]
		last.RuleID = pr.RuleID
		last.Priority = pr.Priority
		last.Effects = pr.Effects
	}
	if pf.Fallback != nil {
		if pf.Fallback["kind"] == "default_if_no_match" {
			f.DefaultIfNoMatch(pf.Fallback["value"])
		}
	}
	return f, nil
}

// RuleOpt configures a native rule.
type RuleOpt func(*Rule)
// WithRuleID sets the rule ID.
func WithRuleID(id string) RuleOpt { return func(r *Rule) { r.ID = id } }
// WithGuard sets the guard callback.
func WithGuard(g GuardFn) RuleOpt { return func(r *Rule) { r.Guard = g } }
// WithPriority sets the evaluation priority.
func WithPriority(p int) RuleOpt { return func(r *Rule) { r.Priority = p } }
// WithEffects sets the proposed effects.
func WithEffects(effects []Effect) RuleOpt { return func(r *Rule) { r.Effects = effects } }

// CatchOpt configures a catch rule.
type CatchOpt func(*CatchRule)
// WithCatchID sets the catch rule ID.
func WithCatchID(id string) CatchOpt { return func(c *CatchRule) { c.ID = id } }

// FlowContract is a compiled, immutable flow contract (SPEC 4.1, 10.9).
type FlowContract struct {
	rules          []Rule
	mode           EvaluationMode
	fallback       *Fallback
	catches        []CatchRule
	hooks          []HookFn
	finalizers     []CleanupFn
	finallyPolicy  FinallyFailurePolicy
	finallyTimeout int64
	traceEnabled   bool
	clock          Clock
	cancelCheck    CancelCheck
	ContractVersion string
	hasPortable    bool
	portableRules  []PortableRule
	flowID         string
	diagnosticHook DiagnosticHook
}

// Compile compiles the builder into an immutable FlowContract (SPEC 4.3, 10.9).
func (f *Flow) Compile() (*FlowContract, error) {
	// catch_any ordering (SPEC 11.3)
	for i, c := range f.catches {
		if c.Kind == "any" {
			for _, later := range f.catches[i+1:] {
				if later.Kind != "rethrow" {
					return nil, NewStructureError("catch_any must be registered after typed catches")
				}
			}
		}
	}
	var rules []Rule
	if f.hasPortable {
		for _, pr := range f.portableRules {
			cond := pr.Condition
			tr := pr.Transform
			rules = append(rules, Rule{
				ID: pr.RuleID, Kind: pr.Kind,
				Condition: func(input any) (bool, error) {
					v, err := EvalExpr(cond, input)
					return truthy(v), err
				},
				Action: func(input any, prev any) (any, error) {
					return EvalExpr(tr, input)
				},
				Priority: pr.Priority,
				Effects:  pr.Effects,
				EffectiveFrom:  parseEffectivePtr(pr.EffectiveFrom),
				EffectiveUntil: parseEffectivePtr(pr.EffectiveUntil),
			})
		}
	} else {
		rules = append([]Rule(nil), f.rules...)
	}
	// effective date validation (SPEC 12.9)
	for _, r := range rules {
		if r.EffectiveFrom != nil && r.EffectiveUntil != nil && *r.EffectiveFrom >= *r.EffectiveUntil {
			return nil, NewStructureError(fmt.Sprintf(
				"rule %s: effective_from must be before effective_until (SPEC 12.9)", r.ID))
		}
	}
	// duplicate RuleId validation (SPEC 4.3)
	seen := map[string]bool{}
	for _, r := range rules {
		if seen[r.ID] {
			return nil, NewStructureError(fmt.Sprintf("duplicate RuleId: %s (SPEC 4.3)", r.ID))
		}
		seen[r.ID] = true
	}
	cv := ContractVersion(rules, f.fallback, f.mode,
		append([]CatchRule(nil), f.catches...), len(f.finalizers),
		f.finallyPolicy, f.finallyTimeout, f.traceEnabled)
	clk := f.clock
	if clk == nil { clk = SystemClock{} }
	return &FlowContract{
		rules: rules, mode: f.mode, fallback: f.fallback,
		catches: append([]CatchRule(nil), f.catches...),
		hooks: append([]HookFn(nil), f.hooks...),
		finalizers: append([]CleanupFn(nil), f.finalizers...),
		finallyPolicy: f.finallyPolicy,
		finallyTimeout: f.finallyTimeout,
		traceEnabled: f.traceEnabled,
		clock: clk,
		cancelCheck: f.cancelCheck,
		ContractVersion: cv,
		hasPortable: f.hasPortable,
		portableRules: append([]PortableRule(nil), f.portableRules...),
		flowID: f.flowID,
		diagnosticHook: f.diagnosticHook,
	}, nil
}

// Clock returns the clock injected at build time.
func (c *FlowContract) Clock() Clock { return c.clock }

func emptyOutcome(status ExecutionStatus) *FlowOutcome {
	return &FlowOutcome{
		ExecutionStatus: status,
		SecondaryExceptions: []any{},
		Effects: []Effect{},
	}
}

// TryExecute executes and always returns a FlowOutcome (SPEC 11.4).
func (c *FlowContract) TryExecute(input any) *FlowOutcome {
	return c.tryExecute(input, c.clock, c.traceEnabled)
}

// TryExecuteWithClock executes with an explicit clock and trace flag (SPEC 11.4, 12.3).
func (c *FlowContract) TryExecuteWithClock(input any, clock Clock, trace bool) *FlowOutcome {
	return c.tryExecute(input, clock, trace)
}

// Execute propagates an unrecovered exception as an error (SPEC 11.4, D13).
func (c *FlowContract) Execute(input any) (*FlowOutcome, error) {
	outcome := c.TryExecute(input)
	if outcome.ExecutionStatus == Failed && outcome.PrimaryException != nil {
		if err, ok := outcome.PrimaryException.(error); ok {
			return outcome, err
		}
		return outcome, fmt.Errorf("%v", outcome.PrimaryException)
	}
	return outcome, nil
}

// ExecuteAsync — goroutine wrapper; Go has no awaitables so parity is
// structural (SPEC 11.7 equivalent).
func (c *FlowContract) ExecuteAsync(input any) *FlowOutcome {
	return c.TryExecute(input)
}

func (c *FlowContract) tryExecute(input any, clock Clock, trace bool) *FlowOutcome {
	if clock == nil {
		clock = c.clock
	}
	var rec *ExecutionTrace
	if trace {
		rec = &ExecutionTrace{ContractVersion: c.ContractVersion, DiagnosticHook: c.diagnosticHook}
	}
	primary := c.primary(input, clock, rec)
	outcome := c.finalize(input, clock, primary, rec)
	if rec != nil { outcome.Trace = rec }
	return outcome
}

func (c *FlowContract) orderedRules() []Rule {
	rules := append([]Rule(nil), c.rules...)
	if c.mode == Priority {
		// stable sort by priority desc
		for i := 0; i < len(rules); i++ {
			for j := i + 1; j < len(rules); j++ {
				if rules[j].Priority > rules[i].Priority {
					rules[i], rules[j] = rules[j], rules[i]
				}
			}
		}
	}
	return rules
}

func (c *FlowContract) primary(input any, clock Clock, rec *ExecutionTrace) *FlowOutcome {
	outcome, err := c.evaluate(input, clock, rec)
	if err == nil { return outcome }
	if _, ok := err.(*KindCancelled); ok {
		if rec != nil { rec.Emit(EvCancelledObserved, "", "", clock.Wall()) }
		o := emptyOutcome(Cancelled)
		o.Interruption = &InterruptionInfo{Kind: InterruptedCancelled, Source: "host", Timestamp: clock.Wall()}
		o.PrimaryException = err
		return o
	}
	if _, ok := err.(*KindTimeout); ok {
		if rec != nil { rec.Emit(EvTimedOutObserved, "", "", clock.Wall()) }
		o := emptyOutcome(TimedOut)
		o.Interruption = &InterruptionInfo{Kind: InterruptedTimedOut, Source: "external", Timestamp: clock.Wall()}
		o.PrimaryException = err
		return o
	}
	return c.handleException(input, clock, err, rec)
}

func (c *FlowContract) evaluate(input any, clock Clock, rec *ExecutionTrace) (*FlowOutcome, error) {
	rules := c.orderedRules()
	var secondary []any
	var effects []Effect
	matched := false
	var value any

	for _, rule := range rules {
		if c.cancelCheck != nil && c.cancelCheck() {
			return nil, &KindCancelled{}
		}
		if rule.Kind == "then" {
			if !matched { continue }
			v, err := rule.Action(input, value)
			if err != nil {
				if rec != nil { rec.Emit(EvActionRaised, rule.ID, "", clock.Wall()) }
				return nil, err
			}
			value = v
			if rec != nil { rec.Emit(EvActionExecuted, rule.ID, "", clock.Wall()) }
			effects = append(effects, rule.Effects...)
			if len(rule.Effects) > 0 && rec != nil { rec.Emit(EvEffectProposed, rule.ID, "", clock.Wall()) }
			continue
		}
		if matched && c.mode != AllMatch {
			if rec != nil { rec.Emit(EvSkippedByShortCircuit, rule.ID, "", clock.Wall()) }
			continue
		}
		if !rule.isEffective(clock.Wall()) {
			if rec != nil { rec.Emit(EvRuleSkipped, rule.ID, ReasonNotEffective, clock.Wall()) }
			continue
		}
		condResult, err := rule.Condition(input)
		if err != nil {
			if rec != nil { rec.Emit(EvConditionRaised, rule.ID, "", clock.Wall()) }
			return nil, err
		}
		if rec != nil { rec.Emit(EvConditionEvaluated, rule.ID, "", clock.Wall()) }
		holds := condResult
		if rule.Kind == "when_not" { holds = !holds }
		skipReason := Reason("")
		if rule.Guard != nil {
			g, gerr := rule.Guard(input)
			if rec != nil { rec.Emit(EvGuardEvaluated, rule.ID, "", clock.Wall()) }
			if gerr != nil { return nil, gerr }
			if !g { holds = false; skipReason = ReasonGuardBlocked }
		}
		if !holds && skipReason == "" { skipReason = ReasonConditionFalse }
		if !holds {
			if skipReason != "" && rec != nil { rec.Emit(EvRuleSkipped, rule.ID, skipReason, clock.Wall()) }
			continue
		}
		matched = true
		v, err := rule.Action(input, nil)
		if err != nil {
			if rec != nil { rec.Emit(EvActionRaised, rule.ID, "", clock.Wall()) }
			return nil, err
		}
		value = v
		if rec != nil { rec.Emit(EvActionExecuted, rule.ID, "", clock.Wall()) }
		effects = append(effects, rule.Effects...)
		if len(rule.Effects) > 0 && rec != nil { rec.Emit(EvEffectProposed, rule.ID, "", clock.Wall()) }
		for _, hook := range c.hooks {
			func() {
				defer func() {
					if r := recover(); r != nil {
						secondary = append(secondary, r)
						if rec != nil { rec.Emit(EvHookRaised, rule.ID, "", clock.Wall()) }
					}
				}()
				hook(input, rule.ID, value)
				if rec != nil { rec.Emit(EvHookInvoked, rule.ID, "", clock.Wall()) }
			}()
		}
	}

	if matched {
		approved := Approved
		return &FlowOutcome{
			ExecutionStatus: Completed, DecisionStatus: &approved, Value: value,
			SecondaryExceptions: secondary, Effects: effects,
		}, nil
	}
	if c.fallback != nil {
		if c.fallback.Kind == "otherwise" && c.fallback.Action != nil {
			fb, err := c.fallback.Action(input, nil)
			if err != nil { return nil, err }
			nm := NoMatch
			return &FlowOutcome{ExecutionStatus: Completed, DecisionStatus: &nm, Value: fb, SecondaryExceptions: secondary, Effects: effects}, nil
		}
		if c.fallback.Kind == "default_if_no_match" {
			nm := NoMatch
			return &FlowOutcome{ExecutionStatus: Completed, DecisionStatus: &nm, Value: c.fallback.Value, SecondaryExceptions: secondary, Effects: effects}, nil
		}
	}
	nm := NoMatch
	return &FlowOutcome{ExecutionStatus: Completed, DecisionStatus: &nm, Value: nil, SecondaryExceptions: secondary, Effects: effects}, nil
}

func (c *FlowContract) handleException(input any, clock Clock, exc error, rec *ExecutionTrace) *FlowOutcome {
	current := exc
	for _, cr := range c.catches {
		if cr.Kind == "rethrow" {
			if rec != nil { rec.Emit(EvRethrowReached, "", "", clock.Wall()) }
			break
		}
		if cr.Kind == "any" {
			if rec != nil { rec.Emit(EvCatchMatched, cr.ID, "", clock.Wall()) }
			v, herr := cr.Handler(input, current)
			if herr != nil { current = herr; continue }
			if rec != nil { rec.Emit(EvCatchHandled, cr.ID, "", clock.Wall()) }
			return &FlowOutcome{
				ExecutionStatus: Completed, Value: v,
				Recovery: &RecoveryInfo{OriginalException: current, HandlerRuleID: cr.ID, RecoveredAt: clock.Wall()},
			}
		}
		// typed / when — match by KindOfException
		if KindOfException(current) != fmt.Sprint(cr.ExcType) {
			if rec != nil { rec.Emit(EvCatchDeclined, cr.ID, "", clock.Wall()) }
			continue
		}
		if cr.Kind == "when" && cr.Predicate != nil {
			if rec != nil { rec.Emit(EvCatchPredicateEvaluated, cr.ID, "", clock.Wall()) }
			pred, perr := cr.Predicate(input, current)
			if perr != nil {
				if rec != nil { rec.Emit(EvCatchPredicateRaised, cr.ID, "", clock.Wall()) }
				current = perr
				continue
			}
			if !pred {
				if rec != nil { rec.Emit(EvCatchDeclined, cr.ID, "", clock.Wall()) }
				continue
			}
		}
		if rec != nil { rec.Emit(EvCatchMatched, cr.ID, "", clock.Wall()) }
		v, herr := cr.Handler(input, current)
		if herr != nil { current = herr; continue }
		if rec != nil { rec.Emit(EvCatchHandled, cr.ID, "", clock.Wall()) }
		return &FlowOutcome{
			ExecutionStatus: Completed, Value: v,
			Recovery: &RecoveryInfo{OriginalException: current, HandlerRuleID: cr.ID, RecoveredAt: clock.Wall()},
		}
	}
	return &FlowOutcome{ExecutionStatus: Failed, PrimaryException: current, SecondaryExceptions: []any{}, Effects: []Effect{}}
}

func (c *FlowContract) finalize(input any, clock Clock, outcome *FlowOutcome, rec *ExecutionTrace) *FlowOutcome {
	if len(c.finalizers) == 0 { return outcome }
	var cleanupExcs []any
	isClean := true
	for i := len(c.finalizers) - 1; i >= 0; i-- {
		fn := c.finalizers[i]
		fctx := &FinallyContext{
			Result: outcome, Status: outcome.ExecutionStatus,
			Value: outcome.Value, Exception: outcome.PrimaryException,
			Context: input,
		}
		if rec != nil { rec.Emit(EvFinallyStarted, "", "", clock.Wall()) }
		func() {
			defer func() {
				if r := recover(); r != nil {
					isClean = false
					cleanupExcs = append(cleanupExcs, r)
					if rec != nil { rec.Emit(EvFinallyRaised, "", "", clock.Wall()) }
				}
			}()
			if err := fn(fctx); err != nil {
				isClean = false
				cleanupExcs = append(cleanupExcs, err)
				if rec != nil { rec.Emit(EvFinallyRaised, "", "", clock.Wall()) }
				return
			}
			if rec != nil { rec.Emit(EvFinallyCompleted, "", "", clock.Wall()) }
		}()
	}
	return c.mergeFinalization(outcome, cleanupExcs, isClean)
}

func (c *FlowContract) mergeFinalization(outcome *FlowOutcome, cleanupExcs []any, isClean bool) *FlowOutcome {
	secondary := append(append([]any{}, outcome.SecondaryExceptions...), cleanupExcs...)
	primaryExc := outcome.PrimaryException
	if c.finallyPolicy == ReplacePrimary &&
		outcome.ExecutionStatus == Failed &&
		outcome.PrimaryException != nil && len(cleanupExcs) > 0 {
		secondary = append(secondary, outcome.PrimaryException)
		primaryExc = cleanupExcs[len(cleanupExcs)-1]
	}
	outcome.SecondaryExceptions = secondary
	outcome.PrimaryException = primaryExc
	outcome.Finalization = &FinalizationInfo{IsClean: isClean, CleanupExceptions: cleanupExcs}
	return outcome
}

// Simulate — SPEC 12.5: no hooks/finalizers/catches.
func (c *FlowContract) Simulate(input any) *FlowOutcome {
	return c.SimulateWithClock(input, c.clock)
}

// SimulateWithClock simulates with an explicit clock (SPEC 12.5).
func (c *FlowContract) SimulateWithClock(input any, clock Clock) *FlowOutcome {
	sim := &FlowContract{
		rules: c.rules, mode: c.mode, fallback: c.fallback,
		catches: nil, hooks: nil, finalizers: nil,
		finallyPolicy: c.finallyPolicy, traceEnabled: false, clock: clock,
		ContractVersion: c.ContractVersion,
		hasPortable: c.hasPortable, portableRules: c.portableRules,
		cancelCheck: c.cancelCheck,
		flowID: c.flowID,
	}
	return sim.TryExecute(input)
}


