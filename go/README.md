# flowsemantics (Go)

FlowSemantics expresses the decision, error-recovery, guaranteed-cleanup,
and interruption-accounting portions of complex application logic as a
traceable, testable, portable pipeline — with **zero runtime
dependencies** (Go standard library only).

Repository: [github.com/sancy1/flowsemantics](https://github.com/sancy1/flowsemantics)`n`n**Documentation:** [sancy1.github.io/flowsemantics](https://sancy1.github.io/flowsemantics/) — guides, feature catalog, and API reference

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

The language-neutral feature guides live in the
[repository documentation](https://github.com/sancy1/flowsemantics/tree/main/docs):

- [Feature catalog](https://github.com/sancy1/flowsemantics/blob/main/docs/features.md) — all 62 features
- [Getting started](https://github.com/sancy1/flowsemantics/blob/main/docs/getting-started.md) — first flow
- [Decision tables](https://github.com/sancy1/flowsemantics/blob/main/docs/decision-tables.md) — hit policies
- [Error handling](https://github.com/sancy1/flowsemantics/blob/main/docs/error-handling.md) — catch/rethrow/finally
- [Finalization](https://github.com/sancy1/flowsemantics/blob/main/docs/finalization.md) — guaranteed cleanup
- [Tracing](https://github.com/sancy1/flowsemantics/blob/main/docs/tracing.md) — traces and explain
- [Replay & simulation](https://github.com/sancy1/flowsemantics/blob/main/docs/replay-simulation.md)
- [Advanced features](https://github.com/sancy1/flowsemantics/blob/main/docs/advanced-features.md) — merge, portability
- [Versioning](https://github.com/sancy1/flowsemantics/blob/main/docs/versioning.md)
- [Framework integration](https://github.com/sancy1/flowsemantics/blob/main/docs/framework-integration.md)
- [Cookbook](https://github.com/sancy1/flowsemantics/blob/main/docs/cookbook.md) — recipes

The normative specification is [SPEC.md](https://github.com/sancy1/flowsemantics/blob/main/SPEC.md).

## API documentation

Published docs index: https://sancy1.github.io/flowsemantics

Go doc comments are the single source of truth:

```
go doc github.com/sancy1/flowsemantics/go
```

## Consumer-driven contract tests

`../cdc/go/` contains contract tests written purely from the public
documentation and run against the published module artifact.

## License

Apache-2.0. See `../LICENSE`.
