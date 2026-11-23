# Replay and simulation

Trust-layer operations (SPEC.md Sections 12.5–12.7, 9.5): simulate,
replay, and shadow — all deterministic, all fail-closed.

## simulate()

```python
result = contract.simulate(input)
```

Runs the decision semantics **without** hooks, finalizers, or effects
(SPEC 12.5). Use it to ask "what would this contract decide?" safely.

## record() and replay()

```python
from flowsemantics import record, replay, ReplayMode

rec = record(contract, input)                    # capture an execution
result = replay(rec, contract, mode=ReplayMode.DECISION)
```

Four modes (`ReplayMode`): `SIMULATION`, `HISTORICAL`, `DECISION`,
`EFFECTS`.

- **Fail-closed** on `spec_version` or `contract_version` mismatch —
  never silently produces a wrong outcome (SPEC 9.5, 12.6).
- **Integrity**: `sign(record, key)` tags a record with HMAC-SHA256;
  `replay(..., integrity_key=key)` verifies it. Unkeyed hashing is not
  sufficient against malicious tampering.
- **EFFECTS mode** requires explicit `authorize_effects=True` plus an
  application-supplied `effect_executor` — the library never applies
  effects itself.
- Equivalence is **semantic** (status, decision, value, recovery,
  interruption), not byte-for-byte (reviewer correction A5). The
  `ReplayResult.equivalent` flag reports it.

## shadow()

```python
from flowsemantics import shadow

report = shadow(current_contract, candidate_contract, inputs)
```

Compares a candidate contract against the current one over a set of
inputs, producing a deterministic `ShadowReport` of divergences —
simulate-based, no effects (SPEC 12.7). Use before deploying a contract
change.

## validate()

```python
issues = contract.validate()
```

Static analysis returning `ValidationIssue` errors/warnings: unreachable
rules, overlaps, coverage gaps (SPEC 12.8).
