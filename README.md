# FlowSemantics

A zero-third-party-runtime-dependency, language-neutral execution-semantics library for defining, validating, executing, explaining, and safely simulating complex application decision flows.

Status: **pre-1.0, Phases 0–7 in progress**. Five conformant implementations (Python, TypeScript, Go, Java, C#/.NET) each pass 100% of the 39 conformance vectors and ship the full advanced feature surface (merge, decision tables, effective dates, cancel check, finally timeout, simulate batch, portability report, deep validate). See `PLANNING.md` and `IMPLEMENTATION_STATE.md` for verified state.

## Published packages (v0.1.5)

| Language | Package | Registry | API docs (auto-generated) |
|---|---|---|---|
| Python | `flow-semantics` | [PyPI](https://pypi.org/project/flow-semantics/) | [Sphinx](https://sancy1.github.io/flowsemantics/python/) |
| TypeScript | `flow-semantics-ts` | [npm](https://www.npmjs.com/package/flow-semantics-ts) | [TypeDoc](https://sancy1.github.io/flowsemantics/typescript/) |
| Go | `github.com/sancy1/flowsemantics/go` | [pkg.go.dev](https://pkg.go.dev/github.com/sancy1/flowsemantics/go) | same page (pkg.go.dev renders docs natively) |
| Java | `io.github.sancy1:flowsemantics` | [Maven Central](https://central.sonatype.com/artifact/io.github.sancy1/flowsemantics/0.1.5) | [Javadoc](https://sancy1.github.io/flowsemantics/java/) |
| C# / .NET | `FlowSemantics` | [NuGet](https://www.nuget.org/packages/FlowSemantics/) | [DocFX](https://sancy1.github.io/flowsemantics/csharp/) |

All docs are also indexed from the [documentation site](https://sancy1.github.io/flowsemantics/).

## What this library is

FlowSemantics expresses the decision, error-recovery, guaranteed-cleanup, and interruption-accounting portions of complex application logic as a traceable, testable, portable pipeline. It is an optional higher-level execution model for the cases where a decision becomes an object of concern — where it must be traced, tested, simulated, versioned, audited, ported across languages, externalized into data, or validated for structural soundness.

It is **not** a rules engine, a workflow engine, a fluent pipeline library, a resilience library, or a replacement for native `if` / `try` / `with`. See `docs/non-goals.md`.

## Dependency classes (read carefully)

This project distinguishes three dependency classes. Do not conflate them.

| Class | Policy | What is in it |
|---|---|---|
| Runtime | **Zero third-party** | Nothing. The core uses only the Python standard library. Enforced by `audit.py` in CI. |
| Build | Minimal, justified | `hatchling`, required to build the wheel and sdist. Declared in `[build-system].requires`. |
| Development | Local only, not shipped | `ruff`, `mypy`, `pytest`, `uv` (for local workflow). Declared in `[dependency-groups].dev`. Never installed by consumers. |

The claim is **zero third-party runtime dependencies**, not zero dependencies of every kind. Build and development dependencies exist and are justified.

## Installation (consumer path is `pip`)

Consumers install with plain `pip`. `uv` is a local development convenience only and is **never required by consumers or deployment platforms**.

```
pip install flow-semantics
```

When a deployment platform requires a `requirements.txt`, generate it from the lockfile (it is an export, not a hand-maintained list):

```
uv export --format requirements-txt --no-dev -o requirements.txt
```

## Python compatibility

`requires-python = ">=3.11"`.

Python 3.11 is the minimum for a deliberate reason: the approved semantics include Python exception-group handling, which requires the built-in `ExceptionGroup` introduced in Python 3.11. This is a compatibility decision driven by a semantic requirement, not a preference for modern Python. See `SPEC.md` §11 (error semantics) for the requirement.

## Typing

The package ships `py.typed` (PEP 561). Downstream `mypy` and `pyright` users get full type information. The `py.typed` marker is included in the built wheel — this is a Phase 0.0 exit gate.

## Packaging names

| Purpose | Name |
|---|---|
| PyPI distribution | `flow-semantics` |
| Python import | `flowsemantics` |
| GitHub repository | `github.com/sancy1/flowsemantics` |

**These names must be verified against PyPI and the Python import namespace before the first publish.** The project does not assert availability. Verification is a Phase 0.6 deliverable and is recorded in `PLANNING.md`.

## Documentation

Start at `docs/README.md`.

- `docs/features.md` — all 62 features described in plain language
- `docs/philosophy.md` — the official positioning
- `docs/non-goals.md` — explicit scope boundaries
- `docs/when-not-to-use.md` — where native code wins
- `docs/adr/` — architecture decision records (D1–D3, B1–B8, O1–O7)
- `SPEC.md` — the single authoritative normative specification

## Governance

- `CONTRIBUTING.md` — how to contribute, dependency classes, PR checklist
- `SECURITY.md` — disclosure process
- `CODE_OF_CONDUCT.md` — Contributor Covenant 2.1
- `CHANGELOG.md` — release history (Keep a Changelog format)
- `PLANNING.md` — phase tracker
- `HANDOVER.md` — next-session handoff
- `IMPLEMENTATION_STATE.md` — what has actually shipped, verified

## License

Apache-2.0. See `LICENSE`.

