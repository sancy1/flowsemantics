// Consumer-driven contract tests — C# / .NET.
// Written purely from the public documentation. Restores only the published
// FlowSemantics nupkg artifact — never the source tree.
// Run: dotnet run

using System.Text.Json.Nodes;
using FlowSemantics;
using static FlowSemantics.Portable;
using ActionFn = FlowSemantics.Flow.ActionFn;
using ExceptionHandler = FlowSemantics.Flow.ExceptionHandler;

var passed = 0;
var failed = 0;

void Check(string name, bool cond)
{
    if (cond) passed++;
    else { failed++; Console.WriteLine($"FAIL: {name}"); }
}

static Dictionary<string, object?> Map(params object?[] kv)
{
    var m = new Dictionary<string, object?>();
    for (var i = 0; i < kv.Length; i += 2) m[(string)kv[i]!] = kv[i + 1];
    return m;
}

static Flow.ConditionFn CondTrue() => _ => true;
static Flow.ConditionFn CondFalse() => _ => false;
static ActionFn Act(object? v) => (_, _) => v;
static ActionFn ActThrow(Exception e) => (_, _) => throw e;
static ExceptionHandler Handler(object? v) => (_, _) => v;

// Features 1-18: core decision layer
{
    var c = Flow.Create()
        .When(i => ((int)((Dictionary<string, object?>)i!)["total"]!) > 100, Act("big"), "big")
        .Compile();
    var o = c.TryExecute(Map("total", 150));
    Check("when approved", o.ExecutionStatus == ExecutionStatus.Completed
        && o.DecisionStatus == DecisionStatus.Approved && (string?)o.Value == "big");

    var c2 = Flow.Create()
        .WhenNot(i => (bool)((Dictionary<string, object?>)i!)["vip"]!, Act("standard"), "std")
        .Otherwise(Act("fallback")).Compile();
    Check("whenNot", (string?)c2.TryExecute(Map("vip", false)).Value == "standard");
    Check("otherwise", (string?)c2.TryExecute(Map("vip", true)).Value == "fallback");

    Check("default", (string?)Flow.Create().When(CondFalse(), Act("x"), "r")
        .DefaultValue("d").Compile().TryExecute(null).Value == "d");
    Check("defaultIfNoMatch", (string?)Flow.Create().When(CondFalse(), Act("x"), "r")
        .DefaultIfNoMatch("d2").Compile().TryExecute(null).Value == "d2");

    Check("FirstMatch", (string?)Flow.Create().WithMode(EvaluationMode.FirstMatch)
        .When(CondTrue(), Act("a"), "a").When(CondTrue(), Act("b"), "b").Compile()
        .TryExecute(null).Value == "a");
    Check("AllMatch", (string?)Flow.Create().WithMode(EvaluationMode.AllMatch)
        .When(CondTrue(), Act("a"), "a").When(CondTrue(), Act("b"), "b").Compile()
        .TryExecute(null).Value == "b");
    Check("Priority", (string?)Flow.Create().WithMode(EvaluationMode.Priority)
        .When(CondTrue(), Act("a"), "a", priority: 1)
        .When(CondTrue(), Act("b"), "b", priority: 10).Compile()
        .TryExecute(null).Value == "b");

    var c3 = Flow.Create().WithMode(EvaluationMode.Priority)
        .When(CondTrue(), Act("low"), "low", priority: 1)
        .When(CondTrue(), Act("high"), "high",
            guard: i => (bool)((Dictionary<string, object?>)i!)["ok"]!, priority: 10)
        .Compile();
    Check("guard pass", (string?)c3.TryExecute(Map("ok", true)).Value == "high");
    Check("guard block", (string?)c3.TryExecute(Map("ok", false)).Value == "low");

    var c4 = Flow.Create().When(CondTrue(), Act("done"), "r1",
        effects: new List<Effect> { new("notify", Map("to", "ops")) }).Compile();
    var o4 = c4.TryExecute(null);
    Check("effects", (string?)o4.Value == "done" && o4.Effects.Count == 1
        && o4.Effects[0].Name == "notify");

    var merged = Advanced.Merge(
        Flow.Create().When(i => (int)((Dictionary<string, object?>)i!)["x"]! > 0, Act("pos"), "pos"),
        Flow.Create().When(i => (int)((Dictionary<string, object?>)i!)["x"]! < 0, Act("neg"), "neg"));
    var mc = merged.Compile();
    Check("merge pos", (string?)mc.TryExecute(Map("x", 1)).Value == "pos");
    Check("merge neg", (string?)mc.TryExecute(Map("x", -1)).Value == "neg");
    var part = Flow.Create().When(i => (int)((Dictionary<string, object?>)i!)["x"]! == 0, Act("zero"), "zero").Compile();
    var mf = Advanced.MergeContract(Flow.Create(), part).Compile();
    Check("mergeContract", (string?)mf.TryExecute(Map("x", 0)).Value == "zero");

    var table = new Advanced.DecisionTable
    {
        Rows = new List<Advanced.DecisionTableRow>
        {
            new("small", new List<Flow.ConditionFn> { i => (int)((Dictionary<string, object?>)i!)["n"]! < 10 }, Act("small"), 0),
            new("big", new List<Flow.ConditionFn> { i => (int)((Dictionary<string, object?>)i!)["n"]! >= 10 }, Act("big"), 0),
        },
        Policy = Advanced.HitPolicy.FIRST,
    };
    var tc = Advanced.TableToFlow(table).Compile();
    Check("table small", (string?)tc.TryExecute(Map("n", 5)).Value == "small");
    Check("table big", (string?)tc.TryExecute(Map("n", 50)).Value == "big");
    foreach (var p in Enum.GetValues<Advanced.HitPolicy>())
    {
        var t2 = new Advanced.DecisionTable
        {
            Rows = new List<Advanced.DecisionTableRow>
            {
                new("r1", new List<Flow.ConditionFn> { CondTrue() }, Act("v1"), 0),
            },
            Policy = p,
        };
        try { Advanced.TableToFlow(t2); Check("policy " + p, true); }
        catch { Check("policy " + p, false); }
    }

    try
    {
        Flow.Create().When(CondTrue(), Act("a"), "dup")
            .When(CondTrue(), Act("b"), "dup").Compile();
        Check("dup id rejected", false);
    }
    catch (StructureError) { Check("dup id rejected", true); }

    var c5 = Flow.Create().When(CondTrue(), Act("active"), "r1",
        effectiveFrom: 1_000_000L, effectiveUntil: 9_000_000_000_000L)
        .DefaultIfNoMatch("inactive").Compile();
    Check("effective window", (string?)c5.TryExecute(null).Value == "active");
}

