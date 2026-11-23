# flow-semantics-ts (TypeScript)

FlowSemantics expresses the decision, error-recovery, guaranteed-cleanup,
and interruption-accounting portions of complex application logic as a
traceable, testable, portable pipeline — with **zero runtime
dependencies** (Node.js standard library only).

Repository: [github.com/sancy1/flowsemantics](https://github.com/sancy1/flowsemantics)

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

TypeScript declaration files (`dist/index.d.ts`) are generated from source
and shipped with the package.

## Consumer-driven contract tests

`../cdc/typescript/` contains contract tests written purely from the public
documentation and run against the published npm tarball.

## License

Apache-2.0. See `../LICENSE`.
