# ADR-0001: Governing decisions

**Status:** accepted

## Context

FlowSemantics is a zero-runtime-dependency, language-neutral execution-
semantics library. It has been through four review rounds. The decisions
recorded here are the ones that are expensive to reverse: they shape the
public API, the outcome model, the effect boundary, the portability
classification, and the finalization policy. They are recorded before any
implementation code is written.

## Decisions

### D1 - ExecutionStatus and DecisionStatus are separate

Execution status describes what happened while running (COMPLETED, FAILED,
CANCELLED, TIMED_OUT). Decision status describes what the flow concluded
(APPROVED, REJECTED, NO_MATCH). Combining them creates an unnecessarily
confusing outcome model.

**Rejected:** a single status enum. It confuses application decisions with
execution mechanics.

### D2 - Pure conditions and transformations; effects proposed only

Conditions and pure transformations must be pure. External operations are
proposed as data and applied only by an application-owned executor. The
library documents the purity contract; it cannot enforce it for arbitrary
callables.

**Rejected:** automatically executing effects during evaluation. It breaks
the central promise of the library and makes simulation unsafe.

### D3 - Native and portable flows; portability on the whole contract

Two flow modes: native (may contain opaque Python callables) and portable
(declarative only). Portability is a property of the entire compiled
FlowContract. A native flow may contain declarative conditions; one opaque
component makes the whole contract non-portable.

**Rejected:** per-component portability. It misleads developers about
whether a flow can be exported.

### B1 - Timeout is recognized, not enforced

FlowSemantics represents externally-imposed timeouts as TIMED_OUT. It does
not own timeout enforcement. Timeout and cancellation are different states.

**Rejected:** owning timeout policies. That belongs to a separate resilience
concern.

### B2 - Portability classification on the whole contract

See D3. The classification is computed from the compiled contract, not from
individual components.

### B3-a - ReplacePrimary preserves CANCELLED and TIMED_OUT

When cleanup fails under ReplacePrimary: for ordinary exception failures,
the cleanup exception becomes the reported failure. For cancellation or
timeout, the execution status is preserved (CANCELLED or TIMED_OUT), and
both the interruption information and the cleanup exception remain
accessible.

**Rejected:** changing CANCELLED or TIMED_OUT to FAILED. Cancellation and
timeout are interruptions, not exceptions.

### B3-b - WithFinallyTimeout is normative in SPEC.md

The default cleanup budget, the override rules, and the exact behavior when
the budget is exceeded are all frozen in SPEC.md (Phase 0.4). Not left as an
implementation guess.

### B3-c - Feature K testability

Finalization is tested with 2 baseline vectors (cleanup succeeds) + 12
policy-sensitive vectors (4 failure combinations x 3 policies) + 6 invariant
vectors = 20. The arithmetic is meaningful, not numeric.

### B4 - TIMED_OUT in canonical ExecutionStatus

ExecutionStatus is {COMPLETED, FAILED, CANCELLED, TIMED_OUT}. The phrase
"seven-state matrix" is retired. The single source of truth is SPEC.md
section 3.

### B5 - interruption is a separate outcome field

InterruptionInfo holds cancellation and timeout data. It is never stored
under recovery. RecoveryInfo is reserved for actual exception recovery.

**Rejected:** storing cancellation/timeout information under recovery. It
confuses two distinct concepts.

### B6 - IsClean is finalization metadata

IsClean appears only as finalization.is_clean. It is never a fifth status
or a composite status like "COMPLETED + IsClean = False".

### B7 - secondary_exceptions meaning

secondary_exceptions includes all non-primary exceptions, including cleanup
exceptions even when the primary execution succeeded. The field name is
precise: it means "exceptions other than the primary reported failure."

### B8 - Cleanup timeout guarantee is honest

The cleanup timeout establishes a maximum permitted budget. It is
cooperative: cooperative callbacks receive a fresh cancellation token at
the deadline. The library does NOT forcibly terminate arbitrary synchronous
code. Budget overruns are reported via finalization.cleanup_budget_exceeded.

**Rejected:** claiming a hard kill of arbitrary synchronous code. It would
be a promise the language cannot keep.

## Open question rulings

- O1 (APPROVED): recovery is metadata on the completed outcome, not a
  terminal state.
- O2 (AMENDED): NO_MATCH is distinct from REJECTED; SKIPPED is reserved
  for executions deliberately not performed.
- O3 (APPROVED): declarative conditions are included, limited to a small
  inspectable portable subset.
- O4 (AMENDED): the effect boundary is in v0.1; full simulation and replay
  implementation are v0.2+.
- O5 (AMENDED): unless() is omitted from v0.1. when_not(predicate) is the
  equivalent.
- O6 (APPROVED WITH AMENDMENTS): Flow* naming retained; FlowContract
  introduced; ExecutionStatus and DecisionStatus separated; interruption
  added to the outcome model.
- O7 (APPROVED): Python is the first implementation. The language-neutral
  specification remains authoritative. Python must not become the
  specification simply because it is implemented first.

## Consequences

- SPEC.md must record every decision above in its normative text.
- Any change to a decision requires a new ADR that supersedes this one.
- Tests must reference the decision each one protects (e.g., "protects D1").
- Documentation must not contradict any decision without an ADR.

## Confidence

High. Each decision was reviewed and amended across multiple review rounds.
The three flagship decisions (D1, D2, D3) are non-negotiable without
re-issuing the product identity.

