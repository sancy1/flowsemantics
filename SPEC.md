# FlowSemantics - Normative Specification

**Version:** 0.1.0 (draft for freeze at Phase 0.4)

**Status:** DRAFT. Not frozen. No implementation code may be written against this specification until Phase 0.4 is signed.

**Authority:** This file is the single authoritative normative specification for FlowSemantics. Supporting material in the spec/ and conformance/ directories supports this document; it does not override it. In any conflict, this file wins.

## Conformance language

The key words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, NOT RECOMMENDED, MAY, and OPTIONAL are to be interpreted as described in RFC 2119 and RFC 8174.

An implementation is **conformant** with this specification if and only if it passes 100 percent of the conformance vectors published in conformance/vectors/ for the specification version it targets. No implementation may call itself conformant, be advertised as portable, or be released as version 1.0 while it fails any vector.

---

## Section 1 - Scope, philosophy, non-goals

### 1.1 Scope

FlowSemantics specifies a deterministic, inspectable, cross-language execution model for application decision-and-error flows. It unifies, in one contract:

- conditions and transformations that determine what a flow concludes;
- proposed effects that describe operations an application-owned executor may perform;
- typed exception handling, recovery, and explicit propagation;
- cooperative cancellation and externally-imposed timeout recognition;
- outcome-aware finalization with a policy for cleanup failure;
- structured traces, explainability, and deterministic simulation and replay.

A FlowSemantics implementation MUST provide the execution model defined in this specification. An implementation MAY also provide additional capabilities that do not contradict this specification.

### 1.2 Philosophy (non-negotiable)

FlowSemantics does **not** replace if, else, try, with, async with, or any language control flow. Those constructs remain fundamental and correct for simple local logic.

FlowSemantics provides an **optional higher-level execution model** for the cases where a decision becomes an **object of concern**: traced, tested, simulated, versioned, audited, ported across languages, externalized into data, or validated for structural soundness.

Where native code is sufficient, native code MUST be used. This specification exists for the complex cases, not the simple ones.

### 1.3 Non-goals (normative exclusions)

A conformant implementation MUST NOT include any of the following as part of the FlowSemantics core:

- Authentication or identity provider.
- Authorization platform.
- Database, ORM, or persistence.
- Message broker or distributed workflow scheduler.
- Durable workflow engine.
- Payment processor.
- API gateway or cloud control plane.
- AI or LLM runtime.
- Hidden automatic retries.
- Hidden network activity.
- Default telemetry.
- A mandatory visual editor.
- Replacement of with / async with or any native control flow.

A conformant implementation MUST NOT impose any third-party runtime dependency on consumers. The FlowSemantics core MUST resolve to the standard library of its host language only. Build-time tools and development-time tools are permitted but MUST NOT be required at runtime by consumers.

---

## Section 2 - Terminology

### 2.1 Core terms

**Flow.** A builder object that constructs a set of rules. A flow is mutable during construction. In this specification, flow refers to the construction-phase object.

**FlowContract.** The compiled result of a flow. A flow contract is structurally immutable and may be reused across invocations. It is the unit against which conformance is measured.

**Rule.** A single condition-guard-action triple with a stable identifier. Rules are ordered within a flow. The order and the rule set are defined by the flow builder.

**RuleId.** A stable, opaque identifier attached to every rule. RuleIds MUST be unique within a flow. The identifier is used in traces, error messages, and conformance vectors.

**Condition.** A predicate over the input. MUST be pure. Returns a boolean.

**Pure transformation.** A function that computes a value from the input without performing I/O or mutating external state. MUST be pure.

**Effect.** A description of an operation an application-owned executor MAY perform. Effects are data. The FlowSemantics library MUST NOT apply effects. Only an EffectExecutor supplied by the application may apply them.

**Outcome.** The result of executing a flow. Structured as FlowOutcome (Section 3).

**Trace.** An ordered record of the semantic events that occurred during an execution. Off by default; enabled by the application.

**Explanation.** A human-readable rendering of a trace, derived only from registered rule metadata. Never invented by the library.

**Simulation.** Evaluation of a flow against an input with no effects applied, no hooks invoked, and no side effects performed.

**Replay.** Reproduction of a past decision using recorded inputs and a recorded clock value. Replay is distinct from re-execution of effects.

**Interruption.** A cancellation request or an externally-imposed timeout. An interruption is **not** an exception. It is a distinct category.

**Recovery.** The handling of an exception by a registered catch rule. Recovery is metadata on the outcome, not a terminal state.

**Finalization.** An outcome-aware cleanup phase that runs after the primary execution, including for cancelled and timed-out executions.

### 2.2 Conformance vocabulary

- **Vector.** A single conformance test case, in language-agnostic JSON, matching spec/vector.schema.json.
- **Fixture.** A named test double (cond.true, action.const(v), cleanup.throws(Kind), and similar) resolved by each language adapter. Fixtures are the only way vectors reference behavior.
- **Adapter.** A language-specific runner that loads vectors, resolves fixtures, executes the pipeline, and reports pass or fail per vector.

---
## Section 3 - Canonical types

### 3.1 ExecutionStatus

A conformant implementation MUST provide an ExecutionStatus type with exactly these four members, and no others:

- **COMPLETED** - primary execution reached a terminal outcome without an unrecovered exception, cancellation, or timeout.
- **FAILED** - primary execution raised an exception that was not recovered by a catch rule.
- **CANCELLED** - primary execution was interrupted by a cooperative cancellation request.
- **TIMED_OUT** - primary execution was interrupted by an externally-imposed timeout.

A conformant implementation MUST NOT add additional execution states. Any state that seems necessary beyond these four MUST be re-examined and, if necessary, added via an ADR and a specification version bump.

### 3.2 DecisionStatus

A conformant implementation MUST provide a DecisionStatus type with exactly these three members, and no others:

- **APPROVED** - a rule matched and produced an affirmative decision.
- **REJECTED** - a rule matched and produced a negative decision.
- **NO_MATCH** - no rule matched. This covers two cases:
  (a) no rule matched and no fallback was configured, producing no value; and
  (b) no rule matched but a fallback (otherwise, default, or default_if_no_match)
      produced a value, which becomes the outcome value under NO_MATCH.

  In both cases, DecisionStatus is NO_MATCH. The presence or absence of a value
  does not change the DecisionStatus. Section 10.4 defines the fallback semantics.

DecisionStatus MUST be absent when ExecutionStatus is FAILED, CANCELLED, or TIMED_OUT.

### 3.3 InterruptionInfo

A conformant implementation MUST provide an InterruptionInfo value that is populated if and only if ExecutionStatus is CANCELLED or TIMED_OUT. It MUST contain:

- **kind** - either cancelled or timed_out. MUST match the ExecutionStatus.
- **source** - a string identifying the origin of the interruption.
- **timestamp** - the clock value at which the interruption was observed, from the injected clock (Section 6).
- **deadline** - the deadline that was exceeded, for timeouts. MUST be absent for cancellations.

An InterruptionInfo MUST NOT contain an exception. Cancellation and timeout are not exceptions.

### 3.4 RecoveryInfo

A conformant implementation MUST provide a RecoveryInfo value that is populated if and only if a catch rule handled an exception. It MUST contain:

- **original_exception** - the exception that was caught.
- **handler_rule_id** - the RuleId of the catch rule that handled it.
- **recovered_at** - the clock value at which recovery completed.

RecoveryInfo MUST NOT contain cancellation or timeout information. Interruption is a separate concept (3.3).

### 3.5 FinalizationInfo

A conformant implementation MUST provide a FinalizationInfo value that is populated
if and only if a finalizer was registered. It MUST contain:

- **is_clean** - a boolean. True if and only if every finalizer completed normally
  within its cleanup budget. False if any finalizer raised an exception, was
  cancelled, or exceeded its cleanup budget. This definition applies under every
  FinallyFailurePolicy. The policy determines what happens to the primary outcome;
  is_clean determines whether cleanup itself was clean.

- **cleanup_exceptions** - a possibly-empty ordered tuple of exceptions raised by
  finalizers. An interruption (cancellation, timeout, or budget exhaustion) is
  recorded in cleanup_budget_exceeded where applicable and in the trace; it is not
  recorded in cleanup_exceptions unless the host language surfaces an exception for
  that interruption, in which case that exception is also included here.

- **cleanup_budget_used** - the elapsed cleanup time as measured by the injected
  monotonic clock. Applicable to every finalizer execution (Section 16.7).

- **cleanup_budget_exceeded** - a boolean. True if any finalizer exceeded its
  configured WithFinallyTimeout budget (Section 16.7). Applies to every finalizer
  execution, regardless of primary ExecutionStatus.

IsClean is finalization metadata. It MUST NOT be represented as a fifth
ExecutionStatus or as a composite of ExecutionStatus and IsClean.

The is_clean definition is uniform across every policy. A cleanup failure sets
is_clean = false whether the policy is PreservePrimary, Attach, or ReplacePrimary.
This is invariant B6 as clarified by this specification version.

### 3.6 FlowOutcome

A conformant implementation MUST provide a FlowOutcome value with the following fields:

- **execution_status** - an ExecutionStatus (3.1).
- **decision_status** - a DecisionStatus or absent value (3.2).
- **value** - the result value, if any.
- **recovery** - a RecoveryInfo or absent value (3.4).
- **interruption** - an InterruptionInfo or absent value (3.3).
- **finalization** - a FinalizationInfo or absent value (3.5).
- **primary_exception** - the primary exception if ExecutionStatus is FAILED and no cleanup replaced it, otherwise absent.
- **secondary_exceptions** - an ordered tuple of all non-primary exceptions. MUST include cleanup exceptions even when the primary execution succeeded.
- **effects** - an ordered tuple of proposed Effect values (Section 5).
- **trace** - an ExecutionTrace or absent value (Section 12).

A FlowOutcome MUST be immutable after construction. It MUST NOT be mutated by finalization or by any observer.

### 3.7 Effect

A conformant implementation MUST provide an Effect value with at least:

- **name** - a stable string identifier.
- **payload** - an opaque value whose structure is defined by the application, not by the library.

The library MUST NOT interpret the payload. The library MUST NOT execute the effect. An effect is proposed by the flow and applied (or not) by an application-supplied EffectExecutor.

### 3.8 ExecutionTrace and TraceEvent

Each ExecutionTrace MUST include:

- contract_version - a string identifying the version of the FlowContract that produced the trace.

Each TraceEvent MUST contain at least:

- type - an event type from the canonical vocabulary (Section 12.1).
- rule_id - the RuleId the event pertains to, or absent for events not tied to a rule.
- timestamp - the clock value at which the event occurred.
- reason - a string explaining why the event occurred, when the event type requires one. Required for the three skip event types (rule_skipped, skipped_by_short_circuit, skipped_by_mode) and OPTIONAL for all other event types. When present, its value MUST come from a closed enumeration defined in Section 12.1. The field is absent for event types that do not define reasons.

Each TraceEvent MAY additionally contain:

- contract_version - an optional string identifying the version of the FlowContract that produced the event. When present, it MUST match the trace-level contract_version.

Additional fields MAY be added but MUST NOT contain input values, secrets, or exception messages by default. Opt-in diagnostics are permitted (Section 12.2).

---

## Section 4 - Rule model and lifecycle

### 4.1 Two-stage lifecycle

A flow has two stages: construction and execution. These stages are distinct and MUST NOT be collapsed into a single object that both builds and executes.

#### 4.1.1 Construction stage

During construction, the developer calls fluent methods on a Flow builder to add rules, guards, catches, finalizers, and configuration. The builder is mutable and is not required to be thread-safe.

Construction MUST NOT execute any condition, transformation, or effect. Construction MUST NOT perform I/O.

#### 4.1.2 Compilation stage

Calling compile on the builder MUST:

1. Validate the flow (Section 4.3).
2. Produce a FlowContract that is structurally immutable, reusable, and safe to share across concurrent invocations.
3. Record the flow portability classification (Section 4.4).

Compilation MUST fail if validation fails. It MUST NOT return a partially-valid contract.

#### 4.1.3 Execution stage

Executing a FlowContract MUST:

1. Create an isolated execution context for the invocation. No mutable state is shared between invocations.
2. Evaluate the flow according to Sections 10 and 11.
3. Produce a FlowOutcome (Section 3.6).

Execution MUST NOT be affected by other concurrent executions of the same contract.

### 4.2 Thread safety (qualified)

A FlowContract MUST be structurally immutable. Its internal state MUST NOT change after compilation.

Execution contexts MUST be isolated per invocation. The library MUST NOT share mutable execution state across invocations of the same contract.

