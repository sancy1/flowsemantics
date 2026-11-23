# Architecture Decision Records

Every decision that is expensive to reverse is recorded here before the
code that depends on it is written.

## When an ADR is required

- Any change to SPEC.md after v1.0 is frozen.
- Any new dependency (runtime, build, or dev).
- Any change to the public API that affects compatibility.
- Any change to the persistence layer, message format, or wire protocol.
- Any change to security or observability posture.

## File naming

`ADR-NNNN-kebab-case-title.md`, where NNNN is a zero-padded sequential
number. Numbers are permanent and never reused.

## Template

Every ADR contains:

- **Status** - proposed | accepted | superseded by ADR-NNNN
- **Context** - requirements, constraints, forces at play
- **Options** - at least two, with cost, risk, and fit
- **Decision** - the chosen option and why
- **Rejected** - for each rejected option: "Not X, because Y."
- **Consequences** - benefits, costs, follow-up work, what would make us revisit
- **Confidence** - percent or low/medium/high, with the reason

## Superseding

An accepted ADR is never deleted. If a decision changes, a new ADR is
written and the old one is updated with **Status: superseded by ADR-NNNN**.

## Index

- [ADR-0001: Governing decisions](ADR-0001-governing-decisions.md) - D1-D3, B1-B8, O1-O7
- [ADR-0002: Phase 0.7 consumer-harness CI deferral](ADR-0002-phase-0.7-deferral.md) - docs-consumer.yml activates at Phase 1.8

