using System.Text.Json;
using System.Text.Json.Nodes;
using FlowSemantics;

// Conformance runner — conformance/runner-protocol.md.
// Usage: dotnet run --project FlowSemantics.Runner -- --vectors <dir>
//        dotnet run --project FlowSemantics.Runner -- --selftest

if (args.Length >= 1 && args[0] == "--selftest")
{
    return SelfTest.Run();
}

var dir = "";
for (var i = 0; i < args.Length - 1; i++)
    if (args[i] == "--vectors") dir = args[i + 1];
if (dir.Length == 0)
{
    Console.Error.WriteLine("usage: Runner --vectors <dir> | --selftest");
    return 2;
}

var paths = Directory.GetFiles(dir, "*.json", SearchOption.AllDirectories).OrderBy(p => p).ToList();
if (paths.Count == 0)
{
    Console.WriteLine("RESULT: 0/0 passed (no vectors discovered)");
    return 0;
}

var passed = 0;
foreach (var p in paths)
{
    var r = RunVector(p);
    if (r.Passed) { passed++; Console.WriteLine($"PASS {r.Id}"); }
    else Console.WriteLine($"FAIL {r.Id}: {r.Reason}");
}
Console.WriteLine($"RESULT: {passed}/{paths.Count} passed");
return passed == paths.Count ? 0 : 1;

static (string Id, bool Passed, string Reason) RunVector(string path)
{
    var id = path;
    JsonObject vector;
    try
    {
        vector = JsonNode.Parse(File.ReadAllText(path),
            documentOptions: new JsonDocumentOptions { MaxDepth = 256 })!.AsObject();
    }
    catch (Exception e)
    {
        return (id, false, "parse: " + e.Message);
    }
    id = vector["id"]?.GetValue<string>() ?? id;
    var pipeline = vector["pipeline"]!.AsObject();
    if (pipeline["rules"] is null && pipeline["portable_ir"] is null)
        return (id, false, "pipeline.rules or portable_ir missing");

    var expectedError = vector["expected_error"]?.GetValue<string>();
    Flow flow;
    try { flow = BuildFlow(pipeline); }
    catch (Exception e)
    {
        if (expectedError is not null) return (id, e.Message?.Contains(expectedError) == true, e.Message ?? "");
        return (id, false, e.Message ?? "");
    }

    object? input;
    try { input = Fixtures.ResolveFixture(vector["input"] as JsonObject, new FixtureContext()); }
    catch (Exception e)
    {
        var msg = "input fixture: " + e.Message;
        if (expectedError is not null) return (id, msg.Contains(expectedError), msg);
        return (id, false, msg);
    }

    Flow.FlowContract contract;
    try { contract = flow.Compile(); }
    catch (Exception e)
    {
        var msg = "compile: " + e.Message;
        if (expectedError is not null) return (id, msg.Contains(expectedError), msg);
        return (id, false, msg);
    }

    var clock = new FakeClock(1700000000000L, 0);
    var traceEnabled = vector["trace"] is not null;
    FlowOutcome outcome;
    try { outcome = contract.TryExecute(input, clock, traceEnabled); }
    catch (Exception e)
    {
        var msg = "execution threw: " + e.Message;
        if (expectedError is not null) return (id, msg.Contains(expectedError), msg);
        return (id, false, msg);
    }

    if (expectedError is not null)
        return (id, false, $"expected rejection containing {expectedError} but execution completed");

    var mismatch = CompareExpected(outcome, vector["expected"]!.AsObject());
    if (mismatch is not null) return (id, false, mismatch);
    var terr = CompareTrace(vector, outcome);
    if (terr is not null) return (id, false, terr);
    return (id, true, "");
}

