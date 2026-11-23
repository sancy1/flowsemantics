# flowsemantics (Go module)

This directory contains the Go implementation of FlowSemantics — a
conformance target per `SPEC.md` §14.5.

For the full project documentation, see the repository root `README.md`.

## Package identity

| Purpose | Name |
|---|---|
| Go module | `github.com/sancy1/flowsemantics/go` |
| Import path | `github.com/sancy1/flowsemantics/go` |
| Minimum Go | 1.23 |

## Dependencies

Runtime dependencies: **zero third-party**. Standard library only.

## Installation

```
go get github.com/sancy1/flowsemantics/go
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

Go doc comments are the single source of truth:

```
go doc github.com/sancy1/flowsemantics/go
```

## Consumer-driven contract tests

`../cdc/go/` contains contract tests written purely from the public
documentation and run against the published module artifact.

## License

Apache-2.0. See `../LICENSE`.
