# Consumer-Driven Contract Tests — C# / .NET

Tests written purely from the public documentation, restored and run against
**only the published artifact** — never the source tree.

## Pre-publish (local nupkg)

```bash
# Build the package once (from repo root):
cd csharp
dotnet pack FlowSemantics/FlowSemantics.csproj -c Release -o dist

# Run the consumer tests:
cd ../cdc/csharp
dotnet run
```

Expected: `passed=78 failed=0`

The consumer `Consumer.csproj` references `FlowSemantics 0.1.0` and resolves it
from `../../csharp/dist` via `RestoreSources`. After first restore, NuGet caches
the package — if the library is rebuilt with the same version, delete
`%USERPROFILE%\.nuget\packages\flowsemantics` before re-running.

## Post-publish (NuGet.org)

Remove the `RestoreSources` line and keep:

```xml
<PackageReference Include="FlowSemantics" Version="0.1.0" />
```

## Coverage

All 62 SPEC features: core decision layer (when/whenNot/otherwise/default,
evaluation modes, guard, priority, effects, merge, decision tables, hit
policies, RuleId uniqueness, effective dates), error & execution layer
(typed/when/any catch, rethrow, hooks, cancellation, timeout, finally
policies, secondary exceptions, interruption model, finally context), trust
semantics (trace vocabulary, diagnostic hook, explain, simulate, replay
record/modes, HMAC integrity, fail-closed, shadow, validate, contract
version, deterministic replay), and portable IR (PExpr ops, serialization,
whenExpr/whenNotExpr, fromIr, IR limits, flow_id, contract_version).
