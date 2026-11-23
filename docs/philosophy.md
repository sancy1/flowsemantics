# Philosophy

FlowSemantics does not replace `if`, `else`, `try`, `with`, or any language
control flow. Those constructs are fundamental. It is an optional,
higher-level execution model for the cases where a decision becomes an
object of concern.

## What "object of concern" means

A decision is an object of concern when it must be:

- Traced
- Tested
- Simulated
- Versioned
- Audited
- Ported across languages
- Externalized into data
- Validated for structural soundness

When none of these apply, native code is simpler, faster, and correct.
Use it.

## The three pillars

FlowSemantics is built on three interconnected architectural decisions.
Each one only works if the others are present.

### Pillar 1: Decision / Effect Separation

A flow evaluates and explains a decision without performing its side
effects. Effects are proposed data, applied only by an application-owned
executor.

### Pillar 2: Formal Execution Semantics

A language-neutral specification defines, before any code exists, how
conditions, transformations, exceptions, recovery, cancellation, timeout,
and finalization interact. Implementations are conforming implementations
of the spec, not the definition.

### Pillar 3: Safe Simulation and Replay

Simulation has no route to effect execution. Replay distinguishes historical
replay, decision replay, and effect re-execution. None of these ever
accidentally repeats a real operation.

## The honesty principle

Where native code wins, say so.
Where we cannot analyze, say so.
Where we have not measured, do not claim.

This principle is not a marketing concession. It is a design constraint.

