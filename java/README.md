# flowsemantics (Java library)

This directory contains the Java implementation of FlowSemantics — a
conformance target per `SPEC.md` §14.5.

For the full project documentation, see the repository root `README.md`.

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

## Building

```
cd java
javac -d out src/flowsemantics/*.java src/flowsemantics/runner/*.java
jar --create --file flowsemantics.jar -C out . -C .. LICENSE
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

Javadoc is generated into `docs/`:

```
javadoc -d docs -sourcepath src flowsemantics
```

## Consumer-driven contract tests

`../cdc/java/` contains contract tests written purely from the public
documentation and run against the published jar artifact.

## License

Apache-2.0. See `../LICENSE`.
