# FlowSemantics — Planning

Living phase tracker. Updated at every phase exit. The authoritative plan is the approved implementation plan derived from the v5 feature baseline.

## Current state

- Phase: **7 — Cross-Language, ~97% (2026-11-22)**
- Phase 6: ~75% (phase-exit docs done; IR rejection vectors deferred)
- Phase 4: ~95% (phase-exit docs pending)
- Phase 5: ~60% (allocation pass optional)
- Phase 3: ~95% (async parity deferred to Phase 4)
- Phase 2: ~90% (async parity + error vectors deferred)
- Phase 1: COMPLETE except git tag (no git repo exists)
- VERSION: `0.0.0`
- SPEC.md: **frozen** at v0.1
- Conformance: **39/39 vectors PASS** (core 13, error 9, trace/effects 3,
  finalizer 3, IR 4, async 2, IR rejection 5)
- Tests: **312 passing**, mypy --strict clean (28 files), ruff clean,
  audit.py 5/5 PASS

## Phase 2 checklist

- [x] 2.0 Catch rules — `Flow.catch/catch_when/catch_any/rethrow`,
      CatchRule, ordered first-match routing, handler-failure propagation,
      catch_any ordering validation (SPEC 11.1-11.4)
- [x] 2.1-2.2 on_match hooks + secondary_exceptions (SPEC 11.5)
- [x] 2.3 Cancellation — asyncio.CancelledError → CANCELLED +
      InterruptionInfo, bypasses catches (SPEC 11.6.1)
- [x] 2.4 Timeout recognition — TimeoutError → TIMED_OUT +
      InterruptionInfo, bypasses catches; library does NOT enforce
      timeouts (SPEC 11.6.2)
- [x] 2.5 Finalization — `Flow.finally_`, FinallyContext,
      FinallyFailurePolicy (3 policies), WithFinallyTimeout budget,
      is_clean, LIFO merge ordering, B3-a interruption preservation
      (SPEC 11.8, 16.4, 16.7)
- [x] 2.x Async parity — shipped in Phase 4 (execute_async,
      AsyncOnlyContractError, async finalizers)
- [x] 2.x Conformance vectors — error family landed as vectors
      014-022 in Phase 4 (runner now supports catches/finally)

## Phase 3 checklist

- [x] 3.0 ExecutionTrace + 22-event vocabulary + TraceRecorder +
      with_trace()/trace= override; events emitted across rules, guards,
      actions, catches, hooks, finalizers, interruptions (SPEC 3.8, 12.1-12.3)
- [x] 3.1 explain() — trace → human-readable lines, no invented reasons
      (SPEC 12.4)
- [x] 3.2 simulate() — decision semantics without hooks/finalizers
      (SPEC 12.5)
- [x] 3.5 validate() — static analysis returning ValidationIssue
      error/warning (SPEC 12.8)
- [x] 12.9 contract_version — structural SHA-256 hash (algorithm v1
      documented in code)
- [x] 3.3-3.4 replay() — all 4 operations (simulation/historical/
      decision/effects), fail-closed spec+contract version checks,
      HMAC-SHA256 integrity (sign/verify), semantic equivalence (A5),
      effects require explicit authorization (SPEC 12.6, 9.5)
- [x] 3.x shadow() — candidate-vs-current ShadowReport, deterministic,
      simulate-based (no effects) (SPEC 12.7)
- [x] 12.9 effective dates — effective_from/until on when/when_not,
      inclusive-from/exclusive-until, not_effective skip reason,
      compile-time ordering validation, in contract version hash
- [x] 12.2 trace privacy — diagnostic_hook opt-in on with_trace() and
      try_execute(); library defers redaction to application

## Phase 4 checklist

- [x] 4.0 Portable expression subset — PExpr + 15 ops (field, const,
      6 comparisons, and/or/not, null checks, in/not-in), eval_expr,
      expr_to_dict/from_dict (SPEC 14.2, 5.1)
- [x] 4.1 Portable IR — PortableFlow/PortableRule, Flow.when_expr/
      when_not_expr/with_flow_id/from_ir, contract.to_ir/to_ir_json,
      PORTABLE classification, mixed native+portable rejected,
      spec/ir.schema.json published (SPEC 14.2)
- [x] 4.x Async parity — execute_async/try_execute_async, async
      conditions/actions/guards/catch handlers+predicates/hooks/
      finalizers awaited via _resolve; async-only classification
      (any async callable → async_only); execute()/try_execute() raise
      AsyncOnlyContractError; mixed sync+async finalizers rejected
      (FR8); sync path rejects awaitable results (SPEC 11.7)
- [x] 4.x Proposed effects — Effect on when/when_not/then/when_expr/
      when_not_expr, deterministic evaluation-order proposal,
      effect_proposed trace event, outcome.effects, async parity,
      IR serialization + JSON-safety validation (SPEC 5, 6.4, 14.2)
- [x] 4.x Portability honesty — portable rules + catches/finalizers/
      hooks classify NATIVE (IR cannot represent them; SPEC 4.4, D3)
- [x] 4.x Conformance vectors — runner extended (catches, on_match,
      finally+policy+timeout, rule effects, trace full/subset compare,
      portable_ir pipelines); 17 new vectors 014-030; schema extended;
      coverage.md updated (SPEC 14.3, 14.4)
