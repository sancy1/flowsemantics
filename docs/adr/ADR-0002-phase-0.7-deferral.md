# ADR-0002: Defer Phase 0.7 consumer-harness CI activation to Phase 1.8

- **Status**: accepted
- **Date**: 2026-11-22
- **Deciders**: Alexander (Cyril) Sanchez

## Context

Phase 0.7 calls for a consumer sample harness: `scripts/local-wheel.py`
builds the wheel to a local feed, `python/samples/scratch_consumer/`
restores from that feed only, `scripts/docs-snippets.py` verifies doc
snippets against compiled sample source, and `docs-consumer.yml` runs both
in CI.

The scripts and the sample exist and are verified (Phase 0.0 pip-wheel
exit gate). What remains is CI activation: a workflow that packs the wheel
and builds the sample against it on every relevant PR.

The package currently contains only the Phase 1.0 decision-layer subset
(pulled forward to make the first conformance vector executable). The
scratch_consumer sample exercises F1-F10, F41, F42 exactly as documented —
features that are not all implemented yet (Merge, DecisionTable, modes
beyond the basics, compile() edge cases). Activating the workflow now
would produce a permanently red CI until Phase 1.8, which trains everyone
to ignore CI failures — the opposite of what the gate is for.

## Options

1. **Activate docs-consumer.yml now, accept red CI until Phase 1.8.**
   Cost: a red workflow on every PR for ~2 phases; risk of alert fatigue.
2. **Complete the workflow and sample now, mark it `workflow_dispatch`
   only (manual trigger).** Cost: small; risk: manual gates get skipped.
3. **Formally defer CI activation to Phase 1.8**, when the sample's
   documented features exist. The scripts remain in the repo and are
   runnable locally today.

## Decision

Option 3. CI activation is deferred to Phase 1.8 (the Phase 1 exit gate),
which is exactly when the plan schedules the docs-consumer loop anyway.
The deferral is recorded here and in PLANNING.md so it is an approved
decision, not an oversight.

## Rejected

- Not option 1, because a knowingly-red required check erodes the CI
  signal the project depends on.
- Not option 2, because a manual-only gate is a gate that does not gate.

## Consequences

- `docs-consumer.yml` does not exist yet; it is created in Phase 1.8.
- `scripts/local-wheel.py`, `scripts/docs-snippets.py`, and
  `python/samples/scratch_consumer/` remain usable locally at any time.
- Phase 0.9 exit gate treats 0.7 as "formally deferred per ADR-0002".
- Revisit if Phase 1 slips far enough that the sample harness rots;
  the scripts are small and stdlib-only, so rot risk is low.

## Confidence

High. The deferral matches the plan's own sequencing (docs-consumer loop
is a per-phase exit criterion starting at 1.8) and the handover's
recommendation.
