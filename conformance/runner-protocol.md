# Conformance runner protocol

Every language implementation of FlowSemantics ships a small adapter that loads conformance vectors, resolves fixtures, runs the flow, and reports pass/fail per vector. This document is the protocol.

## Inputs

1. A directory of vector files matching `spec/vector.schema.json`.
2. The fixture vocabulary in `spec/fixtures.md`.
3. The specification version the runner supports (e.g., `0.1.0`).

## Vector discovery

The runner MUST discover vectors by recursively scanning the vectors directory for files matching `*.json`. Subdirectories are permitted and are scanned recursively. Files that do not match the pattern are ignored. The order of discovery is not normative; implementations MAY sort or process in any order, provided the final pass/fail result is deterministic.

## Outputs

1. One line per vector: `PASS <id>` or `FAIL <id>: <reason>`.
2. A summary line: `RESULT: <passed>/<total> passed`.
3. Exit code 0 if and only if all discovered vectors pass; non-zero otherwise.

## Vector version compatibility

A runner MUST reject a vector whose `spec_version` is newer than the specification version supported by the runner.

A runner SHOULD accept a vector whose `spec_version` is older than the runner supported version when the differences are pure additions and the vector remains semantically valid under the runner supported version, per Section 8.5 of the specification.

If an older vector cannot be interpreted safely under the runner supported version, the runner MUST report an explicit version-incompatibility failure. It MUST NOT silently execute an incompatible vector.

A vector whose `spec_version` matches the runner supported version MUST be accepted.

## Adapter responsibilities

- Discover vectors per the discovery rules above.
- Parse each vector file. A parse error is a runner failure, not an implementation failure; report it distinctly.
- Validate each vector against `spec/vector.schema.json`. A validation failure is a runner failure; report it distinctly.
- Resolve every fixture reference. A missing fixture, invalid parameter, or ambiguous reference is a runner failure; report it distinctly.
- Construct the pipeline from the vector description.
- Execute the pipeline with the specified input, clock, and mode.
- Compare the observed outcome against `expected` per the comparison rules below.
- If `trace` is present, compare the observed trace against `expected.trace` per the trace comparison rules.
- Report PASS or FAIL per vector.
- Return exit code 0 if and only if all vectors pass.

## Outcome comparison rules

The runner MUST compare the observed outcome against `expected` for the following fields:

- `execution_status` - exact match.
- `decision_status` - exact match (null matches null).
- `value` - deep equality per the adapter canonical value-comparison rules.
- `has_recovery` - exact match.
- `has_interruption` - exact match.
- `interruption_kind` - exact match (null matches null).
- `has_finalization` - exact match.
- `is_clean` - exact match (null matches null).
- `secondary_exceptions_count` - exact integer match.
- `primary_exception_kind` - exact match (null matches null).
- `effects` - ordered sequence comparison, order-sensitive. Two effect lists match if and only if they contain the same number of effects, each effect has the same name at the same position, and each effect payload is deeply equal. Order matters because Section 6.4 requires deterministic effect ordering.

The `secondary_exceptions_count` counts exceptions only. It MUST NOT count cancellation, timeout, cleanup budget exhaustion, a skipped finalizer, or a hook that did not raise. If a host language surfaces an exception for an interruption, that exception is counted only when it appears in `cleanup_exceptions` or `secondary_exceptions` per Sections 3.5 and 16.

## Trace comparison rules

If `trace` is present and `trace_subset` is false or absent, the runner MUST compare the full observed trace against the expected trace. Every expected event must match the observed event at the same position, including `type`, `rule_id`, and `reason` where defined.

If `trace_subset` is true, the runner MUST verify that every expected event appears in the observed trace in the same relative order. The observed trace MAY contain additional events not in the expected trace. The runner MUST NOT require the observed trace to contain no additional events.

Trace comparison MUST NOT include timestamps unless the vector explicitly provides an injected clock sequence and declares timestamp comparison via a `timestamp_comparison: true` field in the vector. Without that declaration, timestamps are ignored.

## Fixture resolution errors

Fixture resolution errors are runner failures, not implementation failures. They MUST be reported distinctly with the vector id and the fixture reference that failed. The categories are:

- Unknown fixture - the fixture name does not appear in `spec/fixtures.md`.
- Invalid parameter - the fixture is known but a parameter is missing, of the wrong type, or out of range.
- Ambiguous reference - the fixture reference matches multiple fixture forms.

A runner MUST NOT silently skip a vector whose fixture reference failed. The vector is a FAIL with the fixture error as the reason.

## Test isolation

Each vector MUST be executed in a fresh execution context. State from one vector MUST NOT affect the outcome of another vector.

## Coverage obligation

Every MUST in the specification version supported by the runner MUST be covered by at least one published vector, or by an explicitly recorded, phase-assigned coverage exception.

Coverage exceptions are recorded in `conformance/coverage.md`. Each exception MUST include: the affected MUST or MUST NOT statement, the reason coverage is deferred, the target phase or specification version, and the approver name and date.

A coverage exception does not reduce the eventual requirement that every applicable MUST be covered before any conformance claim or version 1.0 general-availability release.

## No implementation is conformant below 100 percent

This is a normative rule. A language implementation may not call itself conformant, must not be published as 1.0, and must not be advertised as portable until it passes 100 percent of the published vectors for the specification version it targets.

