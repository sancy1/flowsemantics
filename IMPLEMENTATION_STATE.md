# Implementation State

What has actually shipped, verified. Not what is planned. Planned work belongs in PLANNING.md.

## Phase 8 — Advanced Parity Completion, complete (2026-11-23)

### Remaining advanced surface closed in Go, Java, C#

TypeScript and Python already carried the full advanced surface; this
pass brought Go, Java, and C# to the same level:

- **withFlowId / withClock**: `Flow.withFlowId`/`WithFlowId`/`WithFlowId`,
  `Flow.withClock`/`WithClock`/`WithClock` — flow_id + contract_version
  flow into Portable IR export; injected clock used by compile.
- **Diagnostic hook**: `withTrace(hook)` / `WithTrace(DiagnosticHook)` /
  `WithTrace(DiagnosticHook)` — TraceEvent gains contract_version +
  diagnostics map (SPEC 12.2).
- **execute** (propagating): `FlowContract.Execute`/`execute`/`Execute`
  — rethrows unrecovered primary exception (SPEC 11.4, D13).
- **simulateWithClock**: `SimulateWithClock`/`simulateWithClock`/
  `SimulateWithClock` (SPEC 12.5).
- **mergeContract**: `Advanced.mergeContract`/`mergeContract`/
  `Advanced.MergeContract` — merge a compiled FlowContract (SPEC 10.7).
- **FlowContext**: new type in all three (SPEC 4.1.3, 6.2).
- **PExpr builders + serialization**: `pField`/`PField`/`PField` etc.,
  `OPS`/`Ops` exported, `exprToDict`/`ExprToNode`/`ExprToNode`,
  `portableFlowToDict`/`PortableFlowToNode`/`PortableFlowToNode`,
  `portableFlowToJSON`/`PortableFlowToJSON`/`PortableFlowToJSON`,
  `portableFlowFromJSON`/`PortableFlowFromJSON`/`PortableFlowFromJSON`
  with SPEC 9.2 size limit; `contract_version` parsed/emitted.
- **Trust fixes**: replay reconstructs FakeClock from recorded
  wall/monotonic and uses simulateWithClock; shadow gains clock
  overload; toIR carries flow_id + contract_version; toIRJSON uses the
  canonical serializer.

### Verified test counts (2026-11-23)

- Python: **323 tests** (incl. 11 new test_advanced.py), 39/39 vectors
- TypeScript: **48 tests** (node:test, incl. 3 decision-table tests),
  tsc --strict clean, 39/39 vectors
- Go: **46 tests** (go test), 39/39 vectors
- Java: **62 tests** (FlowTest), 39/39 vectors
- C#: **63 tests** (SelfTest), 39/39 vectors

### Feature audit (2026-11-23)

Systematic 62-feature audit across all five languages:
`docs/feature-audit.md`. **62/62 features present in every language** —
no gaps. API-shape differences documented (static Trust.*/Advanced.*
helpers in Java/C#, structural async parity in sync languages, Go error
tuples).

## Phase 7 — Advanced Feature Parity, complete (2026-11-23)

### Advanced surface in all five languages

Every implementation now ships the advanced SPEC surface with unit
tests and docs (`docs/advanced-features.md`):

- **Merge** (SPEC 10.7): `Flow.merge` / `flow.merge` / `Flow.Merge` /
  `Advanced.merge` / `Advanced.Merge` — mode + RuleId uniqueness
  checks, outer fallback wins.
- **DecisionTable** (SPEC 10.8): `table_to_flow` / `tableToFlow` /
  `TableToFlow` / `Advanced.tableToFlow` / `Advanced.TableToFlow`;
  hit policies FIRST/COLLECT/PRIORITY/UNIQUE map to EvaluationMode.
  TypeScript gained `src/table.ts` in this pass.
