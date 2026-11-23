# flow-semantics-ts (TypeScript package)

This directory contains the TypeScript implementation of FlowSemantics — a
conformance target per `SPEC.md` §14.5.

For the full project documentation, see the repository root `README.md`.

## Package identity

| Purpose | Name |
|---|---|
| npm distribution | `flow-semantics-ts` |
| Import | `flow-semantics-ts` |
| Minimum Node | 22.18 |

## Dependencies

Runtime dependencies: **zero third-party**. Standard library only.

## Installation

```
npm install flow-semantics-ts
```

## Feature documentation

The language-neutral feature guides live in `../docs/`:

- `../docs/features.md` � all 62 features catalog
- `../docs/getting-started.md` — first flow
- `../docs/decision-tables.md` — decision tables and hit policies
- `../docs/error-handling.md` — catch/rethrow/finally semantics
- `../docs/finalization.md` — guaranteed cleanup
- `../docs/tracing.md` — execution traces and explain
- `../docs/replay-simulation.md` — replay, shadow, simulate
- `../docs/advanced-features.md` — merge, effective dates, portability
- `../docs/versioning.md` — contract versioning
- `../docs/framework-integration.md` — embedding in applications
- `../docs/cookbook.md` — recipes

The normative specification is `../SPEC.md`.

## API documentation

TypeScript declaration files (`dist/index.d.ts`) are generated from source
and shipped with the package.

## Consumer-driven contract tests

`../cdc/typescript/` contains contract tests written purely from the public
documentation and run against the published npm tarball.

## License

Apache-2.0. See `../LICENSE`.