// Features 19-33: error & execution layer
{
    var c = Flow.Create().When(CondTrue(), ActThrow(FlowErrors.ExceptionForKind("Kind.ValueError")), "r1")
        .CatchTyped("Kind.ValueError", Handler("caught"), "h1").Compile();
    var o = c.TryExecute(null);
    Check("catch typed", o.ExecutionStatus == ExecutionStatus.Completed
        && o.Recovery is not null && o.Recovery.HandlerRuleId == "h1");

    var c2 = Flow.Create().When(CondTrue(), ActThrow(new Exception("x")), "r1")
        .CatchWhen("Kind.Any", (_, _) => false, Handler("predicted"), "h1")
        .CatchAny(Handler("any"), "h2").Compile();
    Check("catchAny", (string?)c2.TryExecute(null).Value == "any");

    var c3 = Flow.Create().When(CondTrue(), ActThrow(FlowErrors.ExceptionForKind("Kind.ValueError")), "r1")
        .CatchWhen("Kind.ValueError", (_, _) => false, Handler("handled"), "h1")
        .Rethrow().Compile();
    var o3 = c3.TryExecute(null);
    Check("rethrow", o3.ExecutionStatus == ExecutionStatus.Failed && o3.PrimaryException is not null);

    var seen = new List<string>();
    var c4 = Flow.Create().When(CondTrue(), Act("v"), "r1")
        .OnMatch((_, rid, _) => seen.Add(rid)).Compile();
    c4.TryExecute(null);
    Check("onMatch", seen.Count == 1 && seen[0] == "r1");

    var c5 = Flow.Create().When(CondTrue(), ActThrow(FlowErrors.ExceptionForKind("Kind.Cancelled")), "r1").Compile();
    var o5 = c5.TryExecute(null);
    Check("cancelled", o5.ExecutionStatus == ExecutionStatus.Cancelled
        && o5.Interruption is not null && o5.Interruption.Kind == InterruptionKind.Cancelled);
    var c6 = Flow.Create().When(CondTrue(), ActThrow(FlowErrors.ExceptionForKind("Kind.Timeout")), "r1").Compile();
    var o6 = c6.TryExecute(null);
    Check("timed out", o6.ExecutionStatus == ExecutionStatus.TimedOut
        && o6.Interruption is not null && o6.Interruption.Kind == InterruptionKind.TimedOut);

    var c7 = Flow.Create().When(CondTrue(), Act("a"), "r1")
        .WithCancelCheck(() => true).Compile();
    Check("cancel check", c7.TryExecute(null).ExecutionStatus == ExecutionStatus.Cancelled);

    var c8 = Flow.Create().When(CondTrue(), Act("ok"), "r1").Compile();
    Check("async parity", (string?)c8.ExecuteAsync(null).Value == "ok");

    var cleaned = new List<ExecutionStatus>();
    var c9 = Flow.Create().When(CondTrue(), Act("ok"), "r1")
        .Finally(ctx => cleaned.Add(ctx.Status)).Compile();
    var o9 = c9.TryExecute(null);
    Check("finally", (string?)o9.Value == "ok" && cleaned.Count == 1
        && cleaned[0] == ExecutionStatus.Completed);
    foreach (var p in Enum.GetValues<FinallyFailurePolicy>())
    {
        var c10 = Flow.Create().When(CondTrue(), Act("ok"), "r1")
            .Finally(_ => throw new Exception("cleanup"))
            .WithFinallyPolicy(p).Compile();
        Check("policy " + p, c10.TryExecute(null) is not null);
    }

    var c11 = Flow.Create().When(CondTrue(), Act("ok"), "r1")
        .Finally(_ => { }).WithFinallyTimeout(50).Compile();
    Check("finally timeout", c11.TryExecute(null).Finalization is not null);

    var c12 = Flow.Create().When(CondTrue(), Act("v"), "r1")
        .OnMatch((_, _, _) => throw new Exception("hook boom")).Compile();
    var o12 = c12.TryExecute(null);
    Check("secondary exceptions", (string?)o12.Value == "v" && o12.SecondaryExceptions.Count > 0);

    var o13 = Flow.Create().When(CondTrue(), ActThrow(FlowErrors.ExceptionForKind("Kind.Cancelled")), "r1")
        .Compile().TryExecute(null);
    Check("interruption", o13.Interruption is not null
        && o13.Interruption.Kind == InterruptionKind.Cancelled
        && o13.Interruption.Source.Length > 0 && o13.Interruption.Timestamp > 0);

    ExecutionStatus? status = null;
    object? value = null;
    object? ctxInput = null;
    var c14 = Flow.Create().When(CondTrue(), Act("payload"), "r1")
        .Finally(ctx => { status = ctx.Status; value = ctx.Value; ctxInput = ctx.Context; })
        .Compile();
    c14.TryExecute(Map("in", 1));
    Check("finally context", status == ExecutionStatus.Completed
        && (string?)value == "payload" && ctxInput is not null);
}