User-supplied callbacks are not guaranteed to be thread-safe. A callback that closes over a mutable object is not safe to execute concurrently. The library documents this and MUST NOT claim that user callbacks are thread-safe. The library thread-safety guarantee applies to the contract and its execution contexts, not to user code.

A conformant implementation MUST document this limitation prominently.

### 4.3 Compilation validation

compile() MUST validate at least the following, and MUST reject the flow if any validation fails:

- Every rule has a non-empty RuleId.
- RuleIds are unique within the flow.
- At least one of the following is true: at least one rule is registered, or a default or default_if_no_match fallback is configured. A flow with neither is invalid.
- Catch rules: at least one catch_any rule, if present, is registered after all typed catch and catch_when rules.
- Finalizers: A flow MUST NOT mix synchronous and asynchronous finalizers. If a flow registers one or more asynchronous finalizers, every finalizer registered by that flow MUST be asynchronous. The compiled contract is classified as async-only. Calling execute() on an async-only contract MUST fail with a clearly named error. execute_async() is the only permitted execution entry point.
- Evaluation mode: all merged flows MUST share the same EvaluationMode. Merge with mismatched modes is invalid (Section 10.7).
- Portability: if the flow contains any component that is not representable in the portable IR (an opaque callable), the flow is classified as NATIVE. This is not an error, but it is recorded and MUST NOT be advertised as portable.
- Version: if effective_from or effective_until are configured, effective_from MUST be less than effective_until if both are present.

A conformant implementation MUST reject the flow if any of these checks fails. The specific error type and message are implementation-defined.

### 4.4 Portability classification

Every FlowContract MUST be classified as exactly one of:

- **PORTABLE** - every component of the contract belongs to the portable representation defined in spec/ir.schema.json. The contract may be exported to the portable IR and executed by any conformant implementation.
- **NATIVE** - at least one component is opaque to the library (such as an arbitrary user callable). The contract is not portable and MUST NOT be exported.

The classification is a property of the entire contract, not of individual components. A flow containing any opaque component is NATIVE, even if all other components are declarative.

export_portable() on a NATIVE contract MUST raise a PortabilityError naming the offending component or components.

### 4.5 Evaluation order (normative summary)

Rules within a flow are evaluated in the order they were added, unless EvaluationMode is Priority (Section 10.8), in which case rules are evaluated by declared priority.

Evaluation MUST short-circuit on the first matching rule under FirstMatch mode. Under AllMatch, evaluation MUST continue after a match. The mode is explicit and MUST be documented for every rule chain.

Detailed evaluation semantics are defined in Section 10.

---
## Section 5 - Purity and effects

### 5.1 The purity contract

FlowSemantics distinguishes three operation categories. The distinction is normative and MUST be honored by every conformant implementation.

**Conditions.** Determine whether a rule matches. Conditions MUST be pure:

- MUST NOT perform I/O (network, filesystem, database, message broker, clock read outside the injected clock, random number generation).
- MUST NOT mutate external state.
- MUST return the same result for the same input and the same clock value.
- MAY raise only the exceptions that Section 11 permits to be raised from a condition or transformation. An exception raised by a condition or transformation is treated as the exception that Section 11 catch, catch_any, and rethrow rules evaluate. No other exception type is permitted from a pure condition or transformation; if a host-language exception does not fall into one of Section 11 permitted categories, it is treated as an unrecovered FAILED exception.

**Pure transformations.** Compute a value from the input without performing I/O or mutating external state. Pure transformations MUST satisfy the same constraints as conditions, plus:

- MUST return a value of the declared output type.
- MAY raise the exceptions permitted in Section 11.

**Effects.** Describe operations an application-owned executor MAY perform. Effects:

- Are **data**, not code. An effect has a stable name and an opaque payload.
- MUST NOT be executed by the FlowSemantics library.
- MUST only be applied by an EffectExecutor supplied by the application.
- MUST be proposed in a deterministic order (Section 6.4).

### 5.2 Honesty about non-enforcement

A conformant implementation MUST document, clearly and prominently, that:

- The library **cannot** mechanically enforce the purity contract for arbitrary user callables in a general-purpose language.
- A condition or transformation that performs I/O inside its body will not be detected by the library unless the implementation provides a static analyzer that specifically checks for it (an optional Phase 6+ capability).
- Users are responsible for honoring the purity contract.

The library MUST NOT claim, in documentation or marketing, that it enforces purity. It documents the contract; it does not enforce it. It MAY provide tooling to help, and that tooling MUST be clearly labeled as an aid, not a guarantee.

### 5.3 Why this matters

Purity is not a style preference. It is what makes the following properties possible:

- **Determinism.** A pure condition evaluated twice with the same input produces the same result.
- **Traceability.** A pure condition produces a trace event that accurately describes what happened.
- **Simulation safety.** A flow evaluated in simulation mode performs no external operation, because no external operation is inside any condition or transformation.
- **Cross-language portability.** A pure condition is expressible in the portable IR. An impure condition is not, because the IR cannot carry the side effect.

An implementation MAY provide opt-in checks (a purity_checked flag at compile time, a static analyzer, or a runtime guard that raises on the first non-injected clock read). Any such check MUST be documented as a best-effort aid, not a guarantee.

### 5.4 The three categories are not the same

A flow that mixes the three categories violates this specification. Examples of violations:

- A condition that calls datetime.now() instead of the injected clock. Violation: impure condition.
- A transformation that writes to a database. Violation: impure transformation (I/O inside a pure computation).
- A transformation that returns an effect and also applies it. Violation: the library MUST NOT execute effects; only an EffectExecutor may.
- A hook (on_match) that mutates the primary outcome. Violation: hook failures are isolated (Section 11.5); hooks may not change the outcome.

A conformant implementation MAY detect some of these at compile time (e.g., a hook that is declared to return a value instead of being a side effect). It MUST NOT claim to detect all of them.

### 5.5 Side-effect boundary (normative)

The boundary of the library is:

- **Inside the library**: pure evaluation, trace recording, proposal of effects.
- **Outside the library (application-owned)**: effect execution, persistence, network I/O, messaging, and every operation the application decides to perform.

The library MUST NOT cross this boundary. It MUST NOT ship with a built-in database client, HTTP client, message queue producer, or any other external operation. interfaces/ subpackages may exist for adapters, but they are not part of the core library and MUST NOT be imported by the core.

---

## Section 6 - Determinism and time

### 6.1 The determinism requirement

Given the same input, the same flow contract, the same injected clock value, and the same random source (if any), a conformant implementation MUST produce the same FlowOutcome. This is a MUST, not a SHOULD.

Determinism is required for:

- **Replay.** A replay of a recorded execution with the recorded clock value must produce the recorded outcome.
- **Testing.** A test that evaluates a flow twice must not see different results.
- **Cross-language conformance.** Two implementations that pass the same vectors must produce the same outcome for the same vector.

### 6.2 Injected clocks (normative)

A conformant implementation MUST support injecting clocks. It MUST distinguish at least two clock concepts:

**Wall clock.** Used for effective dates (effective_from, effective_until), for timestamps recorded in traces, and for the timestamp in InterruptionInfo.

**Monotonic clock.** Used for elapsed-time measurement, for cleanup budget accounting, and for any duration computation.

Both clocks MUST be injectable. In Python, the idiom is a Clock protocol with wall() and monotonic() methods. In C#, the idiom is TimeProvider. In Go, the idiom is an interface with the two methods. In TypeScript, the idiom is a similar interface. Language-specific names are permitted; the two-concept distinction is normative.

The core library MUST NOT read the host's ambient clocks (e.g., datetime.now(), 	ime.time() in Python; DateTime.Now, Environment.TickCount in C#; 	ime.Now() in Go) directly. Every time read MUST route through the injected clock(s).

### 6.3 Default clock and CI enforcement

A conformant implementation MAY provide a default clock that reads the host's real clocks, for convenience. If it does, the default MUST be clearly documented, and it MUST be replaceable.

Every conformant implementation MUST provide a way for the application to inject a fake clock. The fake clock MUST be sufficient to control both wall time and monotonic time.

