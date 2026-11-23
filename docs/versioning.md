# Versioning and release policy

FlowSemantics versions three things independently: the **package**
(SemVer), the **specification** (SPEC.md, its own version line), and each
**language implementation** (SemVer per package). This page defines the
rules.

## Package versioning (SemVer)

- Before 1.0.0 the package uses `0.x.y` with pre-release tags
  (`0.1.0-alpha.1`, `0.2.0-alpha.1`, `0.3.0-beta.1`, `0.4.0-beta.1`,
  `1.0.0-rc.1`).
- `VERSION` at the repository root is the single source of truth.
  `python/pyproject.toml` reads it dynamically via hatchling; `_version.py`
  resolves it from the source tree or installed metadata. The three never
  diverge.
- MAJOR.MINOR.PATCH follow semver.org: MAJOR for breaking public-API or
  conformance changes, MINOR for backward-compatible features, PATCH for
  fixes.

## What counts as breaking

- Removing or renaming a public symbol in `__all__`.
- Changing the signature or semantics of a public method.
- Changing a normative outcome field (`FlowOutcome` members, enum members).
- Changing conformance-vector expected results for an existing vector id.
- Tightening validation so previously-valid flows now fail `compile()`.

## Compatibility guarantees

- A `FlowContract` compiled by version X MUST produce identical
  `FlowOutcome`s under version X forever (determinism, SPEC.md section 6).
- Public API additions are MINOR; removals/changes are MAJOR.
- `scripts/api-baseline.py` diffs the public API surface in CI; any
  intentional change is recorded in CHANGELOG.md.

## Deprecation policy

- Deprecated symbols remain for at least one MINOR release, emit a
  `DeprecationWarning`, and are listed in CHANGELOG.md before removal.
- Removal happens only in a MAJOR release (or a 0.x MINOR bump before 1.0,
  which is treated as breaking by convention and announced).

## Specification vs package version

- SPEC.md carries its own version (`0.1.0` today, exposed as
  `flowsemantics._spec.SPEC_VERSION`).
- Conformance vectors declare `spec_version`; the runner rejects vectors
  newer than the implementation supports (runner-protocol.md).
- When the spec bumps, implementations may lag: a package at spec 0.1.0
  keeps passing 0.1.0 vectors while a spec 0.2.0 draft is written. At 1.0,
  package and spec versions are expected to align; divergence after 1.0
  requires an ADR.

## Release process

1. Phase exit gate green (all sub-phases, vectors, docs, samples).
2. CHANGELOG.md entry written; IMPLEMENTATION_STATE.md and HANDOVER.md
   updated to describe what actually shipped.
3. Tag `v<version>`; `pack.yml` builds wheel + sdist, produces SBOM,
   signs, and publishes to the configured feed.
4. Pre-release tags follow the release train in the implementation plan
   (alpha for Phases 1-2, beta for Phases 3-5, rc for Phase 6, GA at 8.3).

## Migration

- Every breaking change ships a migration note in CHANGELOG.md and, for
  1.0+, a `docs/migration-vX-to-vY.md` page.
- The conformance suite is the compatibility oracle: if a change alters
  observable semantics, vectors change first (with an ADR), then code.
