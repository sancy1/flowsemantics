using System.Text.Json.Nodes;

namespace FlowSemantics;

/// Mutable context shared across fixture resolutions within one vector run.
public sealed class FixtureContext
{
    /// Records captured by hook.records fixtures.
    public List<Dictionary<string, object?>> Records { get; } = new();
}

/// A resolved fixture: one or more callable slots (condition, action, guard,
/// handler, hook, cleanup) depending on the fixture kind.
public sealed class FixtureValue
{
    /// Condition callback (cond.* fixtures).
    public Flow.ConditionFn? Cond { get; set; }
    /// Action callback (action.* fixtures).
    public Flow.ActionFn? Action { get; set; }
    /// Guard callback (guard.* fixtures).
    public Flow.GuardFn? Guard { get; set; }
    /// Exception handler callback (catch.* fixtures).
    public Flow.ExceptionHandler? Handler { get; set; }
    /// Match hook callback (hook.* fixtures).
    public Flow.HookFn? Hook { get; set; }
    /// Finalizer cleanup callback (cleanup.* fixtures).
    public Flow.CleanupFn? Cleanup { get; set; }
}

/// Fixture vocabulary — spec/fixtures.md, C# adapter.
public static class Fixtures
{
    private static readonly Dictionary<string, object?> Inputs = new()
    {
        ["input.empty"] = new Dictionary<string, object?>(),
        ["input.order_50"] = new Dictionary<string, object?> { ["total"] = 50.0 },
        ["input.order_0"] = new Dictionary<string, object?> { ["total"] = 0.0 },
        ["input.order_large"] = new Dictionary<string, object?> { ["total"] = 10000.0 },
    };

    /// Resolve a fixture reference (or nested action.returns ref) to a value.
    public static object? ResolveFixture(JsonObject? reference, FixtureContext ctx)
    {
        var name = reference?["fixture"]?.GetValue<string>() ?? "";
        var prms = reference?["params"] as JsonObject;
        object? P(string k) => prms?[k] is { } n ? Portable.ToClr(n) : null;
        string PS(string k) => P(k)?.ToString() ?? "";
        bool PB(string k) => P(k) is true;
        double PN(string k) => P(k) switch { double d => d, long l => l, int i => i, _ => 0 };

        if (Inputs.TryGetValue(name, out var input)) return input;

        var fv = new FixtureValue();
        switch (name)
        {
            case "cond.true": fv.Cond = _ => true; break;
            case "cond.false": fv.Cond = _ => false; break;
            case "cond.returns": { var v = PB("value"); fv.Cond = _ => v; break; }
            case "cond.throws": { var k = PS("kind"); fv.Cond = _ => throw FlowErrors.ExceptionForKind(k); break; }
            case "cond.returns_per_call":
                {
                    var vals = prms?["values"] as JsonArray ?? new JsonArray();
                    var idx = 0;
                    fv.Cond = _ =>
                    {
                        var v = idx < vals.Count ? vals[idx++]?.GetValue<bool>() ?? false : vals.Count > 0 && vals[^1]!.GetValue<bool>();
                        return v;
                    };
                    break;
                }
            case "action.const": { var v = P("v"); fv.Action = (_, _) => v; break; }
            case "action.throws": { var k = PS("kind"); fv.Action = (_, _) => throw FlowErrors.ExceptionForKind(k); break; }
            case "action.prev": fv.Action = (_, prev) => prev; break;
            case "action.returns":
                {
                    var sub = prms?["ref"] ?? prms?["fixture_ref"];
                    return ResolveFixture(sub as JsonObject, ctx);
                }
            case "guard.true": fv.Guard = _ => true; break;
            case "guard.false": fv.Guard = _ => false; break;
            case "catch.handles": { var v = P("v"); fv.Handler = (_, _) => v; break; }
            case "catch.throws": { var k = PS("kind"); fv.Handler = (_, _) => throw FlowErrors.ExceptionForKind(k); break; }
            case "hook.records": fv.Hook = (_, rid, v) => ctx.Records.Add(new() { ["rule_id"] = rid, ["value"] = v }); break;
            case "hook.throws": { var k = PS("kind"); fv.Hook = (_, _, _) => throw FlowErrors.ExceptionForKind(k); break; }
            case "cleanup.succeeds": fv.Cleanup = _ => { }; break;
            case "cleanup.throws": { var k = PS("kind"); fv.Cleanup = _ => throw FlowErrors.ExceptionForKind(k); break; }
            case "cleanup.cooperative": fv.Cleanup = _ => { }; break;
            case "cleanup.ignores_token": fv.Cleanup = _ => { }; break;
            case "cleanup.delays": fv.Cleanup = _ => { }; break;
            case "enrichment.delayed": { var ms = PN("ms"); fv.Action = (_, _) => new Dictionary<string, object?> { ["delayed_ms"] = ms }; break; }
            default: throw new StructureError("unknown fixture: " + name);
        }
        return fv;
    }

    /// Cast a resolved fixture value to FixtureValue; throws StructureError otherwise.
    public static FixtureValue AsFixture(object? v) =>
        v as FixtureValue ?? throw new StructureError("expected FixtureValue, got " + v?.GetType());
}
