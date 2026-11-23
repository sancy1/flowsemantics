# Feature catalog — all 62 features

Plain-language description of every feature in FlowSemantics, grouped by
area. Each entry gives the SPEC reference and links to the detailed guide.
Implementation status across all five languages (Python, TypeScript, Go,
Java, C#) is tracked in [feature-audit.md](feature-audit.md) — **62/62
present everywhere**.

## Core decision (SPEC 10.x)

| # | Feature | What it does | Guide |
|---|---|---|---|
| 1 | `when` | Register a rule that fires when its condition is true. The basic building block of every flow. | [getting-started](getting-started.md) |
| 2 | `when_not` | Register a rule that fires when its condition is **false** — the negative branch without a separate `else`. | [getting-started](getting-started.md) |
| 3 | `then` | Sequential stage: runs after the decision, receiving `(input, previous_output)`. Chains flows into pipelines. | [getting-started](getting-started.md) |
| 4 | `otherwise` | Catch-all rule that fires when no `when`/`when_not` matched. | [getting-started](getting-started.md) |
| 5 | `default` | Fallback value/action when nothing matches — simpler than `otherwise` for constant results. | [getting-started](getting-started.md) |
| 6 | `default_if_no_match` | Explicit alias making the no-match fallback intent unmistakable in code review. | [getting-started](getting-started.md) |
| 7 | FirstMatch | Evaluation mode: stop at the first matching rule. The default; predictable and cheap. | [decision-tables](decision-tables.md) |
| 8 | AllMatch | Evaluation mode: collect **every** matching rule's effects — for audit/aggregation scenarios. | [decision-tables](decision-tables.md) |
| 9 | Priority | Rules can carry a priority so higher-priority matches win regardless of registration order. | [decision-tables](decision-tables.md) |
| 10 | guard | Optional second condition on a rule — fires only if both condition **and** guard pass. | [getting-started](getting-started.md) |
| 11 | rule priority | Per-rule ordering weight used by Priority mode and conflict resolution. | [decision-tables](decision-tables.md) |
| 12 | effects proposal | Rules can *propose* side effects (emails, writes) that are recorded in the outcome but never executed by the engine — the host applies them. Keeps flows pure and replayable. | [advanced-features](advanced-features.md) |
| 13 | merge (Flow) | Combine two flow builders into one — rules, catches, hooks, finalizers all carry over. | [advanced-features](advanced-features.md) |
| 14 | merge (FlowContract) | Merge two **compiled** contracts — validated at compile time, useful for composing libraries. | [advanced-features](advanced-features.md) |
| 15 | DecisionTable | Spreadsheet-style rules: rows of conditions → actions, with hit policies. For dense, auditable decision logic. | [decision-tables](decision-tables.md) |
| 16 | hit policies FIRST / COLLECT / PRIORITY / UNIQUE | How a table resolves multiple matching rows: first only, all matches, highest priority, or error on ambiguity. | [decision-tables](decision-tables.md) |
| 17 | compile validation | `compile()` rejects duplicate rule IDs, mis-ordered `catch_any`, invalid effective windows — fail fast, not at runtime. | [versioning](versioning.md) |
| 18 | effective_from / effective_until | Time-window gating: a rule only fires inside its validity window. For seasonal/pricing logic. | [advanced-features](advanced-features.md) |

## Error & execution (SPEC 11.x, 16.x)

| # | Feature | What it does | Guide |
|---|---|---|---|
| 19 | catch typed | Catch a specific exception type and recover with a handler — like try/catch but declarative. | [error-handling](error-handling.md) |
| 20 | catch_when | Catch with a predicate — recover only when the exception matches your condition. | [error-handling](error-handling.md) |
| 21 | catch_any | Catch-all recovery handler; must be registered last (enforced at compile). | [error-handling](error-handling.md) |
| 22 | rethrow | Explicitly propagate the current exception — opt out of recovery for this path. | [error-handling](error-handling.md) |
| 23 | on_match hook | Observable callback fired after a rule matches — for logging/metrics without touching rule logic. Hook failures are isolated, never trigger catches. | [tracing](tracing.md) |
| 24 | cancellation recognition | Detects platform cancellation (e.g. `asyncio.CancelledError`, `OperationCanceledException`) and reports it as CANCELLED, not FAILED. | [error-handling](error-handling.md) |
| 25 | timeout recognition | Same for timeout exceptions — reported as TIMED_OUT distinctly from generic failures. | [error-handling](error-handling.md) |
| 26 | cooperative cancel check | `with_cancel_check(fn)` polls a user predicate during execution — long flows can be cancelled cooperatively. | [error-handling](error-handling.md) |
| 27 | async parity | `execute_async`/`try_execute_async` await async conditions, actions, hooks and finalizers with identical semantics to the sync path. (Go/Java/C# are sync languages — parity is structural.) | [error-handling](error-handling.md) |
| 28 | finally | Guaranteed cleanup that runs after primary execution **whether it succeeded or failed** — like `finally` in code. | [finalization](finalization.md) |
| 29 | finally policies | What happens when a finalizer itself fails: `PreservePrimary` (default), `Attach` (record alongside), `ReplacePrimary`. | [finalization](finalization.md) |
| 30 | finally timeout budget | Optional time limit for finalizers — a hung cleanup can't hang the flow forever. | [finalization](finalization.md) |
| 31 | secondary_exceptions | Failures in hooks/finalizers are collected here — never silently swallowed, never mask the primary result. | [finalization](finalization.md) |
| 32 | interruption model | `InterruptionInfo` records *why* execution stopped (cancelled/timed out) as structured data, not just an exception. | [error-handling](error-handling.md) |
| 33 | FinallyContext + cancellation token | Finalizers receive a context object with elapsed time, outcome so far, and a cancellation token — enough to clean up intelligently. | [finalization](finalization.md) |

## Trust semantics (SPEC 12.x)

| # | Feature | What it does | Guide |
|---|---|---|---|
| 34 | trace vocabulary (22 events) | Opt-in structured event stream: rule evaluated, matched, action ran, catch fired, finalizer ran… every step is a typed event. | [tracing](tracing.md) |
| 35 | trace opt-in | Tracing is off by default — zero overhead unless `with_trace()` is set. | [tracing](tracing.md) |
| 36 | diagnostic hook | Custom hook receiving `(contract_version, diagnostics)` per execution — for APM integration. | [tracing](tracing.md) |
| 37 | explain | Human-readable "why did this rule fire / not fire" report for a given input — debugging without reading code. | [tracing](tracing.md) |
| 38 | simulate | Dry-run a flow against an input **without executing actions** — see what *would* happen. | [replay-simulation](replay-simulation.md) |
| 39 | simulate_batch | Run simulate over many inputs at once — coverage analysis, "which rules ever fire?" | [replay-simulation](replay-simulation.md) |
| 40 | replay record | Capture a full execution record (input, decisions, effects, trace) for later replay. | [replay-simulation](replay-simulation.md) |
| 41 | replay 4 modes | Replay a record in simulation / historical / decision / effects modes — verify behavior changed correctly after a flow edit. | [replay-simulation](replay-simulation.md) |
| 42 | HMAC-SHA256 integrity | Sign replay records and contracts with a shared key; verify detects tampering — fail-closed. | [replay-simulation](replay-simulation.md) |
| 43 | fail-closed version check | Replay refuses records whose spec/contract version doesn't match — no silent semantic drift. | [versioning](versioning.md) |
| 44 | shadow | Run a candidate flow alongside the live one on real traffic, comparing outcomes without affecting production. | [replay-simulation](replay-simulation.md) |
| 45 | validate | Static analysis: unreachable rules, coverage gaps, overlapping conditions — find dead logic before deploy. | [advanced-features](advanced-features.md) |
| 46 | contract_version | Deterministic SHA-256 hash of the contract's semantics — same logic ⇒ same version, any change ⇒ new version. | [versioning](versioning.md) |
| 47 | deterministic clock replay | Replays use a recorded/fake clock so time-dependent rules behave identically on replay. | [replay-simulation](replay-simulation.md) |

## Portable IR & cross-cutting (SPEC 14.2, 6.x, 4.x)

| # | Feature | What it does | Guide |
|---|---|---|---|
| 48 | PExpr 15 ops | Portable expression tree with 15 operators (`eq`, `gt`, `in`, `and`, `or`, `not`, arithmetic, …) — the cross-language condition language. | [advanced-features](advanced-features.md) |
| 49 | PExpr builders | Fluent constructors (`p_eq`, `p_and`, …) to build expressions without raw dicts. | [advanced-features](advanced-features.md) |
| 50 | expr serialization | Expressions serialize to/from plain dicts — the wire format for IR. | [advanced-features](advanced-features.md) |
| 51 | PortableFlow / PortableRule | Language-neutral contract representation — a flow that any implementation can execute. | [advanced-features](advanced-features.md) |
| 52 | when_expr / when_not_expr | Register rules directly from PExpr trees — write a flow once, run it in five languages. | [advanced-features](advanced-features.md) |
| 53 | from_ir | Rebuild a runnable contract from portable IR — the consumer side of portability. | [advanced-features](advanced-features.md) |
| 54 | to_ir / to_ir_json | Export a compiled contract to portable IR (dict or JSON string) — the producer side. | [advanced-features](advanced-features.md) |
| 55 | PORTABLE / NATIVE classification | Contracts are classified: pure portable rules vs. ones using native (language-specific) callables. | [advanced-features](advanced-features.md) |
| 56 | portability report | Lists exactly which rules/elements block portability and why — actionable, not just a boolean. | [advanced-features](advanced-features.md) |
| 57 | IR limits | Hard caps: expression depth 100, 10k rules, 1 MiB serialized, duplicate-ID rejection — IR can't be a DoS vector. | [advanced-features](advanced-features.md) |
| 58 | flow_id + contract_version in IR | IR carries identity and version — consumers can verify they're running the contract they expect. | [versioning](versioning.md) |
| 59 | PortableFlow JSON round-trip | IR survives `to_json → from_json` byte-for-byte semantically — the basis of cross-language conformance. | [advanced-features](advanced-features.md) |
| 60 | FlowContext | Execution context object passed through evaluation — carries clock, flow_id, trace state. | [framework-integration](framework-integration.md) |
| 61 | with_clock / SystemClock / FakeClock | Inject time: real clock in prod, fake clock in tests — deterministic time-dependent rules. | [framework-integration](framework-integration.md) |
| 62 | with_flow_id | Attach a stable identifier to a contract — appears in traces, IR, and replay records for correlation. | [framework-integration](framework-integration.md) |

## Where to go next

- **Try it:** [getting-started.md](getting-started.md)
- **All features in depth:** the per-topic guides linked above
- **Normative spec:** [SPEC.md](../SPEC.md)
- **Per-language status:** [feature-audit.md](feature-audit.md)
- **Recipes:** [cookbook.md](cookbook.md)
