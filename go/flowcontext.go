package flowsemantics

// FlowContext — isolated per-invocation execution context (SPEC 4.1.3, 6.2).
// A fresh FlowContext is created per invocation; no mutable state is
// shared between invocations of the same contract.
type FlowContext struct {
	Input  any
	Clock  Clock
	State  map[string]any
}

// NewFlowContext creates a context with the given input and clock.
// A nil clock defaults to SystemClock.
func NewFlowContext(input any, clock Clock) *FlowContext {
	if clock == nil { clock = SystemClock{} }
	return &FlowContext{Input: input, Clock: clock, State: map[string]any{}}
}