Every conformant implementation MUST enforce, in CI, that the core library does not call ambient clock APIs. This is enforced by the audit (Phase 0.0's udit.py does this for Python; the C# implementation must do the same; and so on).

### 6.4 Determinism of effects and their order

The order in which effects are proposed MUST be deterministic. Given the same input, the same flow contract, and the same clock value, the ordered tuple of proposed effects MUST be identical across executions.

An implementation MUST NOT propose effects in a way that depends on the order of user callbacks iterating a hash map, a set, or any unordered collection. If the implementation must propose effects in a non-obvious order, that order MUST be documented.

Simulation and replay MUST preserve the proposed-effect order. A replay that produces the same effects in a different order is not a valid replay.

### 6.5 Culture invariance

String formatting of numeric values, dates, and durations in traces, explanations, and error messages MUST be culture-invariant. The canonical culture is en-US with invariant number and date formatting, or the equivalent.

An implementation MUST NOT use the host's current culture for any normative output. An implementation MAY offer culture-aware formatting as an opt-in diagnostic feature, clearly labeled non-normative.

Rationale: a trace produced on a system with de-DE culture and a trace produced on a system with en-US culture must be identical, because they are inputs to replay and to cross-language conformance.

### 6.6 Determinism and random sources

FlowSemantics does not require randomness. If an implementation or a user callback needs randomness, the source MUST be injected, and the injected source MUST be reproducible across replay.

A conformant implementation MUST NOT call 
andom.random(), uuid.uuid4(), or any equivalent ambient random source from the core library. If randomness is needed (for example, for hedging in a future version), it MUST come from an injected source.

### 6.7 Determinism checklist

For an execution to be reproducible, all of the following MUST be true:

- The flow contract is identical (same rules, same order, same configuration).
- The input value is identical.
- The injected wall clock value is identical.
- The injected monotonic clock's elapsed-time sequence is identical.
- The injected random source, if any, is seeded identically.
- The evaluation mode is identical.
- No external state is read (conditions and transformations are pure).

If any of these is different between two executions, the executions MAY produce different outcomes, and this is not a violation of determinism.

---
## Section 7 - Result states and transitions

### 7.1 The transition contract

This section defines every permitted transition between outcome states. A transition is a (current state, event) pair that produces a next state. Any transition not listed in Section 7.3 is a violation of this specification.

Implementations MUST NOT introduce additional transitions. If a transition appears necessary, it MUST be added via an ADR and a specification version bump.

### 7.2 The starting state

Every execution begins in a well-defined initial state:

- ExecutionStatus is absent (not yet set).
- DecisionStatus is absent.
- value is absent.
- recovery is absent.
- interruption is absent.
- finalization is absent.
- primary_exception is absent.
- secondary_exceptions is empty.
- effects is empty.
- trace is absent (unless with_trace was enabled, in which case trace is an empty trace).

The initial state MUST NOT be observable as a FlowOutcome. It is an internal state. The first observable FlowOutcome is produced either by the first rule evaluation that reaches a terminal outcome, or by finalization.

### 7.3 The full transition table

The following table lists every permitted transition. Each row is a (current state, event) pair and the resulting next state. Events not listed here MUST NOT produce a transition; they are no-ops with respect to the outcome state (they may still append to the trace).

#### 7.3.1 Initial state transitions

| Event | Next ExecutionStatus | Notes |
|---|---|---|
| A rule matches and produces an APPROVED decision | COMPLETED | DecisionStatus becomes APPROVED. value is set. |
| A rule matches and produces a REJECTED decision | COMPLETED | DecisionStatus becomes REJECTED. value is set. |
| No rule matches and default_if_no_match is configured | COMPLETED | DecisionStatus becomes NO_MATCH. value is set from the constant. |
| No rule matches and otherwise is configured | COMPLETED | DecisionStatus becomes NO_MATCH. value is set from the fallback transformation. |
| No rule matches and no fallback is configured | COMPLETED | DecisionStatus becomes NO_MATCH. value is absent. |
| An unrecovered exception is raised by a condition or transformation | FAILED | primary_exception is set. |
| A catch rule recovers an exception | The execution remains in the initial state pending further evaluation; RecoveryInfo is populated | The flow continues as if the exception did not occur. |
| A cooperative cancellation is observed | CANCELLED | interruption is set with kind=cancelled. |
| An externally-imposed timeout is observed | TIMED_OUT | interruption is set with kind=timed_out. |

#### 7.3.2 Terminal state transitions (finalization only)

After the primary execution reaches a terminal state (COMPLETED, FAILED, CANCELLED, or TIMED_OUT), the only permitted transition is finalization. The result of finalization depends on the FinallyFailurePolicy (Section 16) and on whether cleanup failed.

The following table is normative. The full policy matrix is in Section 16.4.

| Current ExecutionStatus | Cleanup outcome | FinallyFailurePolicy | Next ExecutionStatus | Notes |
|---|---|---|---|---|
| COMPLETED | succeeds | any | COMPLETED | No change. is_clean=true. |
| COMPLETED | fails | PreservePrimary | COMPLETED | is_clean=false. cleanup exception in secondary_exceptions. |
| COMPLETED | fails | Attach | COMPLETED | is_clean=false. cleanup exception in secondary_exceptions. |
| COMPLETED | fails | ReplacePrimary | COMPLETED | is_clean=false. cleanup exception in secondary_exceptions. primary value preserved. |
| FAILED | succeeds | any | FAILED | No change. is_clean=true. |
| FAILED | fails | PreservePrimary | FAILED | is_clean=false. cleanup exception in secondary_exceptions. Original primary_exception preserved. |
| FAILED | fails | Attach | FAILED | is_clean=false. cleanup exception in secondary_exceptions. Original primary_exception preserved. |
| FAILED | fails | ReplacePrimary | FAILED | is_clean=false. cleanup exception becomes primary_exception; original primary_exception moves to secondary_exceptions. Both preserved. |
| CANCELLED | succeeds | any | CANCELLED | No change. is_clean=true. |
| CANCELLED | fails | PreservePrimary | CANCELLED | is_clean=false. cleanup exception in secondary_exceptions. interruption preserved. |
| CANCELLED | fails | Attach | CANCELLED | is_clean=false. cleanup exception in secondary_exceptions. interruption preserved. |
| CANCELLED | fails | ReplacePrimary | CANCELLED | is_clean=false. cleanup exception in secondary_exceptions. interruption preserved. |
| TIMED_OUT | succeeds | any | TIMED_OUT | No change. is_clean=true. |
| TIMED_OUT | fails | PreservePrimary | TIMED_OUT | is_clean=false. cleanup exception in secondary_exceptions. interruption preserved. |
| TIMED_OUT | fails | Attach | TIMED_OUT | is_clean=false. cleanup exception in secondary_exceptions. interruption preserved. |
| TIMED_OUT | fails | ReplacePrimary | TIMED_OUT | is_clean=false. cleanup exception in secondary_exceptions. interruption preserved. |

**Normative invariant B3-a is encoded in this table:** ReplacePrimary MUST NOT change CANCELLED to FAILED, and MUST NOT change TIMED_OUT to FAILED. Interruption is preserved under every policy. Section 16.5 states this as an explicit MUST.

### 7.4 Prohibited transitions

The following transitions are explicitly prohibited and MUST NOT occur:

- COMPLETED to CANCELLED, TIMED_OUT, or FAILED. Under every policy, COMPLETED is preserved and cleanup failure does not change it to FAILED (see Section 16.4.3 for the authoritative matrix).
- CANCELLED to COMPLETED or FAILED (ReplacePrimary is explicitly prohibited from changing CANCELLED).
- TIMED_OUT to COMPLETED or FAILED (ReplacePrimary is explicitly prohibited from changing TIMED_OUT).
- Any transition that loses a cleanup exception. Cleanup exceptions MUST appear in secondary_exceptions regardless of policy (invariant B7).
- Any transition that mutates the value field after the primary execution terminates. The value is sealed when the primary execution terminates.

An implementation that permits a prohibited transition is not conformant.

### 7.5 Determinism of transitions

Given the same flow contract, input, and clock value, the sequence of transitions MUST be identical. The transition table is deterministic. There is no nondeterminism in the transition logic itself, only in the inputs (which are controlled by the application and by the injected clocks).

---

## Section 8 - Specification evolution

### 8.1 Versioning the specification

The specification has its own version number, separate from any implementation's version. The specification version is recorded in VERSION at the repository root. Before 1.0, the specification version and the library version are identical. At 1.0, they diverge: the specification reaches 1.0 when frozen; the reference Python implementation reaches 1.0 when it passes 100 percent of the conformance vectors and is released. After divergence, VERSION records the specification version; each implementation records its own library version in its manifest and independently tracks which specification version it conforms to.

Before 1.0, the specification is considered unstable. It may change without notice, though changes are documented in CHANGELOG.md. Once 1.0 is reached, the specification is frozen and may only change via the process in 8.2.

### 8.2 Changing the specification after 1.0

Once the specification is frozen at 1.0, any normative change MUST go through the following process:

1. **ADR proposal.** A new ADR is proposed with the change, the rationale, the cost of not changing, and the cost of changing.
2. **Compatibility assessment.** The ADR MUST state whether the change is backward-compatible, forward-compatible, or breaking.
3. **Vector update.** If the change affects observable behavior, at least one conformance vector MUST be added or modified.
4. **Review.** The change is reviewed by at least two maintainers or external reviewers who are not the author.
5. **Version bump.** The specification version is bumped according to 8.3.
6. **Implementation sign-off.** Every implementation that claims conformance with the new version MUST sign off that it passes the updated vectors before the version is published.

### 8.3 Version bump rules

The specification follows semantic versioning independently of the library version:

**Patch (x.y.Z).** Clarifications, typo fixes, additions of non-normative notes. No behavior change. Vectors unchanged. All conformant implementations remain conformant.

**Minor (x.Y.z).** Additions to MAY, SHOULD, or OPTIONAL. New optional capabilities. Existing conformant implementations remain conformant without change.

**Major (X.y.z).** Changes to MUST, MUST NOT, REQUIRED, or SHALL. Changes to the canonical types. Changes to the transition table. Any change that a previously conformant implementation would fail. Requires a new major version and a migration guide.

A major version bump does not require every implementation to upgrade immediately. But an implementation that claims conformance with version X must pass the vectors of version X, not version X-1.

### 8.4 Deprecation

A feature MAY be deprecated in a minor version before being removed in a major version. Deprecation MUST:

- Be announced in the changelog.
- Be documented in the specification as deprecated, with the version in which it will be removed.
- Remain functional in all minor versions until the removal.

Removal without deprecation in a prior minor version is not permitted after 1.0.

### 8.5 Cross-language compatibility

Implementations in different languages MUST conform to the same specification version to be considered mutually compatible. An implementation that targets specification version 1.0 and another that targets version 1.1 are not required to interoperate, though the 1.1 implementation SHOULD accept 1.0 inputs where the change is a pure addition.

The specification version is recorded in VERSION at the repository root. Each implementation records the specification version it targets in its manifest (Python: pyproject.toml metadata; C#: csproj property; and so on).

### 8.6 Frozen decisions

The following decisions are frozen by this specification version and MUST NOT be changed without an ADR and a specification version bump:

- D1: ExecutionStatus and DecisionStatus are separate.
- D2: Conditions and transformations are pure; effects are proposed data.
- D3: Portability classification is on the whole compiled contract.
- B1: Timeout is recognized, not enforced.
- B5: Interruption is not stored under recovery.
- B6: IsClean is finalization metadata, not a fifth status.
- B7: Cleanup exceptions always appear in secondary_exceptions.
- B8: The cleanup timeout is a cooperative budget, not a hard kill.
- O1: Recovery is metadata on the completed outcome.
- O2: NO_MATCH is distinct from REJECTED; SKIPPED is reserved for deliberate non-execution.

Each of these is encoded in the normative text of Sections 3 through 7 and Section 16. A change to any of them is a major version bump.

---
## Section 9 - Security

### 9.1 Threat model

FlowSemantics executes user-supplied rules against user-supplied input. The security surface is narrow but not zero. The following threats are in scope for a conformant implementation:

- **Malformed rule graphs** from the portable IR. An attacker may supply a rule graph that is syntactically valid but pathological (deep nesting, huge tables, cyclic references, duplicate RuleIds).
- **Deserialization attacks** through the portable IR. An attacker may craft input that exploits a lenient deserializer.
- **Resource exhaustion** through pathological rule sets. A rule set with ten thousand rules that all match may exhaust memory or CPU.
- **Replay-record tampering.** A recorded execution that is used as input to replay may be tampered with to produce a fraudulent outcome.

A conformant implementation MUST document its threat model and MUST publish a security disclosure process.

### 9.2 Portable IR hardening

Any implementation that deserializes the portable IR MUST:

- Enforce a maximum nesting depth. Implementations MUST document a specific maximum depth. A depth greater than 100 MUST be rejected. A depth of at least 10 is RECOMMENDED as a minimum supported depth.
- Enforce a maximum rule count. The exact maximum is implementation-defined but MUST be documented.
- Enforce a maximum total byte size of the deserialized structure.
- Reject duplicate RuleIds at deserialization time, not at execution time.
- Reject references to undefined fixtures, undefined fields, or undefined operators.
- Reject cyclic references.
- Not execute arbitrary code from the IR. The portable IR carries structure, RuleIds, named references, and a limited expression subset; it MUST NOT carry host-language code.

An implementation that accepts an unbounded IR is not conformant.

### 9.3 Resource exhaustion

A conformant implementation MAY impose resource limits on execution:

- A maximum number of rules evaluated per execution.
- A maximum execution time (this is distinct from a timeout; it is an internal safety limit).
- A maximum memory footprint.

If resource limits are imposed, they MUST be documented and MUST be configurable. An implementation that imposes hidden limits without documentation is not conformant.

### 9.4 Fuzz and adversarial testing

A conformant implementation SHOULD include the following in its test suite:

- Fuzz tests for the Portable IR deserializer, including malformed JSON, deeply nested JSON, oversized JSON, and duplicate-key JSON.
- Property-based tests for the transition table in Section 7, asserting that no execution produces a prohibited transition.
- Differential tests comparing compiled execution with interpreted execution for every conformance vector.

For specification version 0.1, these test categories are scheduled for delivery in Phase 6.5. An implementation that has not yet completed Phase 6.5 MUST document this omission in its conformance report as a deferred quality-assurance item, including the target delivery phase. A version 1.0 general-availability release MUST include all three test categories.

### 9.5 Replay-record integrity

A replay record is an input to the replay engine. A tampered record could produce a fraudulent outcome. A conformant implementation MUST:

- Record the specification version and the flow contract version in every replay record.
- Provide a keyed integrity mechanism for every replay record. An implementation MUST support at least one of: HMAC, digital signature, or an application-supplied integrity mechanism providing equivalent tamper detection. Unkeyed hashing alone MUST NOT be presented as sufficient protection against malicious tampering (see Section 12.6).
- Fail closed if a replay record's version does not match the current contract version, rather than silently producing a wrong outcome.

### 9.6 What the library does NOT do

The library does not authenticate users, authorize access to resources, encrypt data at rest or in transit, manage secrets, or perform any security function beyond the boundary described in this section. Applications MUST provide these capabilities. Section 1.3 lists them as normative non-goals.

---

## Section 10 - Decision semantics

This section defines how rules are structured and evaluated. Sections 10.1 through 10.5 define the primitives. Sections 10.6 through 10.9 (Part 3b) define evaluation modes, merge, decision tables, and compile semantics.

### 10.1 Rule structure and evaluation order

A rule is a tuple: (RuleId, condition, guard, action). The action is either a transformation that produces the value, or a proposal of effects, or both. The precise shape of the action is defined in Section 11.

Rules within a flow are evaluated in the order in which they were added to the builder, unless EvaluationMode is Priority (Section 10.6), in which case rules are evaluated in declared-priority order.

The evaluation order MUST be deterministic. Two evaluations of the same contract with the same input MUST evaluate rules in the same order.

### 10.2 when and when_not

**when(condition, then=action, id=ruleId).** Evaluates the condition against the input. If the condition is true, the rule matches and the action is executed according to the evaluation mode. If the condition is false, the rule does not match.

**when_not(condition, then=action, id=ruleId).** Evaluates the condition against the input. If the condition is false, the rule matches and the action is executed. If the condition is true, the rule does not match.

Both methods:

- MUST require a non-empty RuleId.
- MUST register the rule in the flow's rule list in the order called.
- MUST NOT execute the condition during construction. The condition is executed only during execution.
- MUST NOT short-circuit differently than the evaluation mode specifies.

A condition that raises an exception is handled by the exception rules in Section 11. The rule does not match by the exception; the exception propagates according to Section 11.

### 10.3 unless (omitted from v0.1)

The unless method is **deliberately omitted from v0.1**. The rationale is documented in the v5 feature baseline and in the ADR:

- when_not(predicate) expresses the same logic without ambiguity.
- An unless method has historically been interpreted in two ways in other libraries: as a guard on the preceding rule, or as a negative condition. Both interpretations exist in the wild, which makes the method name a source of confusion.
- The library chooses not to introduce a method whose semantics could be misread.

A conformant implementation of specification version 0.1 MUST NOT include unless in the public API. A future specification version MAY introduce it, but only with a single unambiguous meaning documented in an ADR.

### 10.4 otherwise, default, default_if_no_match

These three methods provide fallback behavior when no rule matches.

**otherwise(action).** A dynamic fallback. The action is a transformation over the input. It is executed only if no rule matched during evaluation. The result of the action becomes the value in the outcome, and DecisionStatus is set to NO_MATCH.

**default_if_no_match(value).** A constant fallback. The value is a constant of the output type. If no rule matched, the value becomes the outcome value, and DecisionStatus is set to NO_MATCH.

**default(value).** A documented alias of default_if_no_match. The two methods MUST produce identical outcomes. Implementations MUST provide both; the alias exists for API familiarity.

Rules:

- At most one of otherwise, default, or default_if_no_match may be configured per flow. Configuring two or more is a compilation error (Section 4.3).
- If none is configured and no rule matches, the outcome has DecisionStatus NO_MATCH and no value. This is not an error; it is a valid outcome.
- The otherwise action MUST be pure (Section 5.1).

The interaction between NO_MATCH and fallback values is defined in Section 3.2. NO_MATCH covers both cases: no rule matched and no fallback produced a value, and no rule matched but a fallback produced a value that became the outcome value.

### 10.5 then (sequential transformation)

**then(stage, id=ruleId).** A sequential transformation that runs only if the preceding rule matched. The stage receives two arguments: the input, and the previous output (the value produced by the preceding matched rule or then stage). The stage returns the next value.

Rules:

- 	hen MUST be registered immediately after a rule or after another 	hen. It cannot be the first element of a flow. Registering 	hen before any rule or fallback is a compilation error.
- 	hen runs once per match, in the evaluation order. Under FirstMatch mode, at most one preceding rule matches, so at most one chain of 	hen runs. Under AllMatch mode, 	hen runs once per matched rule, receiving that rule's output as the previous value. Under Priority mode, 	hen runs once after the highest-priority matching rule.
- If no preceding rule matched, 	hen is skipped and a trace event is recorded indicating it was skipped.
- The stage MUST be pure (Section 5.1).
- The stage's RuleId MUST be unique within the flow.

	hen is what makes the pipeline a pipeline and not just a switch. A 	hen after a match transforms the outcome; a 	hen after no match does nothing.

---
### 10.6 EvaluationMode

EvaluationMode determines what happens when more than one rule could match. It is a property of the flow, set at construction time, and frozen at compile time.

A conformant implementation MUST provide exactly these three modes, and no others:

**FirstMatch.** Rules are evaluated in registration order. The first rule whose condition is true (and whose guard, if any, permits) matches, its action executes, and evaluation terminates. This is the default mode. Under FirstMatch, at most one rule matches.

**AllMatch.** Rules are evaluated in registration order. Every rule whose condition is true matches, and its action executes. Evaluation continues to the end of the rule list. Under AllMatch, zero or more rules may match. If any rule matches, DecisionStatus is set by the last matched rule decision; if none matches, DecisionStatus is NO_MATCH.

**Priority.** Rules are evaluated in declared-priority order (highest priority first). The first rule whose condition is true matches, and evaluation terminates. Ties in priority are resolved by registration order (earlier wins). Under Priority, at most one rule matches.

Rules:

- The default mode is FirstMatch. An implementation MUST default to FirstMatch if no mode is explicitly set.
- The mode MUST be set at construction time. Setting it after a rule is added is permitted, but the mode used at compile time is the one that applies to execution.
- Merge requires both flows to have the same mode (Section 10.7).
- The mode is recorded in the flow contract and is available as metadata on the contract.

### 10.7 Merge

**merge(other).** Splices another flow rules, guards, catches, finalizers, and fallback into the current flow at the call site. Merge is what makes flows composable.

Rules:

- **EvaluationMode compatibility.** Both flows MUST have the same EvaluationMode. Merging a FirstMatch flow with an AllMatch flow is a compilation error. An implementation MUST reject it, not silently choose one.
- **RuleId uniqueness.** After merge, all RuleIds in the combined flow MUST be unique. An implementation MUST reject a merge that would produce duplicate RuleIds.
- **Catch scoping.** Catch rules introduced by a merged flow apply only to exceptions raised by rules, transformations, guards, and fallback actions that originate from that merged flow. They do not apply to: rules registered in the outer flow before the merge call site; rules registered in the outer flow after the merge call site; exceptions raised by the outer flow's own fallback action; or exceptions raised by the outer flow's finalizers. Catch rules registered by the outer flow continue to apply according to their normal registration and evaluation rules.
- **Finally ordering.** Finalizers from the merged flow run before the outer flow finalizers, in LIFO order (inner first, then outer). This is normative. A merge that would place an inner finalizer after an outer finalizer is not conformant.
- **Fallback ownership.** If both flows have a fallback, the outer flow fallback wins. The inner flow fallback is discarded. An implementation MUST document this behavior; it MUST NOT silently combine the two.
- **Effect ordering.** Proposed effects from the merged flow appear after the effects of the outer flow earlier rules, in the order the merged rules execute.

Merge is not associative across different modes: A.merge(B).merge(C) may differ from A.merge(B.merge(C)) if the modes differ. Since merge requires matching modes, this is not a source of ambiguity, but the property test in Section 9.4 MUST account for it (the associativity property is stated as under matching modes).

### 10.8 DecisionTable

**from_table(table).** Compiles a decision table into an equivalent rule list. Decision tables are a way for non-developers to author rules, and the library treats them as a builder that produces the same internal rule list as the fluent API.

A decision table consists of:

- Columns that declare the condition fields.
- Rows that declare the condition values and the decision (or action) for that combination.
- A hit policy that specifies what to do when multiple rows match.

The hit policy is mapped to EvaluationMode:

- FIRST maps to FirstMatch.
- COLLECT maps to AllMatch.
- PRIORITY maps to Priority.
- UNIQUE maps to first-match, but with a compile-time validation that no two rows can both match.

A conformant implementation MUST provide at least the FIRST, COLLECT, PRIORITY, and UNIQUE hit policies. It MAY provide additional policies (ANY, RULE ORDER, OUTPUT ORDER) as documented extensions.

Validation: for a decision table using the UNIQUE hit policy, the implementation MUST validate row exclusivity to the extent supported by the portable expression subset and the implementation's static analysis capability. If exclusivity cannot be proven statically, the implementation MUST report a validation warning. It MUST NOT claim a compile-time uniqueness guarantee for conditions it cannot analyze. A UNIQUE table that is accepted as uniquely valid MUST NOT produce two matches for the same input.

### 10.9 Compile semantics

**compile().** Is the transition from the construction stage to the execution stage. It validates the flow (Section 4.3) and produces a FlowContract.

Rules:

- compile() MUST validate the flow. If validation fails, compile() MUST raise (or return an error equivalent) and MUST NOT produce a partial contract.
- compile() MUST be idempotent: calling it twice on the same builder MUST produce two contracts that are structurally identical (though they may be distinct objects).
- A compiled contract MUST be structurally immutable. Attempts to mutate it MUST raise.
- A compiled contract MUST record the specification version it conforms to.
- A compiled contract MUST record the portability classification (Section 4.4).
- A compiled contract MUST be reusable across invocations, including concurrent invocations from multiple threads.

A flow builder that has been compiled MUST remain usable for further construction. Adding a rule after compile() MUST NOT invalidate the previously-compiled contract; it produces a new contract when compile() is called again.

---
## Section 11 - Error and execution semantics

This section defines how exceptions are handled, how recovery works, and how interruption (cancellation and timeout) is treated. Sections 11.1 through 11.5 define catch rules and hooks. Sections 11.6 through 11.8 (Part 3d) define interruption, async, and finalization.

### 11.1 catch

**catch(handler).** Registers a typed exception handler. The handler receives two arguments: the input and the caught exception. It returns the value that becomes the outcome value.

The exception type is declared in the language's native form: a type parameter in C#, a class in Python, and so on. Exception matching follows the host language inheritance rules. In Python, a handler registered for Exception catches any subclass of Exception; it does not catch BaseException subclasses that do not inherit from Exception (such as SystemExit or KeyboardInterrupt). In C#, a handler registered for a base exception type catches derived types, but does not catch exceptions that do not inherit from the registered type.

Rules:

- A catch handler MUST receive the input and the exception. It MUST NOT receive only the exception. The input is available because handlers frequently need context (for example, to compute a fallback value from the input).
- A catch handler MUST return a value of the output type. The outcome value becomes the handler return value.
- Recovery is metadata on the outcome. It is not a terminal state. When a catch rule recovers an exception, the RecoveryInfo is populated and the execution continues; the final ExecutionStatus depends on what happens next. If no subsequent failure or interruption occurs, the final ExecutionStatus is COMPLETED. If a subsequent failure occurs and is not recovered, the final ExecutionStatus is FAILED. If a subsequent interruption occurs, the final ExecutionStatus is CANCELLED or TIMED_OUT. Recovery itself does not determine the final status; it only records that an exception was handled at that point.
- A catch handler that itself raises an exception propagates the new exception, not the original. This is explicit, not silent.

### 11.2 catch_when

**catch_when(predicate, handler).** A typed exception handler with a predicate. The predicate receives two arguments: the input and the caught exception. It returns a boolean.

Rules:

- The predicate is evaluated only after the type eligibility check. If the exception is not of the declared type (or a subtype), the predicate is not called.
- If the predicate returns true, the handler is invoked with (input, exception). The handler returns a value of the output type.
- If the predicate returns false, this catch does not apply. Evaluation continues to the next catch rule.
- If the predicate itself raises an exception, the new exception propagates. The original exception is not silently dropped; it is recorded in the trace as a nested event, but the primary failure becomes the predicate failure.
- A failing predicate is an explicit failure. It MUST NOT be silently treated as false.

### 11.3 catch_any

**catch_any(handler).** A broad exception handler that catches any exception not already caught by a typed catch or catch_when.

Rules:

- catch_any MUST be registered after all typed catch and catch_when rules. Registering catch_any before any typed catch is a compilation error (Section 4.3).
- The handler receives (input, exception). It returns a value of the output type.
- A catch_any that itself raises propagates the new exception.
- If multiple catch_any rules are registered, the first one is tried, then the next. A catch_any that declines (by not matching, if the implementation supports predicate-based catch_any) falls through to the next.

### 11.4 rethrow

**rethrow().** Explicit propagation. Registers a rule that, if reached, propagates the current exception without recovery.

Rules:

- rethrow MUST preserve the original exception. The traceback (in Python) or stack trace (in C#) MUST be preserved as far as the host language allows.
- After rethrow, ExecutionStatus is FAILED, primary_exception is the original exception, and DecisionStatus is absent.
- rethrow is not automatic. An implementation MUST NOT rethrow silently. The behavior after all catch rules decline is normative and distinct per method: execute() MUST propagate the unrecovered exception to the caller. try_execute() MUST NOT propagate; it MUST return a FlowOutcome with ExecutionStatus FAILED and primary_exception set to the unrecovered exception. The two methods have different contracts by design: execute() is for callers who want the exception (Python-style, try/except-friendly), try_execute() is for callers who want the outcome (outcome-oriented). This is decision D13.

### 11.5 on_match (observable hook)

**on_match(hook).** Registers a hook that is invoked when a rule matches, after the rule action executes. The hook is a side effect (logging, metrics, audit), not a transformation.

Rules:

- The hook receives (input, RuleId, value). It MUST NOT return a value that affects the outcome.
- The hook is invoked after the rule action produces its value. The hook sees the value that the action produced.
- Hook failures are isolated. If the hook raises an exception, that exception is recorded in secondary_exceptions (Section 3.6) and the trace, but the outcome is not altered. The hook MUST NOT trigger a catch rule.
- Hooks run for every matched rule, in evaluation order. Under AllMatch, multiple hooks may run; under FirstMatch, at most one.
- Hooks are suppressed in simulation mode (Section 12.3) and in replay modes that do not re-execute effects.
- A hook MUST be optional. A conformant implementation MUST allow on_match to be omitted with no behavior change other than the absence of the hook.

---
### 11.6 Cancellation and timeout recognition

Cancellation and timeout are **interruptions**, not exceptions. They are distinct from ordinary failures and from recovery. This section defines them.

#### 11.6.1 Cooperative cancellation

A conformant implementation MUST support cooperative cancellation. A cancellation request is signalled through the host language mechanism: CancellationToken in C#, asyncio.CancelledError or a context flag in Python, context.Context in Go, AbortSignal in TypeScript.

Rules:

- Cancellation is checked between rule evaluations. The exact points of check are implementation-defined, but the check MUST occur at least at the start of each rule evaluation and after each action completes.
- A cancellation request MUST NOT be silently ignored. If cancellation is observed, the flow MUST transition to CANCELLED (Section 7.3.1).
- A cancellation request MUST NOT be treated as an exception. Ordinary catch rules MUST NOT catch a cancellation. If an implementation models cancellation as an exception internally (asyncio.CancelledError in Python), it MUST distinguish it from application exceptions before catch rules run. A catch registered for Exception MUST NOT catch CancelledError.
- Cancellation observed during a condition evaluation MUST terminate evaluation immediately. The condition is not re-evaluated.
- Cancellation observed during a finalizer is treated separately (Section 11.8).

#### 11.6.2 Timeout recognition

A conformant implementation MUST recognize externally-imposed timeouts. It MUST NOT implement timeout enforcement.

Rules:

- A timeout is imposed by the application or by a separate resilience component (such as the Portfolio.Resilience library). The FlowSemantics library does not set timers, does not check wall-clock deadlines, and does not impose timeouts on its own.
- When an execution is interrupted by an externally-imposed timeout, the flow transitions to TIMED_OUT (Section 7.3.1) with an InterruptionInfo whose kind is timed_out.
- A timeout MUST NOT be treated as an exception. Ordinary catch rules MUST NOT catch it.
- The library MUST distinguish timeout from cancellation. They are different execution states with different finalization semantics (Section 11.8).

#### 11.6.3 What interruption is not

- An interruption is **not** a catchable exception. It bypasses catch rules.
- An interruption is **not** recovery. Recovery applies to exceptions only.
- An interruption is **not** stored under recovery. It is stored under interruption (Section 3.3).
- An interruption is **not** silently dropped. It is visible in the outcome and in the trace.

### 11.7 Async execution parity

A conformant implementation MUST provide both synchronous and asynchronous execution methods: execute() and execute_async().

Rules:

- The synchronous path and the asynchronous path MUST produce identical outcomes for the same contract and input, except for the timing of interruption observation.
- Short-circuiting behavior MUST be identical: FirstMatch mode short-circuits on the first match in both paths.
- Trace content MUST be identical in structure, though timestamps will differ.
- An async condition that never awaits is still an async condition. The library MUST await it. An implementation MUST NOT attempt to run async conditions synchronously.
- A pipeline that registers async finalizers (finally_async) produces an async-only contract. At compile time, the contract is classified as async-only and this classification is recorded as metadata on the contract. At invocation time, execute() on an async-only contract MUST fail with a clearly named error (an AsyncOnlyContractError or equivalent). execute_async() is the only permitted entry point for an async-only contract. The error is raised when the caller invokes the wrong method, not at compile time, because compile time has no invocation to reject.
- User-supplied callbacks (conditions, transformations, catch handlers, hooks) MUST be awaited if they are async. A conformant implementation MUST NOT silently skip awaiting them.

### 11.8 Finally and interruption separation

This section defines the outcome-aware finalization phase and, critically, the separation between interruption and recovery. It is referenced by Section 7.3.2 and by Section 3.5.

#### 11.8.1 Finally

**finally_(cleanup).** Registers a finalizer that runs after the primary execution, regardless of outcome, including cancellation and timeout.

The finalizer receives a FinallyContext with:

- **Result** - the sealed primary outcome.
- **Status** - the ExecutionStatus.
- **Value** - the value, read-only. Finally MUST NOT change it.
- **Exception** - the primary exception, if any.
- **Context** - the typed input from the flow.
- **CancellationToken** - a fresh cancellation token, optionally bounded by WithFinallyTimeout (Section 16.7).

#### 11.8.2 The invariants

The following invariants MUST hold under every policy:

- **FR1.** If cleanup succeeds, the final outcome is identical to the primary outcome under every policy.
- **FR2.** If cleanup fails, its exception is always recorded in secondary_exceptions and in the trace. It MUST NOT be silently dropped.
- **FR3.** Cleanup exceptions never trigger catch handlers and never re-enter rule evaluation.
- **FR4.** Finally cannot change the value or the status except through the ReplacePrimary policy on cleanup failure (Section 16.4).
- **FR5.** Finally runs for all canonical execution states, including CANCELLED and TIMED_OUT, with a fresh cancellation token.
- **FR6.** If cleanup is itself cancelled or times out, that is a cleanup failure under FR2. The interruption (cancellation or timeout) is recorded in the trace and, where applicable, in cleanup_budget_exceeded. An exception is recorded in cleanup_exceptions and secondary_exceptions only when the host language surfaces an exception for the interruption; if the host does not surface an exception, the cleanup failure is recorded only in the trace and in cleanup_budget_exceeded.
- **FR7.** A flow MAY register zero or more finalizers. When flows are merged, finalizers run in LIFO order (innermost first, outermost last), each isolated so a failure in one does not skip the rest. Each finalizer runs independently and receives its own fresh cancellation token.
- **FR8.** A flow MUST NOT mix synchronous and asynchronous finalizers. If any finally_async is registered, the contract is async-only. Calling execute() on an async-only contract MUST fail at invocation time with a clearly named error (Section 11.7). execute_async() is the only permitted entry point.

#### 11.8.3 The three finally failure policies

A conformant implementation MUST provide exactly these three policies, and no others:

The three policies determine what happens to the primary outcome when cleanup fails. They do NOT determine is_clean. Under every policy, is_clean is false if any finalizer raised an exception, was cancelled, or exceeded its budget; is_clean is true only if every finalizer completed normally within its budget. This is the single definition from Section 3.5, restated here as normative for the finalization section. The policy and is_clean are orthogonal: a policy that preserves the primary outcome does not make cleanup clean; only a cleanup that actually completed normally makes it clean.

- **PreservePrimary** (default). The primary outcome is preserved unchanged. Any cleanup exception is recorded in secondary_exceptions.
- **Attach.** The primary outcome is preserved unchanged. Any cleanup exception is recorded in secondary_exceptions. The policy is distinguished from PreservePrimary by its intent: Attach signals that the application should consciously notice the cleanup failure, whereas PreservePrimary treats cleanup as best-effort. Both policies produce is_clean=false when cleanup failed.
- **ReplacePrimary.** Under this policy, the treatment of cleanup failure depends on the primary ExecutionStatus. For an ordinary FAILED outcome, the cleanup exception becomes the primary reported failure, and the original exception moves to secondary_exceptions (both preserved). For COMPLETED, CANCELLED, and TIMED_OUT outcomes, the execution status is preserved as-is and the cleanup exception is recorded in secondary_exceptions; ReplacePrimary MUST NOT change COMPLETED to FAILED, and MUST NOT change CANCELLED or TIMED_OUT to FAILED (see Section 16.4 for the exact matrix).

#### 11.8.4 Interruption separation (B5, B3-a)

This is the normative statement of two critical decisions:

**B5 - Interruption is not stored under recovery.** When a flow is CANCELLED or TIMED_OUT, the outcome has a non-absent interruption (InterruptionInfo) and an absent recovery. Interruption information is NEVER stored in the recovery field.

**B3-a - ReplacePrimary preserves interruption.** Under every policy, a CANCELLED execution MUST retain ExecutionStatus CANCELLED, and a TIMED_OUT execution MUST retain ExecutionStatus TIMED_OUT. ReplacePrimary MUST NOT change CANCELLED to FAILED, and MUST NOT change TIMED_OUT to FAILED. Both the interruption information and the cleanup exception remain accessible. The full policy matrix is in Section 16.4.

#### 11.8.5 Merge and LIFO ordering

When flows are merged (Section 10.7), finalizers run in LIFO order: the innermost finalizer runs first, then the next, then the outermost. Each finalizer is isolated: a failure in one finalizer MUST NOT prevent the others from running.

Each finalizer receives its own fresh cancellation token, bounded by WithFinallyTimeout (Section 16.7) on every execution path. One finalizer cancelling its token MUST NOT cancel the tokens of the others.

---
## Section 12 - Trust semantics

This section defines the trace, the explanation, the simulation, the replay, the shadow evaluation, the validation, and the versioning and clock capabilities. These are the trust layer - the capabilities that make a flow's behavior inspectable and reproducible.

### 12.1 Trace vocabulary

A trace is an ordered list of TraceEvent values (Section 3.8). Each event has a type from this canonical vocabulary, and no others:

- condition_evaluated - a condition was evaluated and produced a boolean result.
- condition_raised - a condition raised an exception.
- guard_evaluated - a guard was evaluated.
- action_executed - a rule action produced a value.
- action_raised - a rule action raised an exception.
- catch_matched - a catch rule matched an exception by type.
- catch_predicate_evaluated - a catch_when predicate was evaluated.
- catch_predicate_raised - a catch_when predicate raised an exception.
- catch_handled - a catch handler recovered an exception.
- catch_declined - a catch rule declined an exception.
- rethrow_reached - a rethrow rule was reached.
- hook_invoked - an on_match hook was invoked.
- hook_raised - an on_match hook raised an exception.
- effect_proposed - an effect was added to the proposed-effects list.
- skipped_by_short_circuit - a rule was not evaluated because an earlier rule matched under FirstMatch.
- skipped_by_mode - a rule was not evaluated because the evaluation mode excluded it.
- finally_started - a finalizer was entered.
- finally_completed - a finalizer completed normally.
- finally_raised - a finalizer raised an exception.
- cancelled_observed - a cancellation request was observed.
- timed_out_observed - an externally-imposed timeout was observed.
- rule_skipped - a rule was skipped. The specific reason is recorded in the event's reason field.

#### 12.1.1 Reason enumeration

The reason field (Section 3.8) is required for the three skip event types and optional for all others. When present, its value MUST come from the following closed enumeration. Implementations MUST NOT use reason values outside this list.

For rule_skipped:
- condition_false - the rule condition evaluated to false.
- guard_blocked - the rule guard prevented the rule from running.
- not_effective - the rule was not active at the current injected wall-clock time (Section 12.9).

For skipped_by_short_circuit:
- earlier_match - an earlier rule matched and evaluation short-circuited under FirstMatch mode (Section 10.6).

For skipped_by_mode:
- mode_excluded - the evaluation mode excluded this rule from consideration (Section 10.6).

Adding a new reason value requires an ADR and a version bump (Section 8.2). The reason field is absent for all other event types; if an implementation adds it, it MUST use one of the values above or document an extension under an ADR.

Trace event types MUST NOT be added without an ADR and a version bump (Section 8.2).

### 12.2 Trace privacy

Trace events MUST NOT contain input values, secrets, exception messages, or any application data by default. The fields listed in Section 3.8 (type, rule_id, timestamp) are the maximum default content.

An application MAY opt in to additional diagnostic data by passing a redaction-aware diagnostic hook. The hook is application-supplied. The library MUST NOT decide what to redact; it MUST defer to the application's policy. Absent a hook, the default is no diagnostic data.

### 12.3 Trace opt-in

Tracing is disabled by default. The with_trace() method enables tracing for a specific execution. Trace collection MUST be zero-cost when disabled - no allocation, no clock read, no event construction.

### 12.4 Explanation

The explain() method renders a trace as a human-readable string. The rationale MUST be derived only from the registered rule metadata and the trace events. The library MUST NOT invent reasons that are not derivable from the metadata.

Example: if a rule's condition matched, the explanation says 'Condition matched'. It does not say 'Condition matched because the order total was high' - that would be invented. Only if the rule's declared metadata includes a human-readable description of the condition may the explanation include that description.

### 12.5 Simulation

The simulate() method evaluates a flow against an input without applying effects, invoking hooks, or invoking finalizers.

Rules:

- Simulation MUST NOT invoke an EffectExecutor.
- Simulation MUST NOT invoke on_match hooks.
- Simulation MUST NOT invoke finalizers.
- Simulation MUST NOT consume a cancellation token from the outer scope. It runs with its own cancellation token.
- Simulation MUST produce the same decision semantics as a real execution for the same input and injected clock value, except that finalization is not performed.

A finalizer that must run during simulation is outside the simulation contract. Applications that need finalizer behavior must perform a real execution, not a simulation.

### 12.6 Replay

The replay() method reproduces a past decision from a recorded tuple (specification version, flow contract version, input, clock value, trace, recorded effects).

Replay is four distinct operations. The library MUST provide all four, and MUST NOT conflate them:

1. **Simulation replay** - evaluate the flow against the recorded input and clock value, producing a new outcome for comparison. Performs no effects. MUST NOT touch real effect executors.
2. **Historical replay** - read the recorded outcome and trace. Performs no evaluation. Returns the recorded data. Useful for audit.
3. **Decision replay** - evaluate the flow decision without applying effects, then compare against the recorded outcome. Provides semantic equivalence, not bit-for-bit equivalence.
4. **Effect re-execution** - explicitly apply the recorded effects through an authorized EffectExecutor. This is the only mode that touches the application's effect boundary. It requires explicit authorization and MUST NOT be the default.

Rules:

- The replay guarantee is semantic equivalence, not bit-for-bit equivalence. This is the reviewer's A5 correction. Two executions that produce the same ExecutionStatus, DecisionStatus, value, recovery, and interruption are semantically equivalent, even if their byte representations differ.
- Replay MUST fail closed if the recorded specification version does not match the current specification version. Silent acceptance of a mismatched record is not permitted (Section 9.5).
- Replay MUST fail closed if the recorded flow contract version does not match the current contract. A FlowContract version is a hash of the contract's structural content. The hash algorithm MUST be documented by the implementation; the algorithm and its output representation MUST be versioned so that a future change to either does not silently invalidate existing replay records.
- Replay records MUST be integrity-protected against unauthorized modification. An implementation MUST support at least one of the following: a keyed message-authentication mechanism such as HMAC; a digital signature mechanism; or an application-supplied integrity mechanism that provides equivalent tamper detection. An unkeyed hash alone MUST NOT be presented as sufficient protection against malicious tampering, because an attacker who can modify the record may also recompute the hash.

### 12.7 Shadow evaluation

The shadow() method evaluates a candidate flow against a set of historical inputs before the candidate is deployed, and reports the differences.

Rules:

- Shadow evaluation MUST NOT apply effects. The candidate flow's proposed effects are recorded, not executed.
- Shadow evaluation MUST produce a comparison report: for each input, the observed outcome from the current flow and the observed outcome from the candidate.
- Shadow evaluation MUST be deterministic. The same inputs, the same flow contract versions, and the same clock values MUST produce the same report.

### 12.8 Validation

The validate() method performs static analysis on a flow without executing it.

A conformant implementation MUST validate at compile time (Section 4.3) at minimum:

- RuleId presence and uniqueness.
- At least one rule or fallback.
- catch_any ordering.
- Finalizer form consistency (async vs sync).
- EvaluationMode compatibility on merge.
- Effective date ordering.

A conformant implementation MAY additionally validate:

- Unreachable rules (rules whose condition is contradictory with earlier rules in FirstMatch mode).
- Overlapping decision-table rows under UNIQUE policy.
- Coverage gaps when the input type declares a closed domain.

Validation results distinguish errors (MUST fix) from warnings (SHOULD investigate). The distinction is normative: a validation result that reports a warning must not block compilation; a validation result that reports an error must block compilation.

### 12.9 Versioning and effective dates

Every FlowContract has a version - a hash of its structural content. The contract version is recorded at the trace level (Section 3.8) and MAY be repeated on individual trace events. It is also recorded in every replay record.

Rules can have effective dates: effective_from and effective_until. A rule with effective dates is considered active only when the current injected wall clock value falls within the interval (inclusive of effective_from, exclusive of effective_until). A rule that is not active is skipped with a trace event of type rule_skipped (reason: not_effective).

Effective date ordering MUST be validated at compile time (Section 4.3).

### 12.10 Deterministic clock and replay

The injected clock (Section 6.2) is the sole source of time for trace timestamps, effective-date comparison, and elapsed measurement. It is recorded in every replay record. Replay uses the recorded clock value, not the current clock value.

---

## Section 13 - Performance rules

### 13.1 Compiled equals interpreted

If an implementation provides a compiled execution path (compile() to a fused delegate, or equivalent), the compiled path MUST produce the same outcome as the interpreted path for every input. This is a MUST, not a SHOULD. A compiled path that differs from the interpreted path - even in edge cases - is not conformant.

### 13.2 Allocation goals

An implementation SHOULD minimize per-execution allocation on the common path (no trace, first-match, no exceptions, no finalization). A zero-allocation common path is RECOMMENDED but not required. An implementation that allocates per-execution on the common path MUST document the allocation and the reason.

### 13.3 Benchmarking rules

An implementation MUST NOT publish performance claims that are not backed by a reproducible benchmark. Any speed comparison (to native code, to another library, to another version of this library) MUST:

- Be measured by a benchmark that is committed to the repository.
- Use the same hardware and software configuration across comparisons.
- Report p50, p95, and p99 latency, not just mean.
- Report allocations and throughput in addition to latency.
- Be reproducible: the benchmark data and the harness MUST be available.

A performance claim that cannot be reproduced from the repository is not a claim; it is a marketing statement, and the specification does not endorse it.

### 13.4 The 3-5x speedup hypothesis

An earlier research pass proposed a fixed 3-5x speedup for a compiled path relative to an interpreted path. That figure is a hypothesis, not a promise. An implementation MUST NOT publish it as a claim without independent benchmarking. If the benchmark shows a different factor, the published figure is the measured one.

This is the discipline: measure first, publish second. Do not assert what has not been verified.

---
## Section 14 - Cross-language

This section defines how multiple language implementations of FlowSemantics stay in sync. It is the contract that makes the cross-language thesis possible.

### 14.1 Governance

The specification is the authority. Implementations are conforming implementations of the specification. No implementation, in any language, is the definition of FlowSemantics.

This has practical consequences:

- A behavior that is not in this specification is not a FlowSemantics behavior, even if one implementation happens to have it.
- A behavior that is in this specification must be implemented by every conformant implementation, even if the first implementation did not have it.
- A change to the specification follows Section 8. A change to any implementation does not change the specification.

### 14.2 Portable IR

The Portable IR is a canonical representation of a compiled FlowContract. A contract that is classified PORTABLE (Section 4.4) may be exported to the Portable IR and executed by any conformant implementation.

The Portable IR carries:

- The specification version it conforms to.
- The flow identifier.
- The portability classification.
- The ordered rule list, where each rule carries: a RuleId, a declarative condition (Section 5.1 pure conditions expressed in the portable expression subset), a declarative transformation, and any proposed effects.
- The EvaluationMode.
- The fallback configuration, if any.
- The effective date interval, if any.

The Portable IR MUST NOT carry:

- Host-language lambdas or closures.
- Serialized executable code in any form.
- References to host-language types not defined in the portable expression subset.
- The compiled execution plan (compilation is per-language).

The portable expression subset is deliberately small and inspectable. It supports:

- Named field access (read-only).
- Comparisons: equal, not-equal, less-than, less-than-or-equal, greater-than, greater-than-or-equal.
- Boolean composition: and, or, not.
- Null checks: is-null, is-not-null.
- Enum membership: in, not-in.

The expression subset MUST NOT be extended without an ADR and a version bump. Adding operators is a minor version change; adding expression types that change the shape of the IR is a major version change (Section 8.3).

The schema for the Portable IR is published at spec/ir.schema.json (Phase 0.5 deliverable).

### 14.3 Conformance vectors and fixtures

A conformance vector is a single test case, expressed in language-agnostic JSON, matching spec/vector.schema.json. Every MUST in this specification MUST be covered by at least one vector. Non-MUST behaviors (SHOULD, MAY) SHOULD be covered where practical. Every MUST has at least one vector that would fail if the MUST were violated.

Vectors reference fixtures by name, not by code. A fixture is a named test double (cond.true, cond.false, action.const(v), cleanup.throws(Kind), and so on) whose behavior is defined in spec/fixtures.md. Each language adapter resolves fixture names to host-language equivalents. This is what makes vectors genuinely language-agnostic (D17).

Vectors MUST use the abstract error kinds (Kind.Timeout, Kind.Cancelled, Kind.ValueError, Kind.Any) rather than host-language exception types. Each adapter maps these abstract kinds to its language concrete exception types.

### 14.4 The conformance runner protocol

Every language implementation ships a conformance runner that:

- Loads vectors from conformance/vectors/.
- Validates each vector against spec/vector.schema.json.
- Resolves fixtures using the language fixture map.
- Executes the pipeline described by the vector.
- Compares the observed outcome against the expected outcome.
- Compares the observed trace against the expected trace (if present).
- Reports pass or fail per vector.
- Returns exit code 0 if and only if all vectors pass.

The full protocol is defined at conformance/runner-protocol.md. Phase 0.0 delivered the stub; Phase 0.5 finalizes it.

**No implementation is conformant below 100% of vectors.** This is a MUST. An implementation that passes 99 of 100 vectors is not conformant.

### 14.5 Phased language rollout

The specification does not prescribe which languages to implement, but it does prescribe how:

- A new language implementation is built strictly against the conformance vectors. It MUST pass 100% of vectors before being published as conformant.
- The implementation MUST NOT add behaviors that are not in the specification, even if they seem convenient.
- The implementation MAY add optional behaviors as documented extensions, but they MUST NOT be advertised as part of FlowSemantics conformance.
- A new implementation SHOULD start from the specification and vectors, not from an existing implementation code. The specification is the source of truth.

The recommended order (from the implementation plan) is Python first, then TypeScript, Go, Java, Rust. This is a recommendation, not a normative requirement.

### 14.6 What the specification does not specify

The specification does not specify:

- The exact API signatures beyond the semantics (for example, whether when takes a lambda or a Protocol, whether compile is a method or a function).
- The exception hierarchy (each language uses its own).
- The error message text.
- The trace rendering format (explain returns a string; the format is implementation-defined).
- The build system, packaging, or distribution mechanism.

The specification specifies semantics and observable behavior. Everything else is implementation freedom, constrained only by the semantics.

---

## Section 15 - Enterprise requirements

This section defines what a conformant implementation must do to be considered enterprise-ready. These are not optional capabilities; they are normative requirements for the enterprise conformance tier.

### 15.1 Dependency policy

A conformant implementation MUST NOT impose any third-party runtime dependency on consumers. The core library MUST resolve to the standard library of its host language only. This is a MUST, not a SHOULD.

Build-time tools (for example, hatchling in Python) and development-time tools (ruff, mypy, pytest) are permitted. They MUST NOT be required at runtime by consumers.

An implementation that requires a third-party runtime dependency is not conformant. This is the strictest version of the policy, and it is the one that this specification adopts.

### 15.2 No hidden network, no hidden telemetry

The core library MUST NOT perform any network access. It MUST NOT emit any telemetry, metrics, or logging to an external destination by default.

Diagnostics MAY be emitted through the host language native diagnostics mechanism (for example, System.Diagnostics in C#, logging module in Python, slog in Go, OpenTelemetry in TypeScript). These diagnostics MUST be inert unless the application explicitly attaches a listener.

An implementation that phones home, collects metrics, or opens any network connection from the core library is not conformant.

### 15.3 Software bill of materials (SBOM)

Every release MUST include a CycloneDX or SPDX software bill of materials, listing every build-time and development-time dependency with its version and license.

The SBOM MUST be reproducible from the repository at the release commit. A consumer MUST be able to verify the SBOM by re-running the SBOM generation tool against the release tag.

### 15.4 Threat model and disclosure process

Every implementation MUST publish a threat model document that covers, at minimum:

- Malformed rule graphs from the Portable IR.
- Deserialization attacks via the IR.
- Resource exhaustion via pathological rule sets.
- Replay-record tampering.
- The library security boundaries (what it does and does not do).

Every implementation MUST publish a security disclosure process (SECURITY.md or equivalent) describing how a vulnerability is reported, how it is acknowledged, and how it is fixed and disclosed.

### 15.5 Non-goals (restated)

Section 1.3 lists the normative exclusions. They are restated here for the enterprise reader:

- No authentication or authorization.
- No database, ORM, or persistence.
- No message broker or distributed workflow scheduler.
- No durable workflow engine.
- No payment processor.
- No API gateway or cloud control plane.
- No AI or LLM runtime.
- No hidden retries.
- No hidden network activity.
- No default telemetry.
- No mandatory visual editor.
- No replacement of native control flow.

An implementation that includes any of these as part of its core is not conformant. They MAY be offered as separate companion packages, but they MUST NOT be in the core.

### 15.6 Semantic versioning and compatibility

The implementation follows semantic versioning. A patch release fixes bugs without changing behavior. A minor release adds compatible features. A major release changes behavior or public API.

The specification has its own version, tracked separately (Section 8). An implementation version records which specification version it conforms to, as metadata.

Every release MUST include a migration guide for any breaking change, even if the change is small. The migration guide MUST state what changed, why, and what a consumer must do to upgrade.

### 15.7 The honesty discipline

Enterprise software vendors often make claims that are not backed by evidence. This specification forbids that practice in the FlowSemantics context.

- No performance claim without a committed, reproducible benchmark (Section 13.3).
- No security claim beyond the documented threat model.
- No conformance claim below 100% of vectors.
- No claim that the library replaces native control flow.
- No claim that the library is 'the industry standard' - it is one specification among many, and standard status is earned through adoption, not asserted.

Where the library cannot do something (for example, enforce purity in a general-purpose language), the documentation says so clearly. Where the library guarantees are bounded (for example, the cleanup timeout is cooperative, not a hard kill), the documentation says so clearly.

This honesty is not marketing weakness. It is a design discipline that makes the library trustworthy. A library that overpromises is a library that will fail in production.

---
## Section 16 - Finalization

This section defines the outcome-aware finalization phase in full. It resolves the references from Section 7.3.2 (the transition table) and Section 11.8.4 (interruption separation) to a complete policy matrix.

Sections 16.1 through 16.3 define the context, the invariants, and the three policies. Section 16.4 (Part 4c) provides the full policy matrix for every combination of primary status and cleanup outcome. Sections 16.5 through 16.7 (Part 4c) define interruption preservation, merge ordering, and the WithFinallyTimeout rules.

### 16.1 The FinallyContext

The finalizer receives a context with the following fields. All fields are read-only from the finalizer perspective.

| Field | Type | Meaning |
|---|---|---|
| Result | FlowOutcome | The sealed primary outcome. Read-only. |
| Status | ExecutionStatus | One of COMPLETED, FAILED, CANCELLED, TIMED_OUT. |
| Value | output type or absent | The result value if any. The finalizer MUST NOT change it. |
| Exception | exception or absent | The primary exception, if any. |
| Context | input type | The subject and threaded state from the flow. This is how the finalizer accesses resources (transactions, file handles) that the flow threaded through. |
| CancellationToken | cancellation token | A fresh token bounded by WithFinallyTimeout (Section 16.7). The budget applies to every finalizer execution; the default is 5000 milliseconds when not configured. This is not the outer cancellation token; the finalizer receives its own. |

**The finalizer receives a FRESH cancellation token.** This is normative. A cleanup that runs after a cancellation must not be cancelled by the very cancellation it is cleaning up after. The fresh token is provided for the finalizer to bound its own work, not to propagate the outer cancellation.

**The finalizer cannot change the value.** The finalizer receives the primary value as read-only where the host language and implementation permit read-only enforcement. The implementation MUST document the degree of read-only enforcement provided. Where the host language cannot prevent mutation of an arbitrary value, the implementation MUST NOT claim that mutation is prevented. The finalizer cannot change the primary outcome except through the ReplacePrimary policy on cleanup failure (Section 16.4).

### 16.2 The invariants

These invariants MUST hold across every policy, every status, and every cleanup outcome. An implementation that violates any of them is not conformant.

**FR1 (cleanup success preserves outcome).** If cleanup succeeds, the final outcome is identical to the primary outcome under every policy. There is no scenario where a successful cleanup changes the outcome.

**FR2 (cleanup exception is never lost).** If cleanup fails, its exception is recorded in secondary_exceptions and in the trace. It MUST NOT be silently dropped. This holds under every policy.

**FR3 (cleanup exceptions are isolated).** A cleanup exception MUST NOT trigger a catch rule. It MUST NOT re-enter rule evaluation. It MUST NOT be caught by any user-registered catch. It is recorded and, if the policy dictates, promoted or not; but it never enters the flow's exception handling.

**FR4 (finalizer cannot mutate the value).** The finalizer MUST NOT change the value or the status. The only permitted effect of a finalizer failure is through the ReplacePrimary policy on a primary FAILED outcome (Section 16.4). Under ReplacePrimary on a primary FAILED outcome, the cleanup exception becomes primary_exception and the original exception moves to secondary_exceptions; the value remains absent. For COMPLETED, CANCELLED, and TIMED_OUT outcomes, the primary outcome (status and value) is preserved regardless of policy. ReplacePrimary does not cause a value to be discarded under any status.

**FR5 (finalization runs for all terminal states).** Finalization runs for every canonical execution state: COMPLETED, FAILED, CANCELLED, TIMED_OUT. This includes cancellation and timeout. The implementation MUST NOT skip finalization for any of these.

**FR6 (cleanup can itself fail by cancellation or timeout).** If cleanup is cancelled or times out, that is a cleanup failure under FR2. The interruption (cancellation or timeout) is recorded in the trace and, where applicable, in cleanup_budget_exceeded. An exception is recorded in cleanup_exceptions and secondary_exceptions only when the host language surfaces an exception for the interruption; if the host does not surface an exception, the cleanup failure is recorded only in the trace and in cleanup_budget_exceeded. The primary outcome status is not changed by this, except through ReplacePrimary on a primary FAILED outcome per Section 16.4.

**FR7 (zero or more finalizers per flow, LIFO on merge).** A flow MAY register zero or more finalizers. When flows are merged, finalizers run in LIFO order: the innermost finalizer runs first, then the next, then the outermost. Each finalizer is isolated: a failure in one MUST NOT prevent the others from running. Each finalizer runs independently and receives its own fresh cancellation token.

**FR8 (async finalizer requires async execution).** A pipeline that registers finally_async MUST be executed only via execute_async. Calling execute() on a pipeline with an async finalizer is a compilation error (Section 4.3).

### 16.3 The three policies

A conformant implementation MUST provide exactly these three policies, and no others. The policy is configured on the flow at construction time (with_finally_policy) and is recorded in the flow contract.

The three policies determine what happens to the primary outcome when cleanup fails. They do NOT determine is_clean. Under every policy, is_clean is false if any finalizer raised an exception, was cancelled, or exceeded its budget; is_clean is true only if every finalizer completed normally within its budget. This is the single definition from Section 3.5, restated here as normative for the finalization section. The policy and is_clean are orthogonal: a policy that preserves the primary outcome does not make cleanup clean; only a cleanup that actually completed normally makes it clean.

**PreservePrimary (default).** The primary outcome is preserved unchanged. Any cleanup exception is recorded in secondary_exceptions. This is the default and is appropriate when cleanup is best-effort (log flush, metric emission, cache release) and a cleanup failure should not alter the caller-visible outcome.

**PreservePrimary and Attach are observationally equivalent in specification version 0.1.** Both preserve the primary outcome, both record any cleanup exception in secondary_exceptions, and both produce is_clean=false when cleanup fails. The two policies are distinguished by intent (PreservePrimary is best-effort; Attach signals that the caller should consciously notice the cleanup failure), but no conformance vector can distinguish their outcomes. Future specification versions MAY give Attach an observable distinction; in version 0.1, the distinction is documentation-only.

**Attach.** The primary outcome is preserved. Any cleanup exception is recorded in secondary_exceptions. The policy is distinguished from PreservePrimary by its intent: Attach signals that the application should consciously notice the cleanup failure, whereas PreservePrimary treats cleanup as best-effort. Both policies produce is_clean=false when cleanup failed. This policy is appropriate when the caller must consciously decide whether to act on the cleanup failure (for example, a commit acknowledgment).

**ReplacePrimary.** The behavior depends on the primary ExecutionStatus. The full treatment is specified in Section 16.4 (the policy matrix). The summary is:

- For a primary FAILED outcome, the cleanup exception becomes the primary reported exception, and the original exception is moved to secondary_exceptions. Both remain accessible.
- For COMPLETED, CANCELLED, or TIMED_OUT outcomes, the execution status is preserved as-is. ReplacePrimary MUST NOT change COMPLETED to FAILED, MUST NOT change CANCELLED to FAILED, and MUST NOT change TIMED_OUT to FAILED. The cleanup exception is recorded in secondary_exceptions. This is the invariant B3-a (Section 11.8.4), restated here as a normative requirement of Section 16.

The three policies are mutually exclusive per flow. Configuring more than one is a compilation error.

---
### 16.4 The full policy matrix

This section is the authoritative policy matrix for finalization. Sections 7.3.2 and 11.8.4 reference it. Every combination of primary ExecutionStatus and cleanup outcome is specified here.

Legend for the following tables:

- **ES** = ExecutionStatus of the final outcome.
- **DS** = DecisionStatus of the final outcome.
- **Value** = the value of the final outcome.
- **PrimEx** = the primary_exception field.
- **SecEx** = the secondary_exceptions collection.
- **is_clean** = the FinalizationInfo.is_clean field.

Under every policy and every case, is_clean is false whenever any finalizer raised an exception, was cancelled, or exceeded its budget. The is_clean column is false for every case where cleanup fails, under every policy. The only rows where is_clean is true are those where cleanup succeeds (Cases 1 and 2).

#### 16.4.1 Case 1 - Primary COMPLETED, cleanup succeeds

This case is policy-independent. All three policies produce identical outcomes.

| Field | Value |
|---|---|
| ES | COMPLETED |
| DS | from primary |
| Value | from primary |
| PrimEx | absent |
| SecEx | empty |
| is_clean | true |

#### 16.4.2 Case 2 - Primary FAILED, cleanup succeeds

This case is policy-independent.

| Field | Value |
|---|---|
| ES | FAILED |
| DS | absent |
| Value | absent |
| PrimEx | the primary exception |
| SecEx | empty |
| is_clean | true |

#### 16.4.3 Case 3 - Primary COMPLETED, cleanup fails

The three policies produce different outcomes.

**PreservePrimary:**

| Field | Value |
|---|---|
| ES | COMPLETED |
| DS | from primary |
| Value | from primary |
| PrimEx | absent |
| SecEx | [cleanup exception] |
| is_clean | false |

**Attach:**

| Field | Value |
|---|---|
| ES | COMPLETED |
| DS | from primary |
| Value | from primary |
| PrimEx | absent |
| SecEx | [cleanup exception] |
| is_clean | false |

**ReplacePrimary:**

| Field | Value |
|---|---|
| ES | COMPLETED |
| DS | from primary |
| Value | from primary |
| PrimEx | absent |
| SecEx | [cleanup exception] |
| is_clean | false |

**Normative note:** For a primary COMPLETED outcome, ReplacePrimary MUST NOT change ES to FAILED. The cleanup exception is recorded, is_clean is set false, but the caller-visible outcome remains COMPLETED with the original value.

#### 16.4.4 Case 4 - Primary FAILED, cleanup fails

This is the only case where ReplacePrimary changes which exception is primary.

**PreservePrimary:**

| Field | Value |
|---|---|
| ES | FAILED |
| DS | absent |
| Value | absent |
| PrimEx | the primary exception (unchanged) |
| SecEx | [cleanup exception] |
| is_clean | false |

**Attach:**

| Field | Value |
|---|---|
| ES | FAILED |
| DS | absent |
| Value | absent |
| PrimEx | the primary exception (unchanged) |
| SecEx | [cleanup exception] |
| is_clean | false |

**ReplacePrimary:**

| Field | Value |
|---|---|
| ES | FAILED |
| DS | absent |
| Value | absent |
| PrimEx | the cleanup exception (new primary) |
| SecEx | [original primary exception] |
| is_clean | false |

**Normative note:** Under ReplacePrimary with a primary FAILED outcome, both exceptions remain accessible. The original primary exception is not lost; it is moved to secondary_exceptions. This is the invariant B7.

#### 16.4.5 Case 5 - Primary CANCELLED, cleanup fails

**This is the case where B3-a is most important.** ReplacePrimary MUST NOT change CANCELLED to FAILED.

**PreservePrimary:**

| Field | Value |
|---|---|
| ES | CANCELLED |
| DS | absent |
| Value | absent |
| PrimEx | absent |
| SecEx | [cleanup exception] |
| is_clean | false |
| Interruption | present, kind=cancelled |

**Attach:**

| Field | Value |
|---|---|
| ES | CANCELLED |
| DS | absent |
| Value | absent |
| PrimEx | absent |
| SecEx | [cleanup exception] |
| is_clean | false |
| Interruption | present, kind=cancelled |

**ReplacePrimary:**

| Field | Value |
|---|---|
| ES | CANCELLED |
| DS | absent |
| Value | absent |
| PrimEx | absent |
| SecEx | [cleanup exception] |
| is_clean | false |
| Interruption | present, kind=cancelled |

**Normative note (B3-a, restated):** For a primary CANCELLED outcome, ReplacePrimary MUST NOT change ES to FAILED. The interruption is preserved. The cleanup exception is recorded in secondary_exceptions. The execution status remains CANCELLED.

#### 16.4.6 Case 6 - Primary TIMED_OUT, cleanup fails

Same structure as Case 5, with TIMED_OUT and kind=timed_out.

**PreservePrimary:**

| Field | Value |
|---|---|
| ES | TIMED_OUT |
| DS | absent |
| Value | absent |
| PrimEx | absent |
| SecEx | [cleanup exception] |
| is_clean | false |
| Interruption | present, kind=timed_out |

**Attach:**

| Field | Value |
|---|---|
| ES | TIMED_OUT |
| DS | absent |
| Value | absent |
| PrimEx | absent |
| SecEx | [cleanup exception] |
| is_clean | false |
| Interruption | present, kind=timed_out |

**ReplacePrimary:**

| Field | Value |
|---|---|
| ES | TIMED_OUT |
| DS | absent |
| Value | absent |
| PrimEx | absent |
| SecEx | [cleanup exception] |
| is_clean | false |
| Interruption | present, kind=timed_out |

**Normative note (B3-a, restated):** For a primary TIMED_OUT outcome, ReplacePrimary MUST NOT change ES to FAILED. The interruption is preserved.

### 16.5 Interruption preservation (B3-a, explicit)

The following is the normative statement of the B3-a decision. It is the invariant that Cases 5 and 6 above encode.

**Under every FinallyFailurePolicy, a CANCELLED execution MUST retain ExecutionStatus CANCELLED, and a TIMED_OUT execution MUST retain ExecutionStatus TIMED_OUT. No policy, including ReplacePrimary, may change CANCELLED or TIMED_OUT to FAILED.**

Rationale: Cancellation and timeout are interruptions, not exceptions. Changing them to FAILED would obscure the meaning of the execution status. The caller must be able to distinguish 'the operation failed with an exception' from 'the operation was cancelled' from 'the operation was interrupted by a timeout'. ReplacePrimary is a policy for changing which exception is primary; it is not a policy for converting interruptions into failures.

An implementation that allows ReplacePrimary to change CANCELLED to FAILED, or TIMED_OUT to FAILED, is not conformant.

### 16.6 Merge and LIFO ordering (detailed)

When flows are merged (Section 10.7), finalization follows this order:

1. The innermost flow's finalizer runs first.
2. Its result is observed. Any cleanup exception is recorded in secondary_exceptions, unless it is promoted to primary_exception by ReplacePrimary on a primary FAILED outcome (Section 16.4.4).
3. Then the next finalizer in the LIFO chain runs, with the current outcome as modified only by any applicable ReplacePrimary exception promotion under Section 16.4.4. No other field of the outcome is mutated by a finalizer.
4. This continues until the outermost finalizer has run.

Each finalizer is isolated: a failure in one MUST NOT prevent the others from running. Even if a finalizer raises, the next finalizer still runs.

Each finalizer receives its own fresh cancellation token, bounded by WithFinallyTimeout (Section 16.7) on every execution path. One finalizer cancelling its token MUST NOT cancel the tokens of the others.

### 16.7 WithFinallyTimeout (normative values)

The cleanup budget is the maximum time a finalizer is permitted to run. It is bounded by WithFinallyTimeout.

**Default value.** When WithFinallyTimeout is not configured, the default cleanup budget is 5000 milliseconds (5 seconds). This value is frozen in this specification version. A future version may change it only via a major version bump.

**Override.** WithFinallyTimeout(t) sets the budget to t. The value MUST be validated at compile time. t MUST be greater than zero. A zero or negative value is a compilation error.

**When the budget applies.** The cleanup budget is applied to every finalizer execution, regardless of the primary ExecutionStatus. The implementation supplies each finalizer with a fresh cancellation token bounded by the configured cleanup budget. The budget is a cooperative bound: it is signalled to the finalizer, and the finalizer is expected to observe the signal. The implementation does not forcibly terminate a finalizer that ignores the signal. When a finalizer exceeds its budget, the implementation records cleanup_budget_exceeded = true and continues. The budget is always present, always bounded, and always reported, but it is not a hard kill. Applications that have finalizers with legitimately longer cleanup requirements SHOULD override the default with an explicit WithFinallyTimeout value.

**What the budget guarantees.** The budget is a cooperative bound. The implementation provides the finalizer with a fresh cancellation token. The finalizer is expected to observe the token. If the finalizer does not observe the token and runs beyond the budget, the implementation does not forcibly terminate it (the host language may not permit that). The implementation records this in FinalizationInfo.cleanup_budget_exceeded = true and continues.

**What the budget does NOT guarantee.** The budget does NOT forcibly terminate arbitrary synchronous code. It does NOT guarantee that the finalizer stops. It does NOT promise a hard kill. This is the honest guarantee. It is normative that the implementation documents this honestly.

**Async finalizers.** For async finalizers, the budget is enforced by signalling cancellation to the async task at the deadline. An async finalizer that does not observe the cancellation signal behaves like a synchronous finalizer that does not observe its token: the implementation records cleanup_budget_exceeded = true and continues.

**Reporting.** FinalizationInfo.cleanup_budget_used reports the elapsed time as measured by the injected monotonic clock. FinalizationInfo.cleanup_budget_exceeded reports whether the budget was exceeded.

---
## Appendix A - Decision log

This appendix records every locked decision from the v5 feature baseline and points to the normative section where each is encoded. A change to any decision requires an ADR and a specification version bump (Section 8).

### Architectural decisions (D-series)

| ID | Decision | Normative location |
|---|---|---|
| D1 | ExecutionStatus and DecisionStatus are separate | Section 3.1, Section 3.2, Section 3.6 |
| D2 | Conditions and transformations are pure; effects are proposed data | Section 5.1, Section 5.2 |
| D3 | Portability classification is on the whole compiled contract | Section 4.4 |
| D4 | FinallyFailurePolicy is explicit | Section 16.3 |
| D5 | Native control flow stays native | Section 1.2 |
| D6 | Object of concern adoption rule | Section 1.2 |
| D7 | Code-defined vs data-defined logic | Section 10.8 |
| D8 | Performance is not the primary argument | Section 13 |
| D9 | One execution model | Section 3, Section 7 |
| D10 | Official philosophy: no replacement of native control flow | Section 1.2 |
| D11 | Signature consistency (handlers receive input) | Section 11.1 |
| D12 | ExecutionStatus naming | Section 3.1 |
| D13 | Two-stage lifecycle; Build returns immutable FlowContract | Section 4.1, Section 10.9 |
| D14 | Finally runs for all four canonical states with fresh token | Section 11.8.1, Section 16.1 |
| D15 | FinallyFailurePolicy executable; cleanup exception never lost | Section 16.2, Section 16.4 |
| D16 | Deterministic clock | Section 6.2 |
| D17 | Portable IR carries structure only, never host-language code | Section 14.2 |

### Baseline corrections (B-series)

| ID | Correction | Normative location |
|---|---|---|
| B1 | Timeout is recognized, not enforced | Section 11.6.2 |
| B2 | Portability classification on the whole contract | Section 4.4 |
| B3-a | ReplacePrimary preserves CANCELLED and TIMED_OUT | Section 11.8.4, Section 16.4, Section 16.5 |
| B3-b | WithFinallyTimeout default and override are normative | Section 16.7 |
| B3-c | Testability: 2 baseline + 12 policy-sensitive + 6 invariants = 20 vectors | Section 16.4 (all cases enumerated) |
| B4 | TIMED_OUT in canonical ExecutionStatus | Section 3.1 |
| B5 | Interruption is not stored under recovery | Section 3.3, Section 3.4, Section 11.8.4 |
| B6 | IsClean is finalization metadata | Section 3.5 |
| B7 | secondary_exceptions includes cleanup exceptions even when primary succeeded | Section 3.6, Section 16.4 |
| B8 | Cleanup timeout is cooperative, not a hard kill | Section 16.7 |

### Open question rulings (O-series)

| ID | Ruling | Normative location |
|---|---|---|
| O1 | Recovery is metadata, not terminal state | Section 3.4 |
| O2 | NO_MATCH is distinct from REJECTED; SKIPPED is reserved | Section 3.2 |
| O3 | Declarative conditions included, limited subset | Section 14.2 |
| O4 | Effect boundary in v0.1; full simulation and replay in v0.2+ | Section 12.5, Section 12.6 |
| O5 | unless is omitted from v0.1 | Section 10.3 |
| O6 | Flow* naming with FlowContract introduced | Section 2, Section 3, Section 4 |
| O7 | Python is first implementation, spec remains authoritative | Section 14.1 |

## Appendix B - Vector index (reference)

This appendix lists the conformance vector groups that will prove the normative behaviors in this specification. The vectors themselves are populated in Phase 0.5 and stored in conformance/vectors/.

| Group | Target count | Proves |
|---|---|---|
| Core decision | ~30 | Sections 10.1-10.5: when, when_not, otherwise, default, then |
| Evaluation modes | ~8 | Section 10.6: FirstMatch, AllMatch, Priority |
| Merge and DecisionTable | ~10 | Sections 10.7-10.9: mode compatibility, LIFO, hit policies |
| Error handling | ~25 | Sections 11.1-11.5: catch, catch_when, catch_any, rethrow, on_match |
| Interruption | ~10 | Sections 11.6-11.7: cancellation, timeout recognition, async parity |
| Finally | 20 | Section 16.4: 2 baseline cases + 4 policy-sensitive cases x 3 policies + 6 invariant vectors |
| Trace shape | ~15 | Section 12.1: canonical event types; zero cost when off |
| Simulation and replay | ~20 | Sections 12.5-12.7: no effects, semantic equivalence, fail-closed on version |
| Validation | ~10 | Section 12.8: unreachable rules, overlaps, coverage gaps |
| Security hardening | ~10 | Section 9.2: IR limits, duplicate ids, cyclic references |
| Total | ~158 | All normative MUSTs of Sections 1-16. This target supersedes the earlier estimate of ~150 from the implementation plan. |

Vector counts are targets, not frozen. The governing principle is: every MUST in this specification has at least one vector that would fail if the MUST were violated.

## Appendix C - Glossary

Key terms, cross-referenced to the section where each is defined normatively. For a complete list see Section 2.

| Term | Meaning | Defined in |
|---|---|---|
| Condition | A pure predicate over input; determines if a rule matches | Section 2.1, Section 5.1 |
| Conformance vector | A single language-agnostic test case | Section 2.2, Section 14.3 |
| DecisionStatus | APPROVED, REJECTED, or NO_MATCH; what the flow concluded | Section 3.2 |
| Effect | A description of an operation the application may perform | Section 2.1, Section 3.7 |
| ExecutionStatus | COMPLETED, FAILED, CANCELLED, or TIMED_OUT; what happened | Section 3.1 |
| Fixture | A named test double referenced by conformance vectors | Section 2.2, Section 14.3 |
| Flow | The mutable builder object | Section 2.1, Section 4.1 |
| FlowContract | The immutable compiled execution definition | Section 2.1, Section 4.1 |
| FlowOutcome | The structured result of an execution | Section 3.6 |
| FinalizationInfo | is_clean, cleanup exceptions, budget used, budget exceeded | Section 3.5 |
| Interruption | A cancellation request or externally-imposed timeout | Section 2.1, Section 11.6 |
| InterruptionInfo | kind, source, timestamp, deadline; not an exception | Section 3.3 |
| Portable IR | The canonical cross-language representation | Section 14.2 |
| Proposed effect | An effect proposed by a flow; not yet applied | Section 3.7 |
| Pure transformation | A function that computes a value without I/O | Section 2.1, Section 5.1 |
| Recovery | The handling of an exception by a catch rule | Section 2.1, Section 11.1 |
| RecoveryInfo | original_exception, handler_rule_id, recovered_at | Section 3.4 |
| Rule | A 4-tuple (RuleId, condition, guard, action) | Section 2.1, Section 10.1 |
| RuleId | A stable identifier attached to every rule | Section 2.1 |
| Simulation | Evaluation without effects or hooks | Section 12.5 |
| Trace | An ordered record of semantic events | Section 2.1, Section 12.1 |
| TraceEvent | A single event in a trace, with type and metadata | Section 3.8 |

---

**End of SPEC.md v0.1.**

Sections 1 through 16 plus Appendices A, B, C. The specification is complete. It is frozen for implementation by the sign-off at Phase 0.4.

