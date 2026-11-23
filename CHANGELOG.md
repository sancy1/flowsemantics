# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Phase 8 (advanced parity completion) — remaining advanced surface
  closed in Go, Java, and C#: withFlowId/withClock, diagnostic hook on
  trace events (contract_version + diagnostics, SPEC 12.2), execute
  (propagating, SPEC 11.4), simulateWithClock (SPEC 12.5), mergeContract
  (SPEC 10.7), FlowContext (SPEC 4.1.3/6.2), PExpr builders + portable
  IR serialization round-trip with contract_version (SPEC 14.2/9.2),
  replay reconstructs recorded clock, shadow clock overload, toIR
  carries flow_id + contract_version. Test counts: Python 323,
  TypeScript 48, Go 46, Java 62, C# 63.
- Phase 7 (advanced parity) — full advanced-feature surface in all five
  languages: flow merge (SPEC 10.7), DecisionTable + hit policies
  (SPEC 10.8, incl. new typescript/src/table.ts), effective dates
  (SPEC 12.9), cooperative cancel check (SPEC 11.6), finally timeout
  budget reporting (SPEC 11.8/16.4), simulate_batch firing distribution
  (SPEC 12.5), portability report (SPEC 4.4), deep validate
  (unreachable/overlap/gap, SPEC 12.8), default alias (SPEC 10.4).
  docs/advanced-features.md documents every feature per language.
  Test counts: Python 323, TypeScript 48, Go 46, Java 62, C# 63.
  Per-language CycloneDX SBOMs added (sbom.{typescript,go,java,
  csharp}.cdx.json via scripts/sbom_languages.py; SPEC 15.3).
- Phase 7 (in progress) — Cross-language (SPEC 14): TypeScript
  implementation (34/34 vectors, 37 unit tests, trust layer with
  replay/shadow/HMAC), Go implementation (34/34 vectors, 20 unit
  tests), Java implementation (34/34 vectors, 24 unit tests,
  zero-dep JSON parser), C#/.NET implementation (34/34 vectors,
  23 unit tests, net10.0 zero third-party). All five
  implementations pass 100% of conformance vectors.
- Phase 7 (parity) — trust layer, contract versioning, validate,
  explain, and portable-IR export ported to Go, Java, and C#;
  toIR export added to TypeScript. All five implementations now
  ship the full SPEC feature surface.
- Phase 6/7 (conformance) — expected_error rejection mechanism in
  vector schema + all 5 runners; vectors 035-039 cover IR rejection
  (duplicate RuleId, then-stage, unknown op, depth, empty rule_id).
  Conformance suite now 39 vectors, 39/39 PASS in all five languages.
- Phase 6 (in progress) — Enterprise hardening: SPEC 9.2 IR limits
  (MAX_EXPR_DEPTH=100, MAX_RULES=10_000, MAX_IR_BYTES=1 MiB, duplicate
  RuleId rejection), docs/threat-model.md (SPEC 15.4), CycloneDX SBOM
  generator + committed sbom.cdx.json (SPEC 15.3), SECURITY.md
  disclosure process.
- Phase 5 — Performance (SPEC 13): reproducible benchmark harness
  (benchmarks/bench_common_path.py, p50/p95/p99 + throughput +
  allocations), committed results, docs/performance.md.
- Phase 4 — Portable IR & Async: portable expression subset (15 ops),
  PortableFlow/PortableRule IR + spec/ir.schema.json, when_expr/
  when_not_expr/from_ir/to_ir, PORTABLE classification with honesty
  rules, proposed effects (Effect on all rule kinds, IR-serialized,
  deterministic order), async parity (execute_async/try_execute_async,
  AsyncOnlyContractError, finally_async, awaitable rejection),
  conformance runner extended (catches, hooks, finalizers, effects,
  trace compare, portable_ir, async execution) with 19 new vectors
  (32/32 PASS total).
- Phase 3 — Trust Semantics: ExecutionTrace (22-event vocabulary),
  explain(), simulate(), replay() (4 modes, HMAC integrity, fail-closed
  versions), shadow(), validate(), contract_version hashing, effective
  dates, trace privacy hook.
- Phase 2 — Error and Execution Layer: catch/catch_when/catch_any/
  rethrow, on_match hooks + secondary_exceptions, cancellation and
  timeout recognition (interruption model), finalization with 3
  policies + timeout budget.
- Phase 1 — Core Decision Layer (~85%): complete decision engine
  (when, when_not, then, otherwise, default, all three EvaluationModes,
  merge, DecisionTable), canonical outcome model, clocks, error
  hierarchy, conformance runner with 13 passing vectors, 126 tests,
  getting-started/cookbook docs, docs-consumer CI workflow.
- Phase 0 — complete: repository bootstrap, Python build tooling, CI/CD
  foundation, docs/governance scaffold, SPEC.md v0.1 frozen, conformance
  infrastructure (schema, fixtures, runner protocol, Python runner, first
  vector, coverage map), versioning policy, audit gate.
- Canonical outcome model: ExecutionStatus, DecisionStatus,
  InterruptionInfo, RecoveryInfo, FinalizationInfo, Effect, FlowOutcome.
- Clocks: Clock protocol, SystemClock (documented default), FakeClock.
- Decision layer (Phase 1.0 subset, pulled forward for conformance):
  Flow builder (when, when_not, then, otherwise, default,
  default_if_no_match, with_mode, with_clock), compile() → FlowContract,
  execute()/try_execute(), EvaluationMode (FirstMatch/AllMatch/Priority),
  FlowPortability classification.
- Conformance runner: `python -m flowsemantics.testing.conformance.runner`
  with vector discovery, fixture resolution, outcome comparison, and
  PASS/FAIL reporting per runner-protocol.md.
- Fixture vocabulary: all 24 fixtures from spec/fixtures.md with
  abstract error-kind mapping.
- docs/versioning.md; ADR-0002 (Phase 0.7 deferral to Phase 1.8).

### Notes
- SPEC.md v0.1 is frozen (SHA256 089AD516…). Changes require an ADR and
  a specification version bump.
- Known spec gap: REJECTED decision polarity is undefined in v0.1;
  matched rules yield APPROVED.
