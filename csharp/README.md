# FlowSemantics (.NET / C#)

FlowSemantics expresses the decision, error-recovery, guaranteed-cleanup,
and interruption-accounting portions of complex application logic as a
traceable, testable, portable pipeline — with **zero third-party
dependencies** (.NET base class library only).

Repository: [github.com/sancy1/flowsemantics](https://github.com/sancy1/flowsemantics)

## Package identity

| Purpose | Name |
|---|---|
| NuGet package | `FlowSemantics` |
| Namespace | `FlowSemantics` |
| Target framework | `net10.0` |
| Version | `0.1.1` |

## Projects

- `FlowSemantics/` — the library (`FlowSemantics.csproj`)
- `FlowSemantics.Runner/` — conformance vector runner

## Dependencies

Runtime dependencies: **zero third-party**. .NET base class library only.

## Installation

```
dotnet add package FlowSemantics
```

Or in your `.csproj`:

```xml
<PackageReference Include="FlowSemantics" Version="0.1.1" />
```

## Building and packing (from source)

```
cd csharp
dotnet build FlowSemantics.Runner/FlowSemantics.Runner.csproj -c Release
dotnet pack FlowSemantics/FlowSemantics.csproj -c Release -o dist
```

Produces `dist/FlowSemantics.0.1.1.nupkg`.

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

XML doc comments are the single source of truth; `GenerateDocumentationFile`
is enabled, so `FlowSemantics.xml` ships inside the nupkg for IDE tooltips.

## Consumer-driven contract tests

`../cdc/csharp/` contains contract tests written purely from the public
documentation and run against the packed nupkg.

## License

Apache-2.0. See `../LICENSE`.