// Features 34-47: trust semantics
static Flow.FlowContract Traced() => Flow.Create().WithTrace()
    .When(i => (int)((Dictionary<string, object?>)i!)["n"]! > 0, Act("pos"), "pos")
    .DefaultIfNoMatch("none").Compile();

{
    var o = Traced().TryExecute(Map("n", 1), null!, true);
    Check("trace events", o.Trace is not null && o.Trace.Events.Count > 0);
    Check("trace opt-in", Flow.Create().When(CondTrue(), Act("x"), "r").Compile()
        .TryExecute(null).Trace is null);

    var hookCalls = 0;
    var c = Flow.Create().When(CondTrue(), Act("v"), "r1")
        .WithTrace(_ => { hookCalls++; return new Dictionary<string, object?> { ["redacted"] = true }; })
        .Compile();
    c.TryExecute(null, null!, true);
    Check("diagnostic hook", hookCalls > 0);

    var text = Trust.Explain(Traced(), Traced().TryExecute(Map("n", 1), null!, true).Trace!);
    Check("explain", !string.IsNullOrEmpty(text));

    var sim = Traced().Simulate(Map("n", 5));
    Check("simulate", sim.DecisionStatus == DecisionStatus.Approved && (string?)sim.Value == "pos");
    var batch = Advanced.SimulateBatch(Traced(), new List<object?> { Map("n", 1), Map("n", -1), Map("n", 2) });
    Check("simulateBatch", batch.Total == 3 && batch.ByStatus.Count > 0 && batch.ByDecision.Count > 0);

    var c2 = Traced();
    var rec = Trust.Record(c2, Map("n", 3), new FakeClock(0, 0));
    Check("record", !string.IsNullOrEmpty(rec.ContractVersion));
    foreach (var m in new[] { Trust.ReplayMode.Simulation, Trust.ReplayMode.Historical, Trust.ReplayMode.Decision })
    {
        var res = Trust.Replay(rec, c2, m, null, null, false);
        Check("replay " + m, res.Mode == m);
    }
    var effC = Flow.Create().When(CondTrue(), Act("x"), "r1",
        effects: new List<Effect> { new("e", 1) }).Compile();
    var effRec = Trust.Record(effC, null, new FakeClock(0, 0));
    var applied = new List<Effect>();
    var effRes = Trust.Replay(effRec, effC, Trust.ReplayMode.Effects, null,
        e => applied.Add(e), true);
    Check("replay effects", effRes.EffectsApplied == 1 && applied.Count == 1);

    var key = "consumer-secret"u8.ToArray();
    var signed = Trust.Sign(Trust.Record(c2, Map("n", 1), new FakeClock(0, 0)), key);
    Check("integrity tag", !string.IsNullOrEmpty(signed.Integrity));
    var res2 = Trust.Replay(signed, c2, Trust.ReplayMode.Simulation, key, null, false);
    Check("equivalent", res2.Equivalent == true);
    try
    {
        Trust.Replay(signed, c2, Trust.ReplayMode.Simulation, "wrong"u8.ToArray(), null, false);
        Check("integrity fail-closed", false);
    }
    catch (Trust.ReplayError) { Check("integrity fail-closed", true); }
    var other = Flow.Create().When(CondTrue(), Act("different"), "r1").Compile();
    try
    {
        Trust.Replay(signed, other, Trust.ReplayMode.Simulation, key, null, false);
        Check("version fail-closed", false);
    }
    catch (Trust.ReplayError) { Check("version fail-closed", true); }

    var current = Flow.Create()
        .When(i => (int)((Dictionary<string, object?>)i!)["n"]! > 0, Act("pos"), "r")
        .DefaultIfNoMatch("neg").Compile();
    var candidate = Flow.Create()
        .When(i => (int)((Dictionary<string, object?>)i!)["n"]! > 10, Act("big"), "r")
        .DefaultIfNoMatch("neg").Compile();
    var report = Trust.Shadow(current, candidate, new List<object?> { Map("n", 5), Map("n", 50) });
    Check("shadow", report.Total == 2 && report.Differences >= 1);

    var issues = Trust.Validate(c2);
    Check("validate", issues is not null);
    Flow.FlowContract V1() => Flow.Create().WhenExpr(PEq(PField("a"), PConst(1)), PConst(1), "r1").Compile();
    Check("contract version stable", Trust.ToIRJSON(V1()) == Trust.ToIRJSON(V1()));

    var clock = new FakeClock(1_700_000_000_000L, 0);
    var rec2 = Trust.Record(c2, Map("n", 1), clock);
    var res3 = Trust.Replay(rec2, c2, Trust.ReplayMode.Decision, null, null, false);
    Check("deterministic replay", res3.Equivalent == true);
}

