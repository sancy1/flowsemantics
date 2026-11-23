# Conformance coverage map

Every MUST in SPEC.md v0.1 MUST be covered by at least one published vector,
or by an explicitly recorded coverage exception (runner-protocol.md,
"Coverage obligation"). This file is that record.

## Coverage exceptions

| SPEC reference | Statement (summary) | Reason deferred | Target phase | Approver | Date |
|---|---|---|---|---|---|
| Sections 10.1-10.9 (all decision semantics) | Full decision-layer vector coverage | Only vector 001 published in Phase 0.5; remaining ~30 core-decision vectors land with Phase 1 sub-phases | Phase 1 (1.1-1.8) | Alexander (Cyril) Sanchez | 2026-11-22 |
| Sections 11.1-11.8 (error, interruption, finalization) | ~45 error/finalization/interruption vectors | Engine support lands in Phase 2 | Phase 2 (2.0-2.5) | Alexander (Cyril) Sanchez | 2026-11-22 |
| Section 12 (trust semantics) | ~35 trace/explain/simulate/replay/validation vectors | Trace and trust layer land in Phase 3 | Phase 3 (3.0-3.5) | Alexander (Cyril) Sanchez | 2026-11-22 |
| Section 14.2 (portable IR) | IR round-trip and portability vectors | Portable IR freezes in Phase 7 | Phase 7.0 | Alexander (Cyril) Sanchez | 2026-11-22 |
| Section 9 (security hardening) | ~10 IR-limit and adversarial vectors | Fuzz targets land in Phase 6.5 | Phase 6.5 | Alexander (Cyril) Sanchez | 2026-11-22 |

## Published vectors

| Vector | SPEC section | Proves |
|---|---|---|
| 001-core-when-true | 10.2 | when() match path: COMPLETED + APPROVED + value |
| 002-core-when-false-no-match | 10.2 | false condition, no fallback: NO_MATCH |
| 003-core-when-not-false-matches | 10.2 | when_not matches on false |
| 004-core-when-not-true-no-match | 10.2 | when_not skips on true |
| 005-core-first-match-short-circuit | 10.6 | FirstMatch stops; later conditions unevaluated |
| 006-core-otherwise-fallback | 10.4 | otherwise produces value under NO_MATCH |
| 007-core-default-if-no-match | 10.4 | constant fallback under NO_MATCH |
| 008-core-fallback-not-used-on-match | 10.4 | fallback skipped on match |
| 009-core-then-after-match | 10.5 | then receives previous_output |
| 010-core-then-skipped-on-no-match | 10.5 | then skipped without match |
| 011-core-guard-blocks-match | 10.1 | false guard vetoes true condition |
| 012-mode-all-match-last-wins | 10.6 | AllMatch evaluates all; last wins |
| 013-mode-priority-highest-first | 10.6 | Priority orders by priority desc |
| 014-error-uncaught-valueerror | 11.4 | Uncaught exception: FAILED + abstract kind |
| 015-error-catch-typed-recovers | 11.1 | Typed catch recovers; RecoveryInfo populated |
| 016-error-catch-when-predicate-declines | 11.2 | Declined predicate does not handle |
| 017-error-catch-any-recovers | 11.3 | catch_any handles uncaught kinds |
| 018-error-rethrow-propagates | 11.4 | rethrow stops the catch chain |
| 019-error-catch-handler-throws | 11.1 | Failing handler propagates the NEW exception |
| 020-error-hook-throws-isolated | 11.5 | Hook failure isolated to secondary_exceptions |
| 021-error-cancelled-interruption | 11.6.1 | Cancellation bypasses catches; CANCELLED |
| 022-error-timeout-interruption | 11.6.2 | Timeout recognized as TIMED_OUT, not caught |
| 023-trace-condition-false-skip | 12.1 | rule_skipped reason=condition_false in trace |
| 024-trace-effect-proposed | 12.1 | effect_proposed trace event + outcome.effects |
| 025-effects-proposed-order | 6.4 | Deterministic effect order under AllMatch |
| 026-finally-clean | 11.8 | Successful finalizer: is_clean true |
| 027-finally-throws-preserve-primary | 11.8.3 | Cleanup exception to secondary; is_clean false |
| 028-finally-replace-primary | 11.8.3 | ReplacePrimary swaps primary/secondary |
| 029-ir-portable-basic | 14.2 | Portable IR executes; effects carried |
| 030-ir-portable-when-not-fallback | 14.2 | when_not + fallback via IR |
| 031-async-parity-basic | 11.7 | Async path: identical outcome + effects |
| 032-async-parity-catch-finally | 11.7 | Async path: catch + finalizer parity |
| 033-ir-nested-expression | 14.2 | Nested boolean ops via IR |
| 034-ir-in-not-in | 14.2 | in/not_in membership ops via IR |
| 035-ir-reject-duplicate-rule-id | 9.2 | Duplicate RuleId rejected |
| 036-ir-reject-then-stage | 14.2 | then stage rejected in IR (ADR-0003) |
| 037-ir-reject-unknown-op | 14.2 | Unknown op rejected |
| 038-ir-reject-depth-exceeded | 9.2 | MAX_EXPR_DEPTH=100 enforced |
| 039-ir-reject-missing-rule-id | 9.2 | Empty rule_id rejected |

## Schema extensions (2026-11-22, third batch, additive, pre-1.0)

- Top-level `expected_error`: optional rejection expectation (SPEC 9.2,
  9.4). Vector passes iff build/compile/execute raises an error whose
  message contains the substring; `expected` block ignored. Implemented
  in all five runners.

## Schema extensions (2026-11-22, additive, pre-1.0)

- `Rule.kind`: `when` | `when_not` | `then` (default `when`); `condition`
  optional only for `then`.
- `pipeline.fallback`: `{kind: otherwise|default_if_no_match, action|value}`.
- Fixture `action.prev` added (returns previous_output) for then vectors.
- Merge and DecisionTable have NO vector coverage yet: the schema cannot
  express composed pipelines or tables. Covered by unit + integration
  tests instead; vector representation deferred to the portable-IR phase.

## Schema extensions (2026-11-22, second batch, additive, pre-1.0)

- `pipeline.catches`: ordered `{kind: typed|when|any|rethrow, exc_kind,
  predicate?, handler?, id?}` per SPEC 11.1-11.4.
- `pipeline.on_match`: array of hook FixtureRefs (SPEC 11.5).
- `pipeline.finally`: string shorthand OR full FixtureRef (params needed
  for `cleanup.throws`).
- `Rule.effects`: ordered proposed effects `{name, payload}` (SPEC 3.7).
- `pipeline.portable_ir`: canonical IR document executed via
  `Flow.from_ir` (SPEC 14.2); `rules` not required when present.
- Top-level `trace` + `trace_subset` now compared by the runner per
  runner-protocol.md (full or ordered-subset; timestamps ignored).
- `pipeline.execution`: `sync` | `async` — async runs via
  `try_execute_async` (SPEC 11.7 parity vectors 031-032).

## Rules

- A coverage exception does NOT reduce the requirement that every applicable
  MUST be covered before any conformance claim or the 1.0 GA release.
- Each exception MUST name the approver and date. Approver is the project
  owner sign-off recorded in the v5 baseline.