- [x] 4.x Async conformance vectors — pipeline.execution="async" in
      schema + runner (try_execute_async via asyncio.run); vectors
      031-032 prove sync/async parity incl. catch+finalizer
- [x] 4.x Portable then-stages — spec gap resolved via ADR-0003:
      deferred to spec v0.2 subset extension (prev pseudo-field);
      from_ir rejects kind="then" honestly
- [ ] Phase 3/4 exit: docs update, CHANGELOG, git tag when repo exists

## Phase 5 checklist (Performance, SPEC 13)

- [x] 5.0 Benchmark harness — benchmarks/bench_common_path.py,
      stdlib-only, p50/p95/p99 + throughput + allocations, committed
      results JSON (SPEC 13.3)
- [x] 5.1 docs/performance.md — 13.1 no compiled path (vacuous),
      13.2 allocation documentation, 13.3 methodology + recorded
      result (~50k ops/sec, p50 16.3µs); 13.4 hypothesis NOT claimed
- [x] 5.x Benchmark smoke tests — test_benchmark.py (2 tests)
- [ ] 5.x Allocation reduction pass (optional; 13.2 is SHOULD-level)

## Phase 6 checklist (Enterprise, SPEC 9, 15)

- [x] 6.1 IR hardening (SPEC 9.2) — MAX_EXPR_DEPTH=100,
      MAX_RULES=10_000, MAX_IR_BYTES=1 MiB, duplicate RuleId rejection
      at deserialization; 4 new tests
- [x] 6.2 Threat model — docs/threat-model.md covering all five
      required areas + boundaries + residual risks (SPEC 15.4)
- [x] 6.3 SBOM — scripts/sbom.py CycloneDX generator + committed
      sbom.cdx.json (runtime: none; build: hatchling; dev: 5 tools)
      (SPEC 15.3)
- [x] 6.4 SECURITY.md — disclosure process: report, ack 7d, fix,
      coordinated disclosure (SPEC 15.4)
- [x] 6.x CHANGELOG — phases 2-6 recorded
- [x] 6.5 Fuzz/adversarial tests (SPEC 9.4) — test_adversarial.py:
      malformed/deep/oversized/dup-key JSON, 500 seeded IR mutations,
      300 expr mutations, depth/rule-count boundaries, transition-table
      property test; differential N/A (no compiled path)
- [x] 6.x IR boundary vectors — 033 (nested expr), 034 (in/not_in)
- [x] 6.x Migration guide template — docs/migration-guide.md (SPEC 15.6)
- [x] 6.x IR rejection vectors — expected_error mechanism added to
      vector schema + all 5 runners; vectors 035-039 (duplicate id,
      then-stage, unknown op, depth, missing id); **39/39 PASS**
- [ ] 6.x Phase exit: docs sweep, CHANGELOG final, git tag

## Phase 7 checklist (Cross-Language, SPEC 14)

- [x] 7.0 TypeScript implementation — typescript/ package: types,
      clock, errors, portable IR (with 9.2 limits), flow engine
      (all modes, catches, hooks, finalizers, effects, trace,
      async parity), fixtures, conformance runner
- [x] 7.x TS conformance — **34/34 vectors PASS**, tsc --strict clean
      (Node 24 native type-stripping, zero runtime deps)
- [x] 7.x TS unit tests — tests/engine.test.ts, 29 tests via
      node:test (all modes, catches, interruptions, finalizers,
      effects, trace, async parity, IR limits); fixed real bug:
      FirstMatch/Priority now skip matching but still run then-stages
- [x] 7.x TS trust layer — trust.ts: record/replay (4 modes, HMAC
      integrity, fail-closed versions), shadow, contractVersionOf;
      8 new tests (37 total)
- [x] 7.x Go implementation — go/ module: full engine + portable IR +
      fixtures + runner; **34/34 vectors PASS**, 20 unit tests,
      go vet clean, zero deps
- [x] 7.x Java implementation — java/ (javac 21, zero deps incl.
      hand-written JSON parser): full engine + portable IR + fixtures
      + runner; **34/34 vectors PASS**, 24 unit tests
- [x] 7.x C#/.NET implementation — csharp/ (net10.0, zero third-party;
      System.Text.Json in-box): full engine + portable IR + fixtures +
      runner + selftest; **34/34 vectors PASS**, 23 unit tests,
      0 warnings
- [x] 7.x Full feature parity — trust layer (record/replay 4 modes,
      HMAC-SHA256 integrity, fail-closed versions), shadow, contract
      versioning (SHA-256 v1), validate, explain, toIR/toIRJSON now in
      ALL FIVE languages; TS gained toIR export
- [ ] 7.x Rust implementation (no toolchain on this machine —
      deferred, needs rustc)

## Phase 0.6 deliverable (deferred from 0.0)

Verify distribution-name and import-name availability against PyPI and the Python import namespace. Record the verification method and result here. Do not assert availability before this check.

**Result (2026-11-22):** PyPI search for `flowsemantics` returns no
package by that name (nearest matches: `semantics.py3`, `tool-semantics`,
`abstractsemantics` — all unrelated). Distribution name `flowsemantics`
and import name `flowsemantics` appear available. Method: PyPI web
search + project page inspection. Re-verify at publish time (Phase 8).