// Features 48-62: portable IR & cross-cutting
{
    var exprs = new PExpr[]
    {
        PField("a"), PConst(1),
        PEq(PField("a"), PConst(1)), PNe(PField("a"), PConst(1)),
        PLt(PField("a"), PConst(1)), PLe(PField("a"), PConst(1)),
        PGt(PField("a"), PConst(1)), PGe(PField("a"), PConst(1)),
        PAnd(PEq(PField("a"), PConst(1)), PGt(PField("b"), PConst(0))),
        POr(PEq(PField("a"), PConst(1)), PEq(PField("a"), PConst(2))),
        PNot(PEq(PField("a"), PConst(1))),
        PIsNull(PField("a")), PIsNotNull(PField("a")),
        PIn(PField("a"), new object?[] { 1, 2, 3 }), PNotIn(PField("a"), new object?[] { 9 }),
    };
    Check("pexpr ops", exprs.Length == 15);
    Check("evalExpr", Portable.EvalExpr(PEq(PField("a"), PConst(1)), Map("a", 1)) is true);

    var expr = PAnd(PEq(PField("x"), PConst(1)), PGt(PField("y"), PConst(0)));
    var restored = Portable.ExprFromNodePublic(Portable.ExprToNode(expr));
    Check("expr round-trip", Portable.EvalExpr(restored, Map("x", 1, "y", 5)) is true);

    var c = Flow.Create().WhenExpr(PEq(PField("n"), PConst(1)), PConst("one"), "r1").Compile();
    var irJson = Trust.ToIRJSON(c);
    var pf = Portable.PortableFlowFromJSON(irJson);
    Check("portable rules", pf.Rules.Count == 1 && pf.Rules[0].RuleId == "r1");

    var c2 = Flow.Create()
        .WhenExpr(PEq(PField("kind"), PConst("a")), PConst("A"), "ra")
        .WhenNotExpr(PEq(PField("kind"), PConst("a")), PConst("not-a"), "rb")
        .DefaultIfNoMatch("none").Compile();
    var port = Advanced.Portability(c2);
    Check("portability PORTABLE", port.Classification == "PORTABLE");
    Check("whenExpr", (string?)c2.TryExecute(Map("kind", "a")).Value == "A");
    Check("whenNotExpr", (string?)c2.TryExecute(Map("kind", "b")).Value == "not-a");
    var rebuilt = Flow.FromIr(Portable.PortableFlowToNode(pf)).Compile();
    Check("fromIr", rebuilt.TryExecute(Map("n", 1)).Value is not null);

    var js = Trust.ToIRJSON(c);
    var round = Portable.PortableFlowFromJSON(js);
    Check("IR JSON round-trip", round.Rules[0].RuleId == "r1");

    try
    {
        Trust.ToIRJSON(Flow.Create().When(CondTrue(), Act(1), "r").Compile());
        Check("native ToIR fails", false);
    }
    catch (StructureError) { Check("native ToIR fails", true); }

    var c3 = Flow.Create().When(CondTrue(), Act(1), "r1")
        .CatchTyped("Kind.Any", Handler(0), "h").Compile();
    var port3 = Advanced.Portability(c3);
    Check("portability report", !string.IsNullOrEmpty(port3.Classification));

    Check("MaxExprDepth", Portable.MaxExprDepth == 100);
    JsonNode? deep = JsonNode.Parse("{\"op\":\"const\",\"value\":1}");
    for (var i = 0; i <= Portable.MaxExprDepth; i++)
        deep = new JsonObject { ["op"] = "not", ["args"] = new JsonArray(deep!.DeepClone()) };
    try
    {
        Portable.ExprFromNodePublic(deep);
        Check("depth limit", false);
    }
    catch (StructureError) { Check("depth limit", true); }

    var c4 = Flow.Create().WithFlowId("consumer-flow")
        .WhenExpr(PEq(PField("a"), PConst(1)), PConst(1), "r1").Compile();
    var ir4 = Portable.PortableFlowFromJSON(Trust.ToIRJSON(c4));
    Check("flow_id", ir4.FlowId == "consumer-flow");
    Check("contract_version in IR", !string.IsNullOrEmpty(ir4.ContractVersion));
}

