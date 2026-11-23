// Package flowsemantics is the Go implementation of FlowSemantics (SPEC 14.5).
// Zero third-party dependencies.
package flowsemantics

// ExecutionStatus — SPEC 3.3.
type ExecutionStatus string

const (
	Completed  ExecutionStatus = "COMPLETED"
	Failed     ExecutionStatus = "FAILED"
	Cancelled  ExecutionStatus = "CANCELLED"
	TimedOut   ExecutionStatus = "TIMED_OUT"
)

// DecisionStatus — SPEC 3.4.
type DecisionStatus string

const (
	Approved DecisionStatus = "APPROVED"
	NoMatch  DecisionStatus = "NO_MATCH"
)

// EvaluationMode — SPEC 10.6.
type EvaluationMode string

const (
	FirstMatch EvaluationMode = "FirstMatch"
	AllMatch   EvaluationMode = "AllMatch"
	Priority   EvaluationMode = "Priority"
)

// FinallyFailurePolicy — SPEC 16.3.
type FinallyFailurePolicy string

const (
	PreservePrimary FinallyFailurePolicy = "PreservePrimary"
	Attach          FinallyFailurePolicy = "Attach"
	ReplacePrimary  FinallyFailurePolicy = "ReplacePrimary"
)

// InterruptionKind — SPEC 11.6.
type InterruptionKind string

const (
	InterruptedCancelled InterruptionKind = "cancelled"
	InterruptedTimedOut  InterruptionKind = "timed_out"
)

// Interruption metadata recorded on an outcome (SPEC 3.3).
type InterruptionInfo struct {
	Kind      InterruptionKind
	Source    string
	Timestamp int64
}

// Recovery metadata recorded when a catch rule recovers (SPEC 3.4).
type RecoveryInfo struct {
	OriginalException any
	HandlerRuleID     string
	RecoveredAt       int64
}

// Finalization metadata recorded on an outcome (SPEC 3.5, 16.4).
type FinalizationInfo struct {
	IsClean           bool
	CleanupExceptions []any
}

// A proposed effect — data only, never applied by the library (SPEC 3.7, 5).
type Effect struct {
	Name    string
	Payload any
}

// The canonical outcome of a flow execution (SPEC 3.6, 7).
type FlowOutcome struct {
	ExecutionStatus      ExecutionStatus
	DecisionStatus       *DecisionStatus
	Value                any
	PrimaryException     any
	Recovery             *RecoveryInfo
	Interruption         *InterruptionInfo
	Finalization         *FinalizationInfo
	SecondaryExceptions  []any
	Effects              []Effect
	Trace                *ExecutionTrace
}

// Trace — SPEC 12.1.
type EventType string

const (
	EvConditionEvaluated      EventType = "condition_evaluated"
	EvConditionRaised         EventType = "condition_raised"
	EvGuardEvaluated          EventType = "guard_evaluated"
	EvActionExecuted          EventType = "action_executed"
	EvActionRaised            EventType = "action_raised"
	EvCatchMatched            EventType = "catch_matched"
	EvCatchPredicateEvaluated EventType = "catch_predicate_evaluated"
	EvCatchPredicateRaised    EventType = "catch_predicate_raised"
	EvCatchHandled            EventType = "catch_handled"
	EvCatchDeclined           EventType = "catch_declined"
	EvRethrowReached          EventType = "rethrow_reached"
	EvHookInvoked             EventType = "hook_invoked"
	EvHookRaised              EventType = "hook_raised"
	EvEffectProposed          EventType = "effect_proposed"
	EvSkippedByShortCircuit   EventType = "skipped_by_short_circuit"
	EvSkippedByMode           EventType = "skipped_by_mode"
	EvFinallyStarted          EventType = "finally_started"
	EvFinallyCompleted        EventType = "finally_completed"
	EvFinallyRaised           EventType = "finally_raised"
	EvCancelledObserved       EventType = "cancelled_observed"
	EvTimedOutObserved        EventType = "timed_out_observed"
	EvRuleSkipped             EventType = "rule_skipped"
)

// Reason — skip/failure reason vocabulary (SPEC 12.1).
type Reason string

const (
	ReasonConditionFalse Reason = "condition_false"
	ReasonGuardBlocked   Reason = "guard_blocked"
	ReasonNotEffective   Reason = "not_effective"
	ReasonEarlierMatch   Reason = "earlier_match"
	ReasonModeExcluded   Reason = "mode_excluded"
)

// A single trace event (SPEC 3.8, 12.1). Carries no input values.
type TraceEvent struct {
	Type            EventType
	RuleID          string
	Reason          Reason
	Timestamp       int64
	ContractVersion string
	Diagnostics     map[string]any
}

// DiagnosticHook receives each TraceEvent and may return extra
// diagnostic fields (SPEC 12.2). Redaction-aware; application-supplied.
type DiagnosticHook func(e *TraceEvent) map[string]any

// Collected execution trace (SPEC 3.8, 12.1-12.3).
type ExecutionTrace struct {
	ContractVersion string
	Events          []TraceEvent
	DiagnosticHook  DiagnosticHook
}

// Emit a trace event, applying the diagnostic hook when present.
func (t *ExecutionTrace) Emit(typ EventType, ruleID string, reason Reason, ts int64) {
	e := TraceEvent{
		Type: typ, RuleID: ruleID, Reason: reason, Timestamp: ts,
		ContractVersion: t.ContractVersion,
	}
	if t.DiagnosticHook != nil {
		e.Diagnostics = t.DiagnosticHook(&e)
	}
	t.Events = append(t.Events, e)
}
