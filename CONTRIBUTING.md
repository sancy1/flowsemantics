# Contributing to FlowSemantics

## Dependency classes

This project distinguishes three dependency classes. Do not conflate them.

| Class | Policy | Where declared |
|---|---|---|
| Runtime | Zero third-party. Standard library only. Enforced by `audit.py` in CI. | Nothing (there are none) |
| Build | Minimal and justified. | `[build-system].requires` in `pyproject.toml` |
| Development | Local only. Never shipped. | `[dependency-groups].dev` in `pyproject.toml` |

Any proposal to add a runtime dependency is a specification change and requires an ADR.

## Tooling

- Local development: `uv`. Not required by consumers, deployment platforms, or the consumer-path CI job.
- Consumer installation: plain `pip`. This is the guaranteed path and is tested in CI on every PR.
- When a platform requires `requirements.txt`, generate it from the lockfile as an export: `uv export --format requirements-txt --no-dev -o requirements.txt`. Do not maintain it by hand.

## Python compatibility

Minimum: Python 3.11. Required by the `ExceptionGroup` semantics in `SPEC.md` section 11. This is a deliberate compatibility decision driven by a semantic requirement, not a preference for modern Python.

## Typing

The wheel ships `py.typed` (PEP 561). This is a Phase 0.0 exit gate: the built wheel must contain `flowsemantics/py.typed`.

## Packaging names

- PyPI distribution: `flow-semantics`
- Python import: `flowsemantics`
- Intended GitHub repository: `flowsemantics`

Availability of these names against PyPI and the Python import namespace must be verified before the first publish. This verification is a Phase 0.6 deliverable and is recorded in `PLANNING.md`. The project does not assert availability.

## Pull request checklist

Every PR must satisfy the Phase 0.0 exit-gate checklist in `.github/PULL_REQUEST_TEMPLATE.md` (added in Script A1.4). No PR is merged with a red gate.

## Architecture Decision Records

Decisions that are expensive to reverse require an ADR under `docs/adr/`. The first is `ADR-0001-governing-decisions.md`, recording D1–D3, B1–B8, and O1–O7. See `docs/adr/README.md` for the ADR process.

