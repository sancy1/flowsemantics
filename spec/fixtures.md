# Fixture vocabulary

Conformance vectors reference fixtures by name. Each language implementation provides an adapter that resolves these names to host-language callables. This is what makes vectors language-agnostic (D17, R9). Vectors never carry host-language lambdas or serialized code.

## Fixture reference rules

Every fixture reference in a conformance vector MUST name a fixture defined in this vocabulary. A fixture reference MUST NOT use an undefined fixture name, an undefined parameter, an invalid parameter type, or an ambiguous fixture form.

Fixture references MUST be validated when a vector is loaded and validated against the vector schema. A missing fixture, invalid parameter, or ambiguous reference MUST cause the vector to fail validation before execution.

Fixture names are resolved at vector validation time. Fixture behavior is bound at execution time. This separation allows a runner to reject invalid vectors early while still allowing language adapters to provide host-language implementations of the named fixture behavior.

## Condition fixtures

- `cond.true` - a condition that always returns true.
- `cond.false` - a condition that always returns false.
- `cond.returns(value)` - a condition that returns the boolean `value`. `value` MUST be a boolean.
- `cond.throws(Kind)` - a condition that raises an exception of the named abstract kind. `Kind` MUST be one of the abstract error kinds defined below.
- `cond.returns_per_call(values)` - a condition that returns successive boolean values on successive calls. `values` MUST be a non-empty array of booleans. Used to test the "no silent re-evaluation" rule from Section 10.1. The first call returns `values[0]`, the second `values[1]`, and so on. If called more times than `values` has entries, the last value is repeated.

## Action fixtures

- `action.const(value)` - an action that returns the constant `value`. `value` MAY be a string, number, boolean, or null.
- `action.returns(fixture_ref)` - an action that delegates to another action fixture, resolved recursively. Used to compose actions.
- `action.throws(Kind)` - an action that raises an exception of the named abstract kind.

## Guard fixtures

- `guard.true` - a guard that permits the rule (returns true).
- `guard.false` - a guard that vetoes the rule (returns false).

## Catch fixtures

- `catch.handles` - a catch handler that recovers the caught exception and returns a constant value.
- `catch.throws(Kind)` - a catch handler that itself raises an exception of the named abstract kind when invoked. Used to test that a failing catch handler propagates the new exception per Section 11.1.

## Hook fixtures

- `hook.records` - an on_match hook that appends a record to the trace. Never fails.
- `hook.throws(Kind)` - an on_match hook that raises a named exception. Must be isolated into secondary exceptions and never trigger a catch.

## Cleanup fixtures

- `cleanup.succeeds` - a finalizer that returns normally.
- `cleanup.throws(Kind)` - a finalizer that raises a named exception.
- `cleanup.cooperative` - a finalizer that observes the cancellation token and stops promptly.
- `cleanup.ignores_token` - a finalizer that ignores the cancellation token (tests the B8 cooperative guarantee honesty).
- `cleanup.delays(ms)` - a finalizer that sleeps for `ms` milliseconds before returning. `ms` MUST be a positive integer. Used to test cleanup budget behavior.

## Enrichment fixtures

- `enrichment.delayed(ms)` - an enrichment operation that returns a value after `ms` milliseconds. `ms` MUST be a positive integer. Used to test timeout behavior. This is an explicit effect, not a condition; it appears in the pipeline proposed effects, not in rule conditions.

## Input fixtures

- `input.empty` - an input with no data. All condition fixtures that read fields should treat missing fields as absent.
- `input.order_50` - a sample order input with total 50.
- `input.order_0` - a sample order input with total 0 (triggers no-match in typical flows).
- `input.order_large` - a sample order input with total 10000 (above typical thresholds).

## Abstract error kinds

Each fixture parameter `Kind` is an abstract error kind that each language maps to a concrete exception type. The starting kinds are:

- `Kind.Timeout` - mapped to `TimeoutError` in Python, `TimeoutException` in C#, etc.
- `Kind.Cancelled` - mapped to `asyncio.CancelledError` in Python, `OperationCanceledException` in C#.
- `Kind.ValueError` - mapped to `ValueError` in Python, `ArgumentException` in C#.
- `Kind.Any` - a generic error not covered by the named kinds.

Each language implementation MUST map each abstract kind to a concrete exception type and MUST document the mapping. A vector that uses an abstract kind not mapped by the implementation MUST fail the conformance run with a clear error.

## Fixture registration

Each language implementation registers its fixtures under a fixed namespace and resolves them at vector-load time. A vector that references an unknown fixture must fail the conformance run, not silently skip.

The fixture namespace is fixed: `cond.*`, `action.*`, `guard.*`, `catch.*`, `hook.*`, `cleanup.*`, `enrichment.*`, `input.*`. Implementations MUST NOT extend the namespace with new prefixes without an ADR and a specification version bump. Implementations MAY add new fixtures within existing prefixes, but such additions do not become part of the conformance contract unless a vector uses them.

## Example

A minimal vector that uses `cond.true`, `action.const(42)`, and `input.empty`:

    {
      "id": "001-core-when-true",
      "pipeline": {
        "rules": [
          {
            "id": "r1",
            "condition": { "fixture": "cond.true" },
            "action": { "fixture": "action.const", "params": { "v": 42 } }
          }
        ]
      },
      "input": { "fixture": "input.empty" }
    }