- **Effective dates** (SPEC 12.9): `effective_from`/`effective_until`
  (Python datetimes), `effectiveFrom`/`effectiveUntil` (TS epoch-ms),
  `WithEffectiveFrom`/`WithEffectiveUntil` (Go), `when(..., effFrom,
  effUntil)` (Java), `When(..., effectiveFrom, effectiveUntil)` (C#).
  Inverted windows fail compile; portable IR carries ISO-8601.
- **Cancel check** (SPEC 11.6): `with_cancel_check` /
  `withCancelCheck` / `WithCancelCheck` / `withCancelCheck` /
  `WithCancelCheck` — produces CANCELLED interruption, bypasses catches.
- **Finally timeout** (SPEC 11.8/16.4): `with_finally_timeout` /
  `withFinallyTimeout` / `WithFinallyTimeout` /
  `withFinallyTimeout` / `WithFinallyTimeout`; outcome reports
  `cleanup_budget_exceeded` + `cleanup_budget_used_ms`.
- **Simulate batch** (SPEC 12.5): `simulate_batch` / `simulateBatch` /
  `SimulateBatch` / `Advanced.simulateBatch` / `Advanced.SimulateBatch`
  — firing distribution by status/decision/value.
- **Portability report** (SPEC 4.4): `portability_report` /
  `portability` / `Portability` / `Advanced.portability` /
  `Advanced.Portability` — PORTABLE/NATIVE + offenders.
- **Validate depth** (SPEC 12.8): unreachable_rule,
  overlapping_rules, possible_gap warnings on portable contracts;
  invalid_effective_window error.
- **Default alias** (SPEC 10.4): `default` / `default` / `Default` /
  `defaultValue` / `DefaultValue`.

### Verified test counts (2026-11-23)

- Python: **323 tests** (incl. 11 new test_advanced.py), 39/39 vectors
- TypeScript: **48 tests** (node:test, incl. 3 decision-table tests),
  tsc --strict clean, 39/39 vectors
- Go: **46 tests** (go test), 39/39 vectors
- Java: **62 tests** (FlowTest), 39/39 vectors
- C#: **63 tests** (SelfTest), 39/39 vectors

## Phase 7 — Cross-Language, ~97% (2026-11-22)

### Conformance: 39/39 vectors in all five languages

- `expected_error` rejection mechanism added to vector schema +
  all 5 runners (Python, TS, Go, Java, C#)
- Vectors 035-039: IR rejection cases (duplicate RuleId, then-stage,
  unknown op, depth>100, empty rule_id) — SPEC 9.2/9.4
- Phase 6 IR-rejection gap closed

### Full feature parity across all five languages

Every implementation now ships the complete SPEC surface:
engine (3 modes, guards, then, catches, hooks, finalizers+policies,
effects, trace, async parity), portable IR (import + export),
simulate, contract versioning (SHA-256 v1), validate, explain,
trust layer (record/replay 4 modes, HMAC-SHA256 integrity,
fail-closed versions, shadow).

- Go: trust.go added; 30 unit tests
- Java: Trust.java added; 34 unit tests
- C#: Trust.cs added; 33 self-tests
- TS: toIR/toIRJSON added to FlowContract; 37 tests

### C#/.NET implementation (SPEC 14.5, fifth)

- `csharp/` (net10.0, zero third-party — System.Text.Json in-box):
  Outcome, Clock/FakeClock, Errors (Kind.*), Portable (IR + 9.2
  limits), Flow (full engine), Fixtures, Runner (conformance +
  --selftest)
- **34/34 conformance vectors PASS**
- **23 unit tests PASS** (--selftest), 0 build warnings
- Enum→spec-string mapping in runner (COMPLETED/FAILED/...)

### Java implementation (SPEC 14.5, fourth)

- `java/` (javac 21, zero deps — hand-written JSON parser in Json.java):
  Outcome, Clock/FakeClock, FlowErrors (Kind.*), Portable (IR + 9.2
  limits), Flow (full engine), Fixtures, runner/Runner, FlowTest
- **34/34 conformance vectors PASS**
- **24 unit tests PASS** (plain assertions)
- Fixed: recovered outcomes carry decision_status=null (SPEC 7)

### Go implementation (SPEC 14.5, third after Python/TS)

- `go/` module (zero deps): outcome.go, clock.go, errors.go,
  portable.go (IR + 9.2 limits), flow.go (full engine), fixtures.go,
  cmd/runner
- **34/34 conformance vectors PASS**
- **20 unit tests PASS** (go test), go vet clean
- Simulate() implemented (SPEC 12.5)

### TypeScript trust layer

- `typescript/src/trust.ts`: record/replay (4 modes, HMAC-SHA256
  integrity, fail-closed spec/contract versions), shadow(),
  contractVersionOf (v1 hash); 8 new tests (37 total, tsc clean)

### TypeScript implementation (SPEC 14.5, first after Python)

- `typescript/` package: types.ts (outcome model + 22-event trace
  vocabulary), clock.ts, errors.ts (abstract Kind.* mapping),
  portable.ts (PExpr 15 ops + IR with 9.2 limits), flow.ts (builder +
  contract: all 3 modes, catches, hooks, finalizers+policies, effects,
  trace, async parity, portable IR), trace.ts, fixtures.ts, runner.ts
- **34/34 conformance vectors PASS** — full parity with Python runner
- `tsc --strict` clean (strict + exactOptionalPropertyTypes +
  erasableSyntaxOnly); Node 24 native type-stripping, zero runtime deps
- **29 unit tests PASS** (node:test) — mandate satisfied
- Bug found by tests: FirstMatch/Priority broke out of the rule loop,
  skipping then-stages; fixed to skip matching but run then-stages
  (sync + async paths)

### Deferred

- TS trust layer (replay/shadow/validate/simulate parity)
- Go/Java/Rust implementations

## Phase 6 — Enterprise Hardening, ~75% (2026-11-22)

### Shipped and verified

**IR hardening (SPEC 9.2):**
- `MAX_EXPR_DEPTH=100`, `MAX_RULES=10_000`, `MAX_IR_BYTES=1 MiB`
  enforced in portable.py; duplicate RuleId rejected at
  deserialization; unknown ops already rejected
- 4 new tests: depth, oversize, rule-count, duplicate-id

**Threat model + SBOM + disclosure (SPEC 15.3, 15.4):**
- `docs/threat-model.md` — all five required areas, trust boundaries,
  mitigations, residual risks, versioning note
- `scripts/sbom.py` — CycloneDX 1.5 generator from pyproject;
  `sbom.cdx.json` committed (runtime: zero deps; build: hatchling;
  dev: ruff/mypy/pytest/pytest-asyncio/uv)
- `SECURITY.md` — report privately, ack within 7 days, coordinated
  disclosure
- CHANGELOG updated for phases 2-6

**Fuzz/adversarial (SPEC 9.4):**
- test_adversarial.py: malformed/deep/oversized/dup-key JSON,
  500 seeded IR mutations + 300 expr mutations (never crash/hang),
  depth/rule-count boundaries, transition-table property test
- from_dict hardened: non-dict IR, non-list rules, non-dict rules,
  non-string rule_id all rejected with StructureError
- Vectors 033-034: IR nested expr + in/not_in (34/34 PASS)

**Tests: 312 passing** (+17 adversarial)

### Deferred

- IR rejection vectors (need expected-rejection mechanism in schema)
- Phase exit docs sweep

## Phase 4 — Portable IR & Async, ~95% (2026-11-22)

### Shipped and verified

**Portable expression subset (SPEC 14.2, 5.1):**
- `PExpr` frozen AST + 15 ops: field, const, eq/ne/lt/le/gt/ge,
  and/or/not, is_null/is_not_null, in/not_in
- `eval_expr` — field access requires mapping input; StructureError
  otherwise; boolean ops short-circuit via all/any
- `expr_to_dict`/`expr_from_dict` — JSON-safe serialization

**Portable IR (SPEC 14.2):**
- `PortableFlow`/`PortableRule` IR documents; to_dict/to_json/
  from_dict/from_json round-trip
- `Flow.when_expr`/`when_not_expr` — declarative rules, no lambdas
- `Flow.with_flow_id`, `Flow.from_ir` (dict or JSON)
- `FlowContract.to_ir()`/`to_ir_json()` — PORTABLE only; NATIVE raises
  PortabilityError
- Mixed portable+native rules rejected at compile (StructureError)
- `spec/ir.schema.json` published (Phase 0.5 deliverable)
- IR verified lambda-free: every node is {op, args, value} only

**Async parity (SPEC 11.7, FR8):**
- `FlowContract.execute_async()`/`try_execute_async()` — full async
  engine mirroring sync semantics (rules, guards, then-chains,
  fallbacks, catches, hooks, finalizers, trace, interruption)
- Every user callback awaited via `_resolve` when it returns an
  awaitable; sync/async paths produce identical outcomes
- `async_only` classification at compile: any async callable
  (condition/guard/action/catch handler+predicate/hook/finalizer,
  incl. partials and async __call__) → async_only=True
- `execute()`/`try_execute()` on async-only contract raise
  AsyncOnlyContractError; sync path rejects awaitable results at
  runtime (never silently skips awaiting)
- `Flow.finally_async()`; mixed sync+async finalizers rejected at
  compile (StructureError, FR8)
- Async finalizers support finally_timeout via asyncio.wait_for

**Proposed effects (SPEC 5, 6.4, 14.2):**
- `effects=` param on when/when_not/then/when_expr/when_not_expr —
  Effect data proposed (never applied) in deterministic evaluation
  order; outcome.effects; effect_proposed trace event; async parity
- Portable effects serialized in IR as {name, payload}; payload must
  be JSON-safe (StructureError otherwise); schema updated
- Portability honesty: portable rules + catches/finalizers/hooks →
  NATIVE classification (IR cannot represent them; SPEC 4.4, D3)

**Conformance runner + vectors (SPEC 14.3, 14.4):**
- Runner extended: pipeline catches (typed/when/any/rethrow via
  exc_kind→KIND_MAP), on_match hooks, finally (string or FixtureRef)
  + finally_policy + finally_timeout_ms, rule effects, trace
  full/subset comparison per runner-protocol.md, portable_ir pipelines
- 19 new vectors 014-032: error (9), trace/effects (3), finalizer (3),
  IR (2), async parity (2); vector.schema.json extended (catches,
  on_match, effects, portable_ir, finally FixtureRef, execution=async);
  runner trace full/subset compare; coverage.md updated
- 32/32 vectors PASS

**ADR-0003 + Performance (SPEC 13):**
- ADR-0003: portable then-stages deferred to spec v0.2 (subset
  extension needs ADR + version bump per SPEC 14.2); from_ir rejects
  kind="then" honestly
- benchmarks/bench_common_path.py — stdlib harness, p50/p95/p99,
  throughput, tracemalloc allocations; results committed
  (benchmarks/results/common-path-2026-11-22.json): ~50k ops/sec,
  p50 16.3µs on Python 3.11.9/Win32
- docs/performance.md — 13.1 vacuous (no compiled path), 13.2
  allocation doc, 13.3 methodology; 13.4 hypothesis not claimed

**Tests: 291 passing** (+16: test_effects.py 9, test_portable.py +4,
  test_runner.py +3 net, test_benchmark.py 2)

### Deferred

- Portable then-stages (ADR-0003: spec v0.2 subset extension)

## Phase 3 — Trust Semantics, ~95% (2026-11-22)

### Shipped and verified

**Trace (SPEC 3.8, 12.1-12.3):**
- `ExecutionTrace`/`TraceEvent` full implementation; closed 22-type
  vocabulary (EVENT_TYPES) + closed reason enum (REASONS), both
  validated at emit time
- `TraceRecorder` — zero-cost when disabled (no recorder created)
- `Flow.with_trace()` + per-call `trace=True` override on try_execute
- Events emitted: condition_evaluated/raised, guard_evaluated,
  action_executed/raised, rule_skipped (condition_false/guard_blocked),
  skipped_by_short_circuit (earlier_match), catch_matched,
  catch_predicate_evaluated/raised, catch_declined, catch_handled,
  rethrow_reached, hook_invoked/raised, finally_started/completed/raised,
  cancelled_observed, timed_out_observed
- Trace privacy: events carry only type/rule_id/timestamp/reason/
  contract_version — no input values (tested)

**Trust operations:**
- `FlowContract.explain(trace)` — human-readable rendering, no invented
  reasons (SPEC 12.4)
- `FlowContract.simulate(input)` — decision semantics without hooks or
  finalizers (SPEC 12.5)
- `FlowContract.validate()` — ValidationIssue error/warning static
  analysis (SPEC 12.8)
- `contract_version` — structural SHA-256 hash, algorithm v1 documented
  (SPEC 12.9); stable across rebuilds, changes with structure

**Replay (SPEC 12.6, 9.5):**
- `record()` captures spec_version, contract_version, input, clock
  wall+monotonic, outcome, trace, effects
- 4 operations: SIMULATION, HISTORICAL, DECISION, EFFECTS — never
  conflated; EFFECTS requires authorize_effects=True + executor
- Fail closed on spec_version/contract_version mismatch
- HMAC-SHA256 integrity: `sign()`/verify; tamper detection tested
- Semantic equivalence (A5): status/decision/value/recovery/
  interruption kind — not bit-for-bit
- Recorded clock reconstructed via FakeClock (12.10)

**Shadow (SPEC 12.7):**
- `shadow(current, candidate, inputs)` → ShadowReport; simulate-based
  (no effects/hooks/finalizers); deterministic; differing_fields per entry

**Effective dates (SPEC 12.9):**
- `effective_from`/`effective_until` on when/when_not; inclusive-from,
  exclusive-until; `not_effective` skip reason; compile-time ordering
  validation; included in contract version hash

**Trace privacy (SPEC 12.2):**
- `diagnostic_hook` opt-in on with_trace()/try_execute(); returns extra
  fields stored in TraceEvent.diagnostics; absent hook → no data

**Tests: 238 passing** (+25: test_replay_shadow.py 22, test_trace.py +3)

### Deferred

- async parity (execute_async etc.) — Phase 2.x/4.x
- conformance vectors for error/trace/IR families (schema extensions)

## Phase 2 — Error & Execution Layer, ~90% (2026-11-22)

### Shipped and verified

**Catch rules (SPEC 11.1-11.4):**
- `Flow.catch(exc_type, handler)`, `catch_when(exc_type, predicate, handler)`,
  `catch_any(handler)`, `rethrow()`; `CatchRule` frozen dataclass
- Ordered first-match routing; handler receives (input, exception)
- Handler failure propagates NEW exception through remaining catches
- catch_when predicate failure becomes new primary candidate
- catch_any MUST follow typed catches (compile-time StructureError)
- Recovery → COMPLETED + value + RecoveryInfo (decision_status absent;
  interpretation documented — spec gap candidate for ADR)
- Catch rules never catch BaseException (SystemExit, CancelledError)

**Hooks (SPEC 11.5):**
- `Flow.on_match(hook)`; hook(input, RuleId, value) after each
  when/when_not action; failures isolated to secondary_exceptions;
  never triggers catch rules

**Interruption (SPEC 11.6):**
- asyncio.CancelledError → CANCELLED + InterruptionInfo(kind=cancelled)
- TimeoutError → TIMED_OUT + InterruptionInfo(kind=timed_out)
- Both bypass catch rules; timestamps from injected clock
- Library does NOT enforce timeouts (spec-correct)

**Finalization (SPEC 11.8, 16.4, 16.7):**
- `Flow.finally_(cleanup)`; FinallyContext (result/status/value/
  exception/context/cancellation_token)
- FinallyFailurePolicy: PreservePrimary (default), Attach,
  ReplacePrimary — exact 16.4 matrix incl. B3-a (CANCELLED/TIMED_OUT
  never become FAILED)
- WithFinallyTimeout budget via monotonic clock → cleanup_budget_exceeded
- is_clean orthogonal to policy; LIFO order; merge = inner-first
- Finalizers run for ALL statuses; never trigger catch (FR3)

**Tests: 179 passing** (+53 since Phase 1: test_catch.py 22,
test_execution_semantics.py 26, integration +5)

### Known limitations / deferred

- execute_async / async conditions / finally_async / AsyncOnlyContractError
  enforcement — needs async engine (Phase 2.x or 3.x)
- ~45 error-semantics conformance vectors deferred: vector schema lacks
  pipeline.catches/finally representation (additive extension needed)
- Cooperative cancellation token not yet injectable (CancelledError
  recognition only)
- Recovery decision_status=None is an interpretation; SPEC v0.1 does not
  pin it — candidate for ADR if contested

## Phase 1 — Core Decision Layer, ~85% (2026-11-22)

### Shipped and verified

**Engine (configuration/):**
- `Flow` builder: when, when_not, then, otherwise, default,
  default_if_no_match, with_mode, with_clock, merge, from_table
- `FlowContract`: compile(), execute(), try_execute()
- `EvaluationMode`: FIRST_MATCH, ALL_MATCH, PRIORITY (all implemented)
- `FlowPortability`: PORTABLE/NATIVE classification (NATIVE for callables)
- `DecisionTable`/`DecisionTableRow`/`table_to_flow` (SPEC 10.8)
- `Rule`/`RuleId` (frozen, unique-id validation at compile)

**Domain (execution/):**
- Full outcome model: ExecutionStatus, DecisionStatus, InterruptionInfo,
  RecoveryInfo, FinalizationInfo, Effect, FlowOutcome (frozen)
- Clock protocol, SystemClock (documented default), FakeClock
- FlowContext (isolated per invocation)
- ExecutionTrace/TraceEvent placeholders (Phase 3.0 fills vocabulary)

**Errors:** FlowSemanticsError hierarchy (6 classes)

**Conformance:**
- 13 vectors (001-013) all PASS: when, when_not, then, otherwise,
  default, guard, FirstMatch short-circuit, AllMatch, Priority
- Schema extended additively: Rule.kind, pipeline.fallback
- Fixture action.prev added
- coverage.md records exceptions for merge/table vectors (schema cannot
  express them yet) and Phases 2-3 vector families

**Tests: 126 passing**
- unit/test_smoke.py (3), unit/test_decision_layer.py (16),
  unit/test_outcome.py (10), unit/test_clock.py (7), unit/test_rule.py (5),
  unit/test_flow_evaluation.py (33), unit/test_fixtures.py (20),
  unit/test_runner.py (15)
- integration/test_conformance.py (1), integration/test_scenarios.py (16)

**Docs/samples:**
- docs/getting-started.md, docs/cookbook.md (real, snippet-verified)
- docs/versioning.md, docs/when-not-to-use.md, ADR-0002
- scratch_consumer exercises real API (order approval flow)
- docs-consumer.yml workflow created (3 OS matrix)
- docs-snippets.py activated: verifies snippets parse + import only
  public names (4 snippets verified)
- Wheel consumer path verified end-to-end (build → install → import)

### Verified gates

| Gate | Evidence |
|---|---|
| Conformance | 13/13 PASS |
| pytest | 126/126 |
| mypy --strict | clean, 22 files |
| ruff | clean |
| audit.py | 5/5 PASS |
| Wheel install | flow_semantics-0.0.0 installs from local feed |

### Known limitations

- REJECTED polarity undefined in SPEC v0.1 (matched → APPROVED)
- Merge/DecisionTable have no conformance vectors (schema gap, deferred
  to portable-IR phase); covered by unit+integration tests
- Trace is placeholder; with_trace() is Phase 3.0
- Effects not yet proposed by actions
- No git repo yet — tag 0.1.0-alpha.1 pending `git init`

## Phase 0 — COMPLETE (exit gate green 2026-11-22)

### Shipped and verified

**Phase 0.0-0.4, 0.8** (from prior session, unchanged):

- Full monorepo tree, root docs, CI workflows (ci/audit/pack), audit.py
- python/ packaging: pyproject.toml (PEP 621, dynamic version), uv.lock,
  consolidated ruff/mypy/pytest/coverage/hatch config, py.typed
- SPEC.md v0.1 FROZEN (SHA256 089AD516…, 1731 lines, 16 sections + appendices)
- spec/vector.schema.json, spec/fixtures.md (24 fixtures, 8 categories)
- docs/ scaffold + ADR-0001 (D1-D3, B1-B8, O1-O7)

**Phase 0.5 — conformance infrastructure (this session):**

- `conformance/runner-protocol.md` — committed (95 lines; duplicate
  sections removed before commit; LF, pure ASCII)
- `python/src/flowsemantics/testing/conformance/fixtures.py` — all 24
  fixtures + abstract error-kind mapping (Kind.Timeout/Cancelled/
  ValueError/Any → TimeoutError/asyncio.CancelledError/ValueError/
  FixtureAnyError)
- `python/src/flowsemantics/testing/conformance/runner.py` — vector
  discovery, spec_version gate, structural validation, fixture
  resolution, Flow construction, outcome comparison per protocol,
  PASS/FAIL output, exit codes
- `conformance/vectors/001-core-when-true.json` — first vector
- `conformance/coverage.md` — coverage exceptions recorded with
  approver/date per runner-protocol.md

**Phase 0.6:** `docs/versioning.md` — SemVer policy, breaking-change
definition, deprecation, spec-vs-package versioning, release process.

**Phase 0.7:** formally deferred to Phase 1.8 per ADR-0002.

**Minimal Phase 1.0 subset (pulled forward per handover sanction):**

- `errors/` — FlowSemanticsError hierarchy (StructureError,
  PortabilityError, EvaluationError, FinalizationBudgetExceeded,
  AsyncOnlyContractError)
- `execution/` — ExecutionStatus, DecisionStatus, InterruptionInfo,
  RecoveryInfo, FinalizationInfo, Effect, FlowOutcome (all frozen
  dataclasses/enums per SPEC.md section 3); Clock protocol, SystemClock,
  FakeClock; FlowContext; ExecutionTrace/TraceEvent placeholders
- `configuration/` — RuleId, Rule, EvaluationMode (3 members),
  FlowPortability, Fallback, Flow builder (when, when_not, then,
  otherwise, default, default_if_no_match, with_mode, with_clock),
  FlowContract (compile, execute, try_execute)
- `_spec.py` — SPEC_VERSION = "0.1.0"

### Verified gates (this session)

| Gate | Evidence |
|---|---|
| Conformance runner | `PASS 001-core-when-true`, `RESULT: 1/1 passed`, exit 0 |
| pytest | 3/3 passed (test_smoke updated for new public surface) |
| mypy --strict | no issues in 21 source files |
| ruff check | clean after --fix (Notes capitalization, __all__ sort) |
| audit.py | 5/5 PASS on full source tree |

### Known limitations (honest)

- REJECTED polarity: SPEC.md v0.1 does not define how a rule declares a
  negative decision; matched rules yield APPROVED. Spec gap, not invented.
- Priority mode + then-chains: then inherits preceding rule priority at
  compile; interaction is an implementation interpretation pending vectors.
- Trace is a placeholder type; with_trace() lands in Phase 3.0.
- Effects are not yet proposed by actions (enrichment.delayed returns a
  dict, not an Effect); effect proposal mechanism lands with its vectors.
- execute_async, catch rules, finalizers, merge, decision tables: not yet
  implemented (Phases 1.6-2.5).

### Findings

- runner-protocol.md.new contained duplicated sections (Outcome
  comparison through "No implementation is conformant" appeared twice)
  and non-ASCII em-dashes; fixed before commit. Recorded as a process
  finding: verify temp files for duplication before atomic commit.