static Flow BuildFlow(JsonObject pipeline)
{
    if (pipeline["portable_ir"] is { } ir)
    {
        try { return Flow.FromIr(ir); }
        catch (Exception e) { throw new Exception("portable_ir rejected: " + e.Message); }
    }

    var flow = Flow.Create();
    if (pipeline["mode"]?.GetValue<string>() is { } mode)
        flow.WithMode(Enum.Parse<EvaluationMode>(mode));
    var ctx = new FixtureContext();

    if (pipeline["rules"] is JsonArray rules)
    {
        foreach (var ro in rules)
        {
            var r = ro!.AsObject();
            var kind = r["kind"]?.GetValue<string>() ?? "when";
            var id = r["id"]?.GetValue<string>() ?? "";
            var av = Fixtures.AsFixture(Fixtures.ResolveFixture(r["action"] as JsonObject, ctx));
            List<Effect>? effects = null;
            if (r["effects"] is JsonArray es)
            {
                effects = new List<Effect>();
                foreach (var ev in es)
                {
                    var em = ev!.AsObject();
                    effects.Add(new Effect(em["name"]!.GetValue<string>(), Portable.ToClr(em["payload"])));
                }
            }
            Flow.GuardFn? guard = null;
            if (r["guard"] is not null)
                guard = Fixtures.AsFixture(Fixtures.ResolveFixture(r["guard"] as JsonObject, ctx)).Guard;
            var priority = r["priority"]?.GetValue<int>() ?? 0;

            if (kind == "then") { flow.Then(av.Action!, id); continue; }
            var cond = Fixtures.AsFixture(Fixtures.ResolveFixture(r["condition"] as JsonObject, ctx)).Cond!;
            if (kind == "when_not") flow.WhenNot(cond, av.Action!, id);
            else flow.When(cond, av.Action!, id, guard, priority, effects);
        }
    }

    if (pipeline["catches"] is JsonArray catches)
    {
        foreach (var co in catches)
        {
            var c = co!.AsObject();
            var ckind = c["kind"]!.GetValue<string>();
            var cid = c["id"]?.GetValue<string>();
            var excKind = c["exc_kind"]?.GetValue<string>();
            if (ckind == "rethrow") { flow.Rethrow(); continue; }
            var hv = Fixtures.AsFixture(Fixtures.ResolveFixture(c["handler"] as JsonObject, ctx));
            if (ckind == "any") { flow.CatchAny(hv.Handler!, cid ?? ""); continue; }
            if (ckind == "typed") { flow.CatchTyped(excKind!, hv.Handler!, cid ?? ""); continue; }
            if (ckind == "when")
            {
                var predCond = Fixtures.AsFixture(Fixtures.ResolveFixture(c["predicate"] as JsonObject, ctx)).Cond!;
                flow.CatchWhen(excKind!, (i, e) => predCond(i), hv.Handler!, cid ?? "");
                continue;
            }
            throw new Exception("unknown catch kind: " + ckind);
        }
    }

    if (pipeline["on_match"] is JsonArray hooks)
        foreach (var ho in hooks)
            flow.OnMatch(Fixtures.AsFixture(Fixtures.ResolveFixture(ho as JsonObject, ctx)).Hook!);

    if (pipeline["finally"] is { } fraw)
    {
        JsonObject? fref = fraw is JsonValue v && v.TryGetValue<string>(out var s)
            ? new JsonObject { ["fixture"] = s }
            : fraw as JsonObject;
        flow.Finally(Fixtures.AsFixture(Fixtures.ResolveFixture(fref, ctx)).Cleanup!);
    }
    if (pipeline["finally_policy"]?.GetValue<string>() is { } fp)
        flow.WithFinallyPolicy(Enum.Parse<FinallyFailurePolicy>(fp));

    if (pipeline["fallback"] is JsonObject fb)
    {
        var fkind = fb["kind"]!.GetValue<string>();
        if (fkind == "otherwise")
        {
            var av = Fixtures.AsFixture(Fixtures.ResolveFixture(fb["action"] as JsonObject, ctx));
            flow.Otherwise(av.Action!);
        }
        else if (fkind == "default_if_no_match")
            flow.DefaultIfNoMatch(Portable.ToClr(fb["value"]));
        else throw new Exception("unknown fallback kind: " + fkind);
    }
    return flow;
}

static string SpecStatus(ExecutionStatus s) => s switch
{
    ExecutionStatus.Completed => "COMPLETED",
    ExecutionStatus.Failed => "FAILED",
    ExecutionStatus.Cancelled => "CANCELLED",
    _ => "TIMED_OUT",
};

static string? SpecDecision(DecisionStatus? d) => d switch
{
    null => null,
    DecisionStatus.Approved => "APPROVED",
    _ => "NO_MATCH",
};

static string? SpecInterruption(InterruptionKind? k) => k switch
{
    null => null,
    InterruptionKind.Cancelled => "cancelled",
    _ => "timed_out",
};

