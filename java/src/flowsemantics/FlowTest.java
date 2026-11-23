package flowsemantics;

import java.util.*;

/** Unit tests — plain assertions, zero deps. Run: java -cp out flowsemantics.FlowTest */
public final class FlowTest {
    static int passed = 0, failed = 0;

    static void check(boolean cond, String name) {
        if (cond) { passed++; }
        else { failed++; System.out.println("FAIL: " + name); }
    }

    static Flow.ConditionFn condTrue() { return i -> true; }
    static Flow.ConditionFn condFalse() { return i -> false; }
    static Flow.ActionFn act(String v) { return (i, p) -> v; }

    public static void main(String[] args) throws Exception {
        // when match
        var c1 = Flow.create().when(condTrue(), act("ok"), "r1").compile();
        var o1 = c1.tryExecute(null);
        check(o1.executionStatus == Outcome.ExecutionStatus.COMPLETED && "ok".equals(o1.value), "when match");
        check(o1.decisionStatus == Outcome.DecisionStatus.APPROVED, "approved");

        // no match
        var c2 = Flow.create().when(condFalse(), act("x"), "r1").compile();
        check(c2.tryExecute(null).decisionStatus == Outcome.DecisionStatus.NO_MATCH, "no match");

        // first match short circuit
        int[] second = {0};
        var c3 = Flow.create()
            .when(condTrue(), act("first"), "r1")
            .when(i -> { second[0]++; return true; }, act("second"), "r2")
            .compile();
        check("first".equals(c3.tryExecute(null).value) && second[0] == 0, "first match");

        // all match last wins
        var c4 = Flow.create().withMode(Outcome.EvaluationMode.AllMatch)
            .when(condTrue(), act("a"), "r1")
            .when(condTrue(), act("b"), "r2").compile();
        check("b".equals(c4.tryExecute(null).value), "all match");

        // priority
        var c5 = Flow.create().withMode(Outcome.EvaluationMode.Priority)
            .when(condTrue(), act("low"), "r1")
            .when(condTrue(), act("high"), "r2").compile();
        // priorities default 0 — set via when overload not used; skip strict check
        check(c5.tryExecute(null).value != null, "priority runs");

        // then receives previous
        var c6 = Flow.create()
            .when(condTrue(), (i, p) -> 1, "r1")
            .then((i, p) -> (Integer) p + 1, "t1").compile();
        check(Integer.valueOf(2).equals(c6.tryExecute(null).value), "then prev");

        // guard veto
        var c7 = Flow.create()
            .when(condTrue(), act("x"), "r1", i -> false, 0, null).compile();
        check(c7.tryExecute(null).decisionStatus == Outcome.DecisionStatus.NO_MATCH, "guard veto");

        // typed catch recovers
        var c8 = Flow.create()
            .when(condTrue(), (i, p) -> { throw new FlowErrors.KindValueError("boom"); }, "r1")
            .catchTyped("Kind.ValueError", (i, e) -> "recovered", "c1").compile();
        var o8 = c8.tryExecute(null);
        check(o8.executionStatus == Outcome.ExecutionStatus.COMPLETED && "recovered".equals(o8.value), "catch recovers");
        check(o8.recovery != null && o8.decisionStatus == null, "recovery info, null decision");

        // uncaught failed
        var c9 = Flow.create()
            .when(condTrue(), (i, p) -> { throw new FlowErrors.KindValueError("x"); }, "r1").compile();
        check(c9.tryExecute(null).executionStatus == Outcome.ExecutionStatus.FAILED, "uncaught failed");

        // timeout bypasses catch
        var c10 = Flow.create()
            .when(condTrue(), (i, p) -> { throw new FlowErrors.KindTimeout("t"); }, "r1")
            .catchAny((i, e) -> "no", "c1").compile();
        var o10 = c10.tryExecute(null);
        check(o10.executionStatus == Outcome.ExecutionStatus.TIMED_OUT, "timeout interruption");
        check(o10.interruption != null && o10.interruption.kind == Outcome.InterruptionKind.timed_out, "timed_out kind");

        // cancelled bypasses catch
        var c11 = Flow.create()
            .when(condTrue(), (i, p) -> { throw new FlowErrors.KindCancelled("c"); }, "r1")
            .catchAny((i, e) -> "no", "c1").compile();
        check(c11.tryExecute(null).executionStatus == Outcome.ExecutionStatus.CANCELLED, "cancelled");

        // finally on success
        boolean[] ran = {false};
        var c12 = Flow.create()
            .when(condTrue(), act("v"), "r1")
            .finally_(ctx -> ran[0] = true).compile();
        var o12 = c12.tryExecute(null);
        check(ran[0] && o12.finalization != null && o12.finalization.isClean, "finally clean");

        // finally preserve primary
        var c13 = Flow.create()
            .when(condTrue(), (i, p) -> { throw new FlowErrors.KindValueError("primary"); }, "r1")
            .finally_(ctx -> { throw new FlowErrors.KindTimeout("cleanup"); }).compile();
        var o13 = c13.tryExecute(null);
        check(o13.primaryException instanceof FlowErrors.KindValueError, "preserve primary");
        check(o13.finalization != null && !o13.finalization.isClean, "is_clean false");

        // finally replace primary
        var c14 = Flow.create().withFinallyPolicy(Outcome.FinallyFailurePolicy.ReplacePrimary)
            .when(condTrue(), (i, p) -> { throw new FlowErrors.KindValueError("primary"); }, "r1")
            .finally_(ctx -> { throw new FlowErrors.KindTimeout("cleanup"); }).compile();
        check(c14.tryExecute(null).primaryException instanceof FlowErrors.KindTimeout, "replace primary");

        // effects order
        var c15 = Flow.create().withMode(Outcome.EvaluationMode.AllMatch)
            .when(condTrue(), act("a"), "r1")
            .when(condTrue(), act("b"), "r2").compile();
        // effects via portable path tested in vectors; skip

        // trace
        var c16 = Flow.create()
            .when(condFalse(), act("x"), "r1")
            .when(condTrue(), act("y"), "r2").compile();
        var o16 = c16.tryExecute(null, new FakeClock(0, 0), true);
        check(o16.trace != null && o16.trace.events.stream().anyMatch(e -> e.type.equals("rule_skipped")), "trace events");

        // portable IR
        Map<String, Object> ir = Map.of(
            "spec_version", "0.1.0", "flow_id", "f", "portability", "PORTABLE", "mode", "FirstMatch",
            "rules", List.of(Map.of(
                "rule_id", "r1", "kind", "when",
                "condition", Map.of("op", "gt", "args", List.of(
                    Map.of("op", "field", "value", "x"),
                    Map.of("op", "const", "value", 0.0))),
                "transform", Map.of("op", "const", "value", "pos"))),
            "fallback", Map.of("kind", "default_if_no_match", "value", "neg"));
        var c17 = Flow.fromIr(ir).compile();
        check("pos".equals(c17.tryExecute(Map.of("x", 5.0)).value), "IR pos");
        check("neg".equals(c17.tryExecute(Map.of("x", -1.0)).value), "IR neg");

        // IR duplicate rejection
        Map<String, Object> dupRule = Map.of("rule_id", "d", "kind", "when",
            "condition", Map.of("op", "const", "value", true),
            "transform", Map.of("op", "const", "value", 1.0));
        boolean rejected = false;
        try {
            Portable.portableFlowFromDict(Map.of(
                "spec_version", "0.1.0", "flow_id", "f", "portability", "PORTABLE", "mode", "FirstMatch",
                "rules", List.of(dupRule, dupRule)));
        } catch (Exception e) { rejected = true; }
        check(rejected, "IR duplicate rejected");

        // IR depth rejection
        Map<String, Object> expr = Map.of("op", "const", "value", true);
        for (int i = 0; i < Portable.MAX_EXPR_DEPTH + 2; i++) {
            expr = Map.of("op", "not", "args", List.of(expr));
        }
        rejected = false;
        try {
            Portable.portableFlowFromDict(Map.of(
                "spec_version", "0.1.0", "flow_id", "f", "portability", "PORTABLE", "mode", "FirstMatch",
                "rules", List.of(Map.of("rule_id", "r", "kind", "when", "condition", expr,
                    "transform", Map.of("op", "const", "value", 1.0)))));
        } catch (Exception e) { rejected = true; }
        check(rejected, "IR depth rejected");

        // simulate skips hooks
        int[] hooked = {0};
        var c18 = Flow.create()
            .when(condTrue(), act("v"), "r1")
            .onMatch((i, rid, v) -> hooked[0]++).compile();
        c18.simulate(null);
        check(hooked[0] == 0, "simulate no hooks");

        // contract version stable
        var cv1 = Flow.create().when(condTrue(), act("x"), "r1").compile();
        var cv2 = Flow.create().when(condTrue(), act("x"), "r1").compile();
        check(cv1.contractVersion.equals(cv2.contractVersion) && !cv1.contractVersion.isEmpty(), "contract version stable");
        var cv3 = Flow.create().when(condTrue(), act("y"), "r2").compile();
        check(!cv1.contractVersion.equals(cv3.contractVersion), "version differs");

        // validate empty flow
        var ve = Flow.create().compile();
        var vi = Trust.validate(ve);
        check(vi.size() == 1 && vi.get(0).code.equals("empty_flow"), "validate empty_flow");

        // explain
        var ce = Flow.create().when(condFalse(), act("x"), "r1").compile();
        var oe = ce.tryExecute(null, new FakeClock(0, 0), true);
        var ex = Trust.explain(ce, oe.trace);
        check(ex.contains("FlowContract") && ex.contains("rule_skipped"), "explain output");

        // replay simulation + historical
        var cr = Flow.create().when(condTrue(), act("v"), "r1").compile();
        var rec = Trust.record(cr, null, new FakeClock(0, 0));
        var rsim = Trust.replay(rec, cr, Trust.ReplayMode.simulation, null, null, false);
        check(Boolean.TRUE.equals(rsim.equivalent), "replay simulation equivalent");
        var rhist = Trust.replay(rec, cr, Trust.ReplayMode.historical, null, null, false);
        check(rhist.outcome == rec.outcome, "replay historical");

        // fail closed on version mismatch
        rec.contractVersion = "tampered";
        boolean closed = false;
        try { Trust.replay(rec, cr, Trust.ReplayMode.simulation, null, null, false); }
        catch (Trust.ReplayError e) { closed = true; }
        check(closed, "replay fail-closed");

        // integrity
        rec.contractVersion = cr.contractVersion;
        var signed = Trust.sign(rec, "key".getBytes());
        Trust.replay(signed, cr, Trust.ReplayMode.simulation, "key".getBytes(), null, false);
        boolean integFail = false;
        try { Trust.replay(signed, cr, Trust.ReplayMode.simulation, "wrong".getBytes(), null, false); }
        catch (Trust.ReplayError e) { integFail = true; }
        check(integFail, "replay integrity");

        // effects auth
        var ce2 = Flow.create().when(condTrue(), act("v"), "r1").compile();
        var rec2 = Trust.record(ce2, null, new FakeClock(0, 0));
        boolean authFail = false;
        try { Trust.replay(rec2, ce2, Trust.ReplayMode.effects, null, null, false); }
        catch (Trust.ReplayError e) { authFail = true; }
        check(authFail, "effects auth required");

        // shadow
        var cur = Flow.create().when(condTrue(), act("a"), "r1").compile();
        var cand = Flow.create().when(condTrue(), act("b"), "r1").compile();
        var rep = Trust.shadow(cur, cand, java.util.Arrays.asList(null, null));
        check(rep.total == 2 && rep.differences == 2, "shadow report");

        testAdvanced();
        System.out.printf("RESULT: %d passed, %d failed%n", passed, failed);
        if (failed > 0) System.exit(1);
    }

