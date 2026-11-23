using System.Text.Json.Nodes;
using FlowSemantics;

namespace FlowSemantics;

/// Unit tests — plain assertions, zero deps. Run: --selftest
public static class SelfTest
{
    static int _passed, _failed;

    static void Check(bool cond, string name)
    {
        if (cond) _passed++;
        else { _failed++; Console.WriteLine("FAIL: " + name); }
    }

    static Flow.ConditionFn CondTrue() => _ => true;
    static Flow.ConditionFn CondFalse() => _ => false;
    static Flow.ActionFn Act(string v) => (_, _) => v;

    public static int Run()
    {
        // when match
        var c1 = Flow.Create().When(CondTrue(), Act("ok"), "r1").Compile();
        var o1 = c1.TryExecute(null);
        Check(o1.ExecutionStatus == ExecutionStatus.Completed && "ok".Equals(o1.Value), "when match");
        Check(o1.DecisionStatus == DecisionStatus.Approved, "approved");

        // no match
        var c2 = Flow.Create().When(CondFalse(), Act("x"), "r1").Compile();
        Check(c2.TryExecute(null).DecisionStatus == DecisionStatus.NoMatch, "no match");

        // first match short circuit
        var second = 0;
        var c3 = Flow.Create()
            .When(CondTrue(), Act("first"), "r1")
            .When(_ => { second++; return true; }, Act("second"), "r2")
            .Compile();
        Check("first".Equals(c3.TryExecute(null).Value) && second == 0, "first match");

        // all match last wins
        var c4 = Flow.Create().WithMode(EvaluationMode.AllMatch)
            .When(CondTrue(), Act("a"), "r1")
            .When(CondTrue(), Act("b"), "r2").Compile();
        Check("b".Equals(c4.TryExecute(null).Value), "all match");

        // then receives previous
        var c6 = Flow.Create()
            .When(CondTrue(), (_, _) => 1, "r1")
            .Then((_, p) => (int)p! + 1, "t1").Compile();
        Check(Equals(2, c6.TryExecute(null).Value), "then prev");

        // guard veto
        var c7 = Flow.Create()
            .When(CondTrue(), Act("x"), "r1", _ => false).Compile();
        Check(c7.TryExecute(null).DecisionStatus == DecisionStatus.NoMatch, "guard veto");

        // typed catch recovers
        var c8 = Flow.Create()
            .When(CondTrue(), (_, _) => throw new KindValueError("boom"), "r1")
            .CatchTyped("Kind.ValueError", (_, _) => "recovered", "c1").Compile();
        var o8 = c8.TryExecute(null);
        Check(o8.ExecutionStatus == ExecutionStatus.Completed && "recovered".Equals(o8.Value), "catch recovers");
        Check(o8.Recovery is not null && o8.DecisionStatus is null, "recovery info, null decision");

        // uncaught failed
        var c9 = Flow.Create()
            .When(CondTrue(), (_, _) => throw new KindValueError("x"), "r1").Compile();
        Check(c9.TryExecute(null).ExecutionStatus == ExecutionStatus.Failed, "uncaught failed");

        // timeout bypasses catch
        var c10 = Flow.Create()
            .When(CondTrue(), (_, _) => throw new KindTimeout("t"), "r1")
            .CatchAny((_, _) => "no", "c1").Compile();
        var o10 = c10.TryExecute(null);
        Check(o10.ExecutionStatus == ExecutionStatus.TimedOut, "timeout interruption");
        Check(o10.Interruption?.Kind == InterruptionKind.TimedOut, "timed_out kind");

        // cancelled bypasses catch
        var c11 = Flow.Create()
            .When(CondTrue(), (_, _) => throw new KindCancelled("c"), "r1")
            .CatchAny((_, _) => "no", "c1").Compile();
        Check(c11.TryExecute(null).ExecutionStatus == ExecutionStatus.Cancelled, "cancelled");

        // finally on success
        var ran = false;
        var c12 = Flow.Create()
            .When(CondTrue(), Act("v"), "r1")
            .Finally(_ => ran = true).Compile();
        var o12 = c12.TryExecute(null);
        Check(ran && o12.Finalization?.IsClean == true, "finally clean");

        // finally preserve primary
        var c13 = Flow.Create()
            .When(CondTrue(), (_, _) => throw new KindValueError("primary"), "r1")
            .Finally(_ => throw new KindTimeout("cleanup")).Compile();
        var o13 = c13.TryExecute(null);
        Check(o13.PrimaryException is KindValueError, "preserve primary");
        Check(o13.Finalization?.IsClean == false, "is_clean false");

        // finally replace primary
        var c14 = Flow.Create().WithFinallyPolicy(FinallyFailurePolicy.ReplacePrimary)
            .When(CondTrue(), (_, _) => throw new KindValueError("primary"), "r1")
            .Finally(_ => throw new KindTimeout("cleanup")).Compile();
        Check(c14.TryExecute(null).PrimaryException is KindTimeout, "replace primary");

        // trace
        var c16 = Flow.Create()
            .When(CondFalse(), Act("x"), "r1")
            .When(CondTrue(), Act("y"), "r2").Compile();
        var o16 = c16.TryExecute(null, new FakeClock(0, 0), true);
        Check(o16.Trace?.Events.Any(e => e.Type == "rule_skipped") == true, "trace events");

        // portable IR
        var ir = JsonNode.Parse("""
            {"spec_version":"0.1.0","flow_id":"f","portability":"PORTABLE","mode":"FirstMatch",
             "rules":[{"rule_id":"r1","kind":"when",
               "condition":{"op":"gt","args":[{"op":"field","value":"x"},{"op":"const","value":0}]},
               "transform":{"op":"const","value":"pos"}}],
             "fallback":{"kind":"default_if_no_match","value":"neg"}}
            """);
        var c17 = Flow.FromIr(ir!).Compile();
        Check("pos".Equals(c17.TryExecute(new Dictionary<string, object?> { ["x"] = 5.0 }).Value), "IR pos");
        Check("neg".Equals(c17.TryExecute(new Dictionary<string, object?> { ["x"] = -1.0 }).Value), "IR neg");

        // IR duplicate rejection
        var dupRejected = false;
        try
        {
            Portable.PortableFlowFromNode(JsonNode.Parse("""
                {"spec_version":"0.1.0","flow_id":"f","portability":"PORTABLE","mode":"FirstMatch",
                 "rules":[{"rule_id":"d","kind":"when","condition":{"op":"const","value":true},
                   "transform":{"op":"const","value":1}},
                  {"rule_id":"d","kind":"when","condition":{"op":"const","value":true},
                   "transform":{"op":"const","value":1}}]}
                """));
        }
        catch { dupRejected = true; }
        Check(dupRejected, "IR duplicate rejected");

        // IR depth rejection
        var depthRejected = false;
        try
        {
            var expr = (JsonNode)new JsonObject { ["op"] = "const", ["value"] = true };
            for (var i = 0; i < Portable.MaxExprDepth + 2; i++)
                expr = new JsonObject { ["op"] = "not", ["args"] = new JsonArray(expr) };
            Portable.PortableFlowFromNode(JsonNode.Parse("""
                {"spec_version":"0.1.0","flow_id":"f","portability":"PORTABLE","mode":"FirstMatch",
                 "rules":[{"rule_id":"r","kind":"when","condition":null,"transform":{"op":"const","value":1}}]}
                """)!.AsObject().Also(o => o["rules"]![0]!["condition"] = expr));
        }
        catch { depthRejected = true; }
        Check(depthRejected, "IR depth rejected");

        // simulate skips hooks
        var hooked = 0;
        var c18 = Flow.Create()
            .When(CondTrue(), Act("v"), "r1")
            .OnMatch((_, _, _) => hooked++).Compile();
        c18.Simulate(null);
        Check(hooked == 0, "simulate no hooks");

        // contract version stable
        var cv1 = Flow.Create().When(CondTrue(), Act("x"), "r1").Compile();
        var cv2 = Flow.Create().When(CondTrue(), Act("x"), "r1").Compile();
        Check(cv1.ContractVersion == cv2.ContractVersion && cv1.ContractVersion.Length > 0, "contract version stable");
        var cv3 = Flow.Create().When(CondTrue(), Act("y"), "r2").Compile();
        Check(cv1.ContractVersion != cv3.ContractVersion, "version differs");

        // validate empty flow
        var ve = Flow.Create().Compile();
        var vi = Trust.Validate(ve);
        Check(vi.Count == 1 && vi[0].Code == "empty_flow", "validate empty_flow");

        // explain
        var ce = Flow.Create().When(CondFalse(), Act("x"), "r1").Compile();
        var oe = ce.TryExecute(null, new FakeClock(0, 0), true);
        var ex = Trust.Explain(ce, oe.Trace!);
        Check(ex.Contains("FlowContract") && ex.Contains("rule_skipped"), "explain output");

        // replay simulation + historical
        var cr = Flow.Create().When(CondTrue(), Act("v"), "r1").Compile();
        var rec = Trust.Record(cr, null, new FakeClock(0, 0));
        var rsim = Trust.Replay(rec, cr, Trust.ReplayMode.Simulation, null, null, false);
        Check(rsim.Equivalent == true, "replay simulation equivalent");
        var rhist = Trust.Replay(rec, cr, Trust.ReplayMode.Historical, null, null, false);
        Check(ReferenceEquals(rhist.Outcome, rec.Outcome), "replay historical");

        // fail closed on version mismatch
        rec.ContractVersion = "tampered";
        var closed = false;
        try { Trust.Replay(rec, cr, Trust.ReplayMode.Simulation, null, null, false); }
        catch (Trust.ReplayError) { closed = true; }
        Check(closed, "replay fail-closed");

        // integrity
        rec.ContractVersion = cr.ContractVersion;
        var signed = Trust.Sign(rec, "key"u8.ToArray());
        Trust.Replay(signed, cr, Trust.ReplayMode.Simulation, "key"u8.ToArray(), null, false);
        var integFail = false;
        try { Trust.Replay(signed, cr, Trust.ReplayMode.Simulation, "wrong"u8.ToArray(), null, false); }
        catch (Trust.ReplayError) { integFail = true; }
        Check(integFail, "replay integrity");

        // effects auth
        var ce2 = Flow.Create().When(CondTrue(), Act("v"), "r1").Compile();
        var rec2 = Trust.Record(ce2, null, new FakeClock(0, 0));
        var authFail = false;
        try { Trust.Replay(rec2, ce2, Trust.ReplayMode.Effects, null, null, false); }
        catch (Trust.ReplayError) { authFail = true; }
        Check(authFail, "effects auth required");

        // shadow
        var cur = Flow.Create().When(CondTrue(), Act("a"), "r1").Compile();
        var cand = Flow.Create().When(CondTrue(), Act("b"), "r1").Compile();
        var rep = Trust.Shadow(cur, cand, new object?[] { null, null });
        Check(rep.Total == 2 && rep.Differences == 2, "shadow report");

        // --- advanced ---
        // merge
        var f1 = Flow.Create().When(CondTrue(), Act("a"), "r1");
        var f2 = Flow.Create().When(CondFalse(), Act("b"), "r2").DefaultIfNoMatch("fb");
        var merged = Advanced.Merge(f1, f2);
        Check("a".Equals(merged.Compile().TryExecute(null).Value), "merge value");
        var modeFail = false;
        try { Advanced.Merge(Flow.Create(), Flow.Create().WithMode(EvaluationMode.AllMatch)); }
        catch (StructureError) { modeFail = true; }
        Check(modeFail, "merge mode mismatch");
        // decision table
        var table = new Advanced.DecisionTable
        {
            Rows = new List<Advanced.DecisionTableRow>
            {
                new("big", new List<Flow.ConditionFn> { CondTrue() }, Act("big")),
                new("small", new List<Flow.ConditionFn> { CondFalse() }, Act("small")),
            },
        };
        Check("big".Equals(Advanced.TableToFlow(table).Compile().TryExecute(null).Value), "table value");
        // effective dates
        long from = 1700000000000L, until = 1800000000000L;
        var ec = Flow.Create().When(CondTrue(), Act("v"), "r1", effectiveFrom: from, effectiveUntil: until).Compile();
        Check(ec.TryExecute(null, new FakeClock(0, 0), true).DecisionStatus == DecisionStatus.NoMatch, "before window");
        Check("v".Equals(ec.TryExecute(null, new FakeClock((from + until) / 2, 0), true).Value), "inside window");
        Check(ec.TryExecute(null, new FakeClock(until + 1, 0), true).DecisionStatus == DecisionStatus.NoMatch, "after window");
        var invFail = false;
        try { Flow.Create().When(CondTrue(), Act("v"), "r1", effectiveFrom: until, effectiveUntil: from).Compile(); }
        catch (StructureError) { invFail = true; }
        Check(invFail, "inverted window");
        // cancel check
        var cancelled = false;
        var cc = Flow.Create().WithCancelCheck(() => cancelled).When(CondTrue(), Act("v"), "r1").Compile();
        cancelled = true;
        Check(cc.TryExecute(null).ExecutionStatus == ExecutionStatus.Cancelled, "cancel check");
        // simulate batch
        var sc = Flow.Create().When(CondTrue(), Act("v"), "r1").Compile();
        var rep2 = Advanced.SimulateBatch(sc, new List<object?> { null, null });
        Check(rep2.Total == 2 && rep2.ByDecision.GetValueOrDefault("Approved") == 2, "simulate batch");
        // portability
        var (cls, off) = Advanced.Portability(sc);
        Check(cls == "NATIVE" && off.Length > 0, "portability report");
        // finally timeout (SystemClock so monotonic advances)
        var ft = Flow.Create().WithFinallyTimeout(1)
            .When(CondTrue(), Act("v"), "r1")
            .Finally(ctx => Thread.Sleep(5))
            .Compile();
        Check(ft.TryExecute(null).Finalization?.CleanupBudgetExceeded == true, "finally budget");
        // validate depth
        var gap = false;
        foreach (var i in Trust.Validate(sc)) if (i.Code == "possible_gap") gap = true;
        Check(gap, "gap warning");

        // --- Phase 8 parity additions ---
        // execute propagates
        var ec2 = Flow.Create()
            .When(CondTrue(), (_, _) => throw new InvalidOperationException("boom"), "r1").Compile();
        var threw = false;
        try { ec2.Execute(null); } catch (InvalidOperationException) { threw = true; }
        Check(threw, "execute propagates");
        Check(ec2.TryExecute(null).ExecutionStatus == ExecutionStatus.Failed, "tryExecute failed");

        // withFlowId + withClock
        var fc = new FakeClock(1000, 5);
        var fc2 = Flow.Create().WithFlowId("my-flow").WithClock(fc)
            .WhenExpr(Portable.PConst(true), Portable.PConst("v"), "p1").Compile();
        var pf2 = Trust.ToIR(fc2);
        Check(pf2.FlowId == "my-flow", "flow_id in IR");
        Check(!string.IsNullOrEmpty(pf2.ContractVersion), "contract_version in IR");
        Check(ReferenceEquals(fc2.ClockRef, fc), "clock injected");

        // diagnostic hook
        var dh = Flow.Create().WithTrace(e => new Dictionary<string, object?> { ["tag"] = e.Type })
            .When(CondTrue(), Act("v"), "r1").Compile();
        var dho = dh.TryExecute(null);
        Check(dho.Trace is { Events.Count: > 0 }, "trace events");
        Check(dho.Trace!.Events[0].Diagnostics is not null, "diagnostics present");
        Check(dho.Trace.Events[0].ContractVersion is not null, "event contract_version");

        // PExpr builders + ExprToNode round trip
        var e = Portable.PAnd(
            Portable.PGt(Portable.PField("total"), Portable.PConst(100)),
            Portable.PNot(Portable.PIsNull(Portable.PField("sku"))));
        var ed = Portable.ExprToNode(e);
        var back = Portable.ExprFromNodePublic(ed);
        Check(back.Op == "and", "pexpr round trip");
        Check(Portable.Ops.Contains("field"), "Ops exported");
        var nv = Portable.EvalExpr(Portable.PNotIn(Portable.PField("s"), new object?[] { "a", "b" }),
            new Dictionary<string, object?> { ["s"] = "c" });
        Check(nv is true, "PNotIn eval");

        // PortableFlow JSON round trip
        var pj = Flow.Create().WithFlowId("f")
            .WhenExpr(Portable.PEq(Portable.PField("x"), Portable.PConst(1)), Portable.PConst("one"), "r1")
            .Compile();
        var js = Portable.PortableFlowToJSON(Trust.ToIR(pj));
        var pback = Portable.PortableFlowFromJSON(js);
        Check(pback.FlowId == "f" && pback.Rules.Count == 1, "portable JSON round trip");
        var irjs = Trust.ToIRJSON(pj);
        Check(Portable.PortableFlowFromJSON(irjs).Rules.Count == 1, "toIRJSON round trip");

        // MergeContract
        var inner = Flow.Create()
            .When(CondFalse(), Act("inner"), "i1")
            .DefaultIfNoMatch("ifb").Compile();
        var outer = Flow.Create()
            .When(CondTrue(), Act("outer"), "o1")
            .DefaultIfNoMatch("ofb");
        Advanced.MergeContract(outer, inner);
        Check("outer".Equals(outer.Compile().TryExecute(null).Value), "MergeContract");

        // SimulateWithClock + shadow clock
        var sc2 = new FakeClock(100, 0);
        var sim = Flow.Create().When(CondTrue(), Act("v"), "r1").Compile();
        Check("v".Equals(sim.SimulateWithClock(null, sc2).Value), "SimulateWithClock");
        var cand2 = Flow.Create().When(CondTrue(), Act("w"), "r1").Compile();
        var sr = Trust.Shadow(sim, cand2, new List<object?> { null }, sc2);
        Check(sr.Differences == 1 && sr.Entries[0].DifferingFields[0] == "value", "shadow clock");

        // FlowContext
        var ctx = new FlowContext(new Dictionary<string, object?> { ["a"] = 1 }, sc2);
        Check(ctx.Input is not null && ReferenceEquals(ctx.Clock, sc2) && ctx.State.Count == 0, "FlowContext");

        // replay uses recorded clock
        var rc = new FakeClock(5000, 3);
        var rc2 = Flow.Create().WithClock(rc).When(CondTrue(), Act("v"), "r1").Compile();
        var recReplay = Trust.Record(rc2, null, rc);
        var rr = Trust.Replay(recReplay, rc2, Trust.ReplayMode.Decision, null, null, false);
        Check(rr.Equivalent == true, "replay equivalent");

        Console.WriteLine($"RESULT: {_passed} passed, {_failed} failed");
        return _failed > 0 ? 1 : 0;
    }
}

internal static class JsonNodeExt
{
    public static T Also<T>(this T obj, Action<T> f) { f(obj); return obj; }
}
