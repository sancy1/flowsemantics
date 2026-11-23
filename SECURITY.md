# Security Policy

## Reporting a vulnerability

Do not open a public issue for a suspected security vulnerability. Report
it privately to the maintainer via the contact method listed in the
repository profile (GitHub private vulnerability reporting is preferred
once enabled; otherwise direct maintainer contact).

## What to include

- A description of the vulnerability and its potential impact.
- Steps to reproduce, including any Portable IR document, replay
  record, or input that triggers it.
- The FlowSemantics version and specification version affected.
- Any suggested mitigation, if known.

## Acknowledgement and fix

- The maintainer acknowledges receipt within 7 days.
- A fix is targeted for the next patch release once confirmed.
- Disclosure is coordinated: the reporter is credited (unless they
  prefer anonymity) in the CHANGELOG security section after the fix
  ships.

## Scope

FlowSemantics is a pure-Python execution-semantics library with **zero
third-party runtime dependencies**. It performs no network access and
no telemetry in its core. The security surface is narrow but not zero:

- Malformed rule graphs and malformed portable IR input
  (deserialization boundaries — see `docs/threat-model.md`).
- Resource exhaustion from pathological rule sets.
- Replay-record tampering (records are inputs to a deterministic
  evaluator; HMAC-SHA256 integrity is provided via `sign()`/`verify()`).

The full threat model, including mitigations and residual risks, is
published at `docs/threat-model.md` (SPEC 15.4).

## Supported versions

Before 1.0.0, only the latest pre-release is supported. After 1.0.0,
the compatibility policy in `docs/versioning.md` applies.
