# FlowSemantics (.NET / C#)

This directory contains the C# implementation of FlowSemantics — a
conformance target per `SPEC.md` §14.5.

For the full project documentation, see the repository root `README.md`.

## Package identity

| Purpose | Name |
|---|---|
| NuGet package | `FlowSemantics` |
| Namespace | `FlowSemantics` |
| Target framework | `net10.0` |
| Version | `0.1.0` |

## Projects

- `FlowSemantics/` — the library (`FlowSemantics.csproj`)
- `FlowSemantics.Runner/` — conformance vector runner

## Dependencies

Runtime dependencies: **zero third-party**. .NET base class library only.

## Building and packing

```
cd csharp
dotnet build FlowSemantics.Runner/FlowSemantics.Runner.csproj -c Release
dotnet pack FlowSemantics/FlowSemantics.csproj -c Release -o dist
```

Produces `dist/FlowSemantics.0.1.0.nupkg`.

## Feature documentation

The language-neutral feature guides live in `../docs/`:

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

XML doc comments are the single source of truth; `GenerateDocumentationFile`
is enabled, so `FlowSemantics.xml` ships inside the nupkg for IDE tooltips.

## Consumer-driven contract tests

`../cdc/csharp/` contains contract tests written purely from the public
documentation and run against the packed nupkg.

## License

Apache-2.0. See `../LICENSE`.