static string? CompareExpected(FlowOutcome o, JsonObject exp)
{
    if (SpecStatus(o.ExecutionStatus) != exp["execution_status"]?.GetValue<string>())
        return $"execution_status: expected {exp["execution_status"]}, got {SpecStatus(o.ExecutionStatus)}";

    var gotDecision = SpecDecision(o.DecisionStatus);
    var expDecision = exp["decision_status"]?.GetValue<string>();
    if (expDecision is null ? gotDecision is not null : expDecision != gotDecision)
        return $"decision_status: expected {expDecision ?? "null"}, got {gotDecision ?? "null"}";

    if (exp["value"] is not null && !JsonEq(Portable.ToClr(exp["value"]), o.Value))
        return $"value: expected {exp["value"]}, got {o.Value}";

    if (exp["has_recovery"]?.GetValue<bool>() is { } hr && hr != (o.Recovery is not null)) return "has_recovery mismatch";
    if (exp["has_interruption"]?.GetValue<bool>() is { } hi && hi != (o.Interruption is not null)) return "has_interruption mismatch";

    var gotKind = SpecInterruption(o.Interruption?.Kind);
    var expKind = exp["interruption_kind"]?.GetValue<string>();
    if (expKind is null ? gotKind is not null : expKind != gotKind)
        return $"interruption_kind: expected {expKind ?? "null"}, got {gotKind ?? "null"}";

    if (exp["has_finalization"]?.GetValue<bool>() is { } hf && hf != (o.Finalization is not null)) return "has_finalization mismatch";
    object? gotClean = o.Finalization?.IsClean;
    var expClean = exp["is_clean"];
    if (expClean is null ? gotClean is not null : !JsonEq(Portable.ToClr(expClean), gotClean))
        return $"is_clean: expected {expClean?.ToJsonString() ?? "null"}, got {gotClean}";

    if (exp["secondary_exceptions_count"]?.GetValue<int>() is { } n && n != o.SecondaryExceptions.Count)
        return $"secondary_exceptions_count: expected {n}, got {o.SecondaryExceptions.Count}";

    var gotPrimary = o.PrimaryException is null ? null : FlowErrors.KindOfException(o.PrimaryException);
    var expPrimary = exp["primary_exception_kind"]?.GetValue<string>();
    if (expPrimary is null ? gotPrimary is not null && gotPrimary.Length > 0 : expPrimary != gotPrimary)
        return $"primary_exception_kind: expected {expPrimary ?? "null"}, got {gotPrimary ?? "null"}";

    if (exp["effects"] is JsonArray want)
    {
        var got = o.Effects.Select(e =>
        {
            var m = new Dictionary<string, object?> { ["name"] = e.Name };
            if (e.Payload is not null) m["payload"] = e.Payload;
            return m;
        }).ToList();
        var wn = want.Select(w =>
        {
            var m = new Dictionary<string, object?>();
            foreach (var kv in w!.AsObject())
                if (kv.Value is not null) m[kv.Key] = Portable.ToClr(kv.Value);
            return m;
        }).ToList();
        if (got.Count != wn.Count || !JsonEq(got, wn))
            return $"effects: expected {string.Join(",", wn.Select(x => x["name"]))}, got {string.Join(",", o.Effects.Select(x => x.Name))}";
    }
    return null;
}

static string? CompareTrace(JsonObject vector, FlowOutcome o)
{
    if (vector["trace"] is not JsonArray expected || expected.Count == 0) return null;
    if (o.Trace is null) return "trace expected but not collected";
    var observed = o.Trace.Events;
    var subset = vector["trace_subset"]?.GetValue<bool>() ?? false;

    bool Matches(TraceEvent ev, JsonObject e) =>
        ev.Type == e["type"]?.GetValue<string>() &&
        (e["rule_id"] is null || ev.RuleId == e["rule_id"]!.GetValue<string>()) &&
        (e["reason"] is null || ev.Reason == e["reason"]!.GetValue<string>());

    if (subset)
    {
        var pos = 0;
        foreach (var eo in expected)
        {
            var e = eo!.AsObject();
            var found = false;
            while (pos < observed.Count)
            {
                if (Matches(observed[pos], e)) { found = true; pos++; break; }
                pos++;
            }
            if (!found) return "trace subset: missing " + e.ToJsonString();
        }
        return null;
    }
    if (observed.Count != expected.Count)
        return $"trace length: expected {expected.Count}, got {observed.Count}";
    for (var i = 0; i < expected.Count; i++)
        if (!Matches(observed[i], expected[i]!.AsObject()))
            return $"trace[{i}]: expected {expected[i]}, got {observed[i].Type}";
    return null;
}

static bool JsonEq(object? a, object? b)
{
    var na = Normalize(a);
    var nb = Normalize(b);
    return JsonSerializer.Serialize(na) == JsonSerializer.Serialize(nb);
}

static object? Normalize(object? v) => v switch
{
    null => null,
    IDictionary<string, object?> d => d.OrderBy(kv => kv.Key).ToDictionary(kv => kv.Key, kv => Normalize(kv.Value)),
    IEnumerable<object?> l when v is not string => l.Select(Normalize).ToList(),
    long l => (double)l,
    int i => (double)i,
    _ => v,
};
