# flowsemantics (Java)

FlowSemantics expresses the decision, error-recovery, guaranteed-cleanup,
and interruption-accounting portions of complex application logic as a
traceable, testable, portable pipeline — with **zero runtime
dependencies** (JDK standard library only).

Repository: [github.com/sancy1/flowsemantics](https://github.com/sancy1/flowsemantics)`n`n**Documentation:** [sancy1.github.io/flowsemantics](https://sancy1.github.io/flowsemantics/) — guides, feature catalog, and API reference

## Package identity

| Purpose | Name |
|---|---|
| Java package | `flowsemantics` |
| Artifact | `flowsemantics.jar` |
| Minimum Java | 17 |

## Dependencies

Runtime dependencies: **zero third-party**. JDK standard library only
(including `com.sun.net.httpserver`-free JSON handling — the library ships
its own minimal JSON reader/writer).

## Installation

Maven Central publication is in progress. Until then, build the jar from
source (below) and add it to your classpath, or depend on the sources
directly.

## Building (from source)

```
cd java
javac -d out src/flowsemantics/*.java src/flowsemantics/runner/*.java
jar --create --file flowsemantics.jar -C out . -C .. LICENSE
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

Javadoc is generated into `docs/`:

```
javadoc -d docs -sourcepath src flowsemantics
```

## Consumer-driven contract tests

`../cdc/java/` contains contract tests written purely from the public
documentation and run against the published jar artifact.

## License

Apache-2.0. See `../LICENSE`.