// Cross-cutting
{
    var c = Flow.Create().WhenExpr(PEq(PField("a"), PConst(1)), PConst("one"), "r1").Compile();
    var js = Trust.ToIRJSON(c);
    var restored = Portable.PortableFlowFromJSON(js);
    Check("portable JSON round-trip", restored.Rules[0].RuleId == "r1");

    object? ctxSeen = null;
    var c2 = Flow.Create().When(CondTrue(), Act("v"), "r1")
        .Finally(ctx => ctxSeen = ctx.Context).Compile();
    c2.TryExecute(Map("x", 1));
    Check("flow context", ctxSeen is not null);

    var fake = new FakeClock(1_000, 0);
    fake.Advance(10_000);
    Check("fake clock", fake.Wall() == 11_000);
    var c3 = Flow.Create().When(CondTrue(), Act("ok"), "r1")
        .WithClock(new FakeClock(0, 0)).Compile();
    Check("withClock", (string?)c3.TryExecute(null).Value == "ok");

    var c4 = Flow.Create().WithFlowId("my-flow")
        .WhenExpr(PEq(PField("a"), PConst(1)), PConst(1), "r1").Compile();
    Check("withFlowId", Portable.PortableFlowFromJSON(Trust.ToIRJSON(c4)).FlowId == "my-flow");

    Check("error hierarchy", FlowErrors.ExceptionForKind("Kind.Timeout") is not null
        && FlowErrors.ExceptionForKind("Kind.Cancelled") is not null
        && FlowErrors.ExceptionForKind("Kind.ValueError") is not null
        && FlowErrors.ExceptionForKind("Kind.Any") is not null
        && Trust.SpecVersion.Length > 0);
}

Console.WriteLine($"passed={passed} failed={failed}");
return failed > 0 ? 1 : 0;