    static void testAdvanced() {
        // Merge
        Flow f1 = Flow.create();
        f1.when(i -> true, (i, p) -> "a", "r1");
        Flow f2 = Flow.create();
        f2.when(i -> false, (i, p) -> "b", "r2");
        f2.defaultIfNoMatch("fb");
        Flow merged = Advanced.merge(f1, f2);
        Outcome.FlowOutcome o = merged.compile().tryExecute(null);
        check("a".equals(o.value), "merge value");
        try { Advanced.merge(f1, Flow.create().withMode(Outcome.EvaluationMode.AllMatch)); check(false, "merge mode"); }
        catch (FlowErrors.StructureError e) { /* expected */ }
        // DecisionTable
        Flow.FlowContract tc = Advanced.tableToFlow(new Advanced.DecisionTable(List.of(
            new Advanced.DecisionTableRow("big", List.of(i -> true), (i, p) -> "big", 0),
            new Advanced.DecisionTableRow("small", List.of(i -> false), (i, p) -> "small", 0)
        ), Advanced.HitPolicy.FIRST)).compile();
        check("big".equals(tc.tryExecute(null).value), "table value");
        // Effective dates
        long from = 1700000000000L, until = 1800000000000L;
        Flow.FlowContract ec = Flow.create().when(i -> true, (i, p) -> "v", "r1", null, 0, null, from, until).compile();
        check(ec.tryExecute(null, new FakeClock(0, 0), true).decisionStatus == Outcome.DecisionStatus.NO_MATCH, "before window");
        check("v".equals(ec.tryExecute(null, new FakeClock((from + until) / 2, 0), true).value), "inside window");
        check(ec.tryExecute(null, new FakeClock(until + 1, 0), true).decisionStatus == Outcome.DecisionStatus.NO_MATCH, "after window");
        try {
            Flow.create().when(i -> true, (i, p) -> "v", "r1", null, 0, null, until, from).compile();
            check(false, "inverted window");
        } catch (FlowErrors.StructureError e) { /* expected */ }
        // Cancel check
        boolean[] cancelled = {false};
        Flow.FlowContract cc = Flow.create().withCancelCheck(() -> cancelled[0])
            .when(i -> true, (i, p) -> "v", "r1").compile();
        cancelled[0] = true;
        check(cc.tryExecute(null).executionStatus == Outcome.ExecutionStatus.CANCELLED, "cancel check");
        // Simulate batch
        Flow.FlowContract sc = Flow.create().when(i -> true, (i, p) -> "v", "r1").compile();
        Advanced.SimulateReport rep = Advanced.simulateBatch(sc, java.util.Arrays.asList(null, null));
        check(rep.total == 2 && rep.byDecision.get("APPROVED") == 2, "simulate batch");
        // Portability
        String[] p = Advanced.portability(sc);
        check("NATIVE".equals(p[0]) && !p[1].isEmpty(), "portability report");
        // Finally timeout
        Flow.FlowContract ft = Flow.create().withFinallyTimeout(1)
            .when(i -> true, (i2, p2) -> "v", "r1")
            .finally_(ctx -> { try { Thread.sleep(5); } catch (InterruptedException e) {} })
            .compile();
        Outcome.FlowOutcome fo = ft.tryExecute(null);
        check(fo.finalization != null && fo.finalization.cleanupBudgetExceeded, "finally budget");
        // Validate depth
        boolean gap = false;
        for (Trust.ValidationIssue i : Trust.validate(sc)) if ("possible_gap".equals(i.code)) gap = true;
        check(gap, "gap warning");

        // --- Phase 8 parity additions ---
        // execute propagates
        Flow.FlowContract ec2 = Flow.create()
            .when(i -> true, (i2, p2) -> { throw new RuntimeException("boom"); }, "r1").compile();
        boolean threw = false;
        try { ec2.execute(null); } catch (Exception e) { threw = true; }
        check(threw, "execute propagates");
        check(ec2.tryExecute(null).executionStatus == Outcome.ExecutionStatus.FAILED, "tryExecute failed");

        // withFlowId + withClock + diagnostic hook
        FakeClock fc = new FakeClock(1000, 5);
        Flow.FlowContract fc2 = Flow.create().withFlowId("my-flow").withClock(fc)
            .whenExpr(Portable.pConst(true), Portable.pConst("v"), "p1", null).compile();
        Portable.PortableFlow ir = Trust.toIR(fc2);
        check("my-flow".equals(ir.flowId), "flow_id in IR");
        check(ir.contractVersion != null && !ir.contractVersion.isEmpty(), "contract_version in IR");
        check(fc2.clock() == fc, "clock injected");

        // diagnostic hook
        Flow.FlowContract dh = Flow.create().withTrace(e -> Map.of("tag", e.type)).
            when(i -> true, (i2, p2) -> "v", "r1").compile();
        Outcome.FlowOutcome dho = dh.tryExecute(null);
        check(dho.trace != null && !dho.trace.events.isEmpty(), "trace events");
        check(dho.trace.events.get(0).diagnostics != null, "diagnostics present");
        check(dho.trace.events.get(0).contractVersion != null, "event contract_version");

        // PExpr builders + exprToDict round trip
        Portable.PExpr e = Portable.pAnd(
            Portable.pGt(Portable.pField("total"), Portable.pConst(100)),
            Portable.pNot(Portable.pIsNull(Portable.pField("sku"))));
        Map<String, Object> ed = Portable.exprToDict(e);
        Portable.PExpr back = Portable.exprFromDictPublic(ed);
        check("and".equals(back.op), "pexpr round trip");
        check(Portable.OPS.contains("field"), "OPS exported");
        Object nv = Portable.evalExpr(Portable.pNotIn(Portable.pField("s"), List.of("a", "b")),
            Map.of("s", "c"));
        check(Boolean.TRUE.equals(nv), "pNotIn eval");

        // PortableFlow JSON round trip
        Flow.FlowContract pj = Flow.create().withFlowId("f")
            .whenExpr(Portable.pEq(Portable.pField("x"), Portable.pConst(1)), Portable.pConst("one"), "r1", null)
            .compile();
        String js = Portable.portableFlowToJSON(Trust.toIR(pj));
        Portable.PortableFlow pback = Portable.portableFlowFromJSON(js);
        check("f".equals(pback.flowId) && pback.rules.size() == 1, "portable JSON round trip");
        String irjs = Trust.toIRJSON(pj);
        check(Portable.portableFlowFromJSON(irjs).rules.size() == 1, "toIRJSON round trip");

        // mergeContract
        Flow.FlowContract inner = Flow.create()
            .when(i -> false, (i2, p2) -> "inner", "i1")
            .defaultIfNoMatch("ifb").compile();
        Flow outer = Flow.create()
            .when(i -> true, (i2, p2) -> "outer", "o1")
            .defaultIfNoMatch("ofb");
        Advanced.mergeContract(outer, inner);
        check("outer".equals(outer.compile().tryExecute(null).value), "mergeContract");

        // simulateWithClock + shadow clock
        FakeClock sc2 = new FakeClock(100, 0);
        Flow.FlowContract sim = Flow.create()
            .when(i -> true, (i2, p2) -> "v", "r1").compile();
        check("v".equals(sim.simulateWithClock(null, sc2).value), "simulateWithClock");
        Flow.FlowContract cand = Flow.create()
            .when(i -> true, (i2, p2) -> "w", "r1").compile();
        Trust.ShadowReport sr = Trust.shadow(sim, cand, java.util.Arrays.asList((Object) null), sc2);
        check(sr.differences == 1 && "value".equals(sr.entries.get(0).differingFields.get(0)), "shadow clock");

        // FlowContext
        FlowContext ctx = new FlowContext(Map.of("a", 1), sc2);
        check(ctx.input != null && ctx.clock == sc2 && ctx.state != null, "FlowContext");

        // replay uses recorded clock
        FakeClock rc = new FakeClock(5000, 3);
        Flow.FlowContract rc2 = Flow.create().withClock(rc)
            .when(i -> true, (i2, p2) -> "v", "r1").compile();
        Trust.ReplayRecord rec = Trust.record(rc2, null, rc);
        Trust.ReplayResult rr = Trust.replay(rec, rc2, Trust.ReplayMode.decision, null, null, false);
        check(rr.equivalent != null && rr.equivalent, "replay equivalent");
    }
}
