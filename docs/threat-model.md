# Threat model — FlowSemantics (Python)

SPEC.md Section 9.1 and 15.4 require every implementation to publish a
threat model covering malformed rule graphs, deserialization attacks,
resource exhaustion, replay-record tampering, and the library security
boundaries. This document is that publication for the Python
implementation.

## Assets

- **Integrity of the decision**: a FlowOutcome must reflect exactly the
  rules, input, and clock it was executed with. Tampering that changes
  the outcome without changing the contract is the primary concern.
- **Availability of the host process**: the library runs inside the
  application's process; a pathological contract must not be able to
  exhaust memory or CPU unboundedly.
- **Confidentiality of inputs**: inputs may contain sensitive data.
  The library must not leak them (no telemetry, no network, no logging
  by default — SPEC 15.2).

## Trust boundaries

| Boundary | Trusted side | Untrusted side |
|---|---|---|
| Portable IR deserialization | Application code that produced the IR | IR documents from files, network, or other tenants |
| Rule evaluation | The compiled FlowContract | The input value and the clock |
| Replay records | Records produced by `record()` in this process | Records loaded from storage |
| Effects | The application-owned EffectExecutor | The library (never executes effects) |

The library itself is trusted code. The threats below concern what
untrusted *data* can do to it.

## Threats and mitigations

### 1. Malformed rule graphs from the Portable IR

An attacker supplies syntactically valid but pathological IR: deep
nesting, huge rule counts, duplicate RuleIds, unknown operators.

**Mitigations (SPEC 9.2, implemented):**

- `MAX_EXPR_DEPTH = 100` — expression nesting deeper than 100 rejected
  with `StructureError` at deserialization.
- `MAX_RULES = 10_000` — rule lists longer than 10,000 rejected.
- `MAX_IR_BYTES = 1_000_000` — serialized IR larger than 1 MiB rejected
  in `PortableFlow.from_json`.
- Duplicate `rule_id` values rejected at deserialization, not at
  execution.
- Unknown expression ops rejected (`OPS` closed set).
- The IR carries no executable code; `kind: "then"` is rejected by
  `Flow.from_ir` (ADR-0003).

**Residual risk**: `Flow.from_ir` accepts an already-parsed `dict`;
the byte-size limit applies to the JSON-string path only. In-process
dict construction is trusted application code. Cyclic references are
impossible: JSON parsing produces trees, and `expr_from_dict` builds
fresh `PExpr` nodes.

### 2. Deserialization attacks via the IR

Crafted JSON targeting a lenient parser: deeply nested arrays,
oversized payloads, duplicate keys, type confusion.

**Mitigations**: the depth/size/rule-count limits above; `json.loads`
produces only JSON types; every field access uses `.get()` with type
checks at the `PortableRule`/`PExpr` boundary; unknown ops and kinds
raise `StructureError`. Python's `json` module is not vulnerable to
object-injection (no `__reduce__` equivalent).

**Residual risk**: `json.loads` itself has recursion limits for deeply
nested *arrays* (handled by CPython's own limit, raising
`RecursionError`/`JSONDecodeError` — surfaced as a parse error, not a
crash of the host beyond the exception). Duplicate keys in JSON objects
are last-wins per JSON spec; the IR schema does not rely on key
uniqueness for security.

### 3. Resource exhaustion via pathological rule sets

A contract with thousands of matching rules, or `AllMatch` mode over a
huge input, could consume CPU/memory.

**Mitigations**: rule count is bounded at compile time by
`MAX_RULES` for portable flows; native flows are built by application
code (trusted). Execution is single-threaded and deterministic; there
is no unbounded loop — evaluation is a single pass over the rule list
(FirstMatch/Priority short-circuit; AllMatch is O(rules) by design).

**Documented non-limits (SPEC 9.3)**: the implementation imposes **no**
hidden execution-time, memory, or rule-evaluation-count limits.
Applications requiring hard bounds must wrap `try_execute` with their
own timeout/cancellation (e.g. `asyncio.wait_for` on
`try_execute_async`, or a thread-level timeout). This is documented
here per SPEC 9.3's documentation requirement.

### 4. Replay-record tampering

A `ReplayRecord` loaded from storage could be modified to produce a
fraudulent replay outcome.

**Mitigations (SPEC 9.5, 12.6, implemented)**:

- `sign()`/`verify()` provide HMAC-SHA256 integrity over a canonical
  JSON payload; `replay()` verifies when `integrity_key` is supplied.
- Replay fails closed on `spec_version` or `contract_version`
  mismatch.
- EFFECTS mode requires explicit `authorize_effects=True` and an
  application-supplied executor — never a default.
- Unkeyed hashing is not presented as tamper protection; HMAC is the
  documented mechanism.

**Residual risk**: an application that stores records without calling
`sign()` has no integrity protection — this is an application
responsibility, documented in `docs/replay-simulation.md` (pending).

### 5. Library security boundaries (what it does NOT do)

Per SPEC 15.5/1.3, the library does not: authenticate, authorize,
encrypt, manage secrets, perform network I/O, emit telemetry, or apply
effects. Effects are proposed data only; an application-owned
`EffectExecutor` applies them. Purity of user callbacks is enforced by
contract and audit tooling, not by the runtime — the library cannot
prove a lambda is pure (SPEC 5.3 honesty clause).

## Disclosure process

See `SECURITY.md`. Report privately to the maintainer; do not open
public issues for suspected vulnerabilities.

## Versioning of this document

This threat model covers the Python implementation at SPEC v0.1. It
MUST be updated when: the IR format changes, new deserialization
boundaries are added, resource limits are introduced, or the replay
integrity mechanism changes.
