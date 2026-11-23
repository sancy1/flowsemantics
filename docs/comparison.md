# Comparison

> **Status**: draft — final comparison lands in Phase 8.1 per the
> implementation plan. This page currently states only what is
> verifiable today.

## What FlowSemantics is not

Per SPEC.md Section 1.2 and 15.7, FlowSemantics does not replace native
control flow, does not provide a rules engine DSL, and makes no
performance claims beyond the committed benchmark
(`benchmarks/results/`).

## Honest positioning

- **vs. hand-written if/elif chains**: FlowSemantics adds a canonical
  outcome model, tracing, replay, and conformance-tested semantics at
  ~16µs p50 per execution on the common path. For trivial branching,
  native code is faster and simpler — see `when-not-to-use.md`.
- **vs. business-rules engines (Drools, etc.)**: FlowSemantics is a
  library, not a platform — no rete network, no persistence, no
  administration UI. It executes deterministic decision flows with
  auditable outcomes.
- **vs. workflow engines (Temporal, etc.)**: no durability, no
  scheduling, no retries — those are normative non-goals (SPEC 1.3).

A full feature-by-feature comparison is deferred to Phase 8.1 and will
be published only with reproducible evidence (SPEC 13.3, 15.7).
