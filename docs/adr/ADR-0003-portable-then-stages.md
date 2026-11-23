# ADR-0003: Portable then-stages deferred pending expression-subset extension

- **Status**: accepted (deferred)
- **Date**: 2026-11-22
- **Deciders**: Alexander (Cyril) Sanchez

## Context

SPEC 14.2 defines the Portable IR as carrying an ordered rule list where
each rule has a declarative condition, a declarative transformation, and
optional proposed effects. The portable expression subset (SPEC 14.2,
5.1) supports named field access, comparisons, boolean composition, null
checks, and enum membership — deliberately small and inspectable.

Native `then` stages (SPEC 10.5) receive `(input, previous_output)` and
chain off the preceding rule's value. A portable then-stage would need
to reference the previous stage's value inside its transform expression.
The current subset has no way to express that: `field` reads from the
input mapping only, and there is no `prev` pseudo-field.

Extending the subset is explicitly governed: SPEC 14.2 states the
subset "MUST NOT be extended without an ADR and a version bump. Adding
operators is a minor version change; adding expression types that change
the shape of the IR is a major version change (Section 8.3)."

## Options

1. **Invent a `prev` pseudo-field now.** Rejected: it changes the shape
   of the IR and the subset without a spec version bump — exactly what
   SPEC 14.2 forbids. The specification is the authority; the
   implementation does not get to extend it unilaterally.
2. **Represent portable then-stages as ordinary portable rules whose
   transform ignores the previous value.** Rejected: it silently changes
   then-stage semantics (no chaining) and would produce IR that means
   something different from the native form — a portability lie.
3. **Defer portable then-stages until a spec revision (v0.2) extends the
   subset** with an explicit previous-value binding (e.g. a `prev`
   pseudo-field or a `let`-style binding), covered by an ADR, a schema
   update, and new conformance vectors.

## Decision

Option 3. `Flow.then()` remains native-only. `Flow.from_ir` rejects IR
documents containing `kind: "then"` rules (already implemented). The gap
is recorded in PLANNING.md and IMPLEMENTATION_STATE.md as deferred, not
silently absent.

## Consequences

- Portable contracts cannot express sequential stages until spec v0.2.
- Native then-stages are unaffected and fully tested.
- When v0.2 lands, the work is: subset extension + ADR + ir.schema.json
  update + `then_expr` builder + from_ir support + vectors.

## Confidence

High. The deferral follows the spec's own governance rule; inventing the
extension now would violate a frozen-spec MUST NOT.
