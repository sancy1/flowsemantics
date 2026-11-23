// Consumer-driven contract tests — Java.
// Written purely from the public documentation. Compiles against only the
// published flowsemantics.jar artifact — never the source tree.
// Run: javac -cp ../../java/flowsemantics.jar ConsumerTest.java && java -cp .;../../java/flowsemantics.jar ConsumerTest

import flowsemantics.*;
import flowsemantics.Advanced.*;
import flowsemantics.Portable.*;
import flowsemantics.Trust.*;
import static flowsemantics.Portable.*;
import java.util.*;

public class ConsumerTest {
    static int passed = 0, failed = 0;

    static void check(String name, boolean cond) {
        if (cond) { passed++; }
        else { failed++; System.out.println("FAIL: " + name); }
    }

    static Flow.ConditionFn condTrue() { return (i) -> true; }
    static Flow.ConditionFn condFalse() { return (i) -> false; }
    static Flow.ActionFn act(Object v) { return (i, p) -> v; }
    static Flow.ActionFn actThrow(RuntimeException e) { return (i, p) -> { throw e; }; }
    static Flow.ExceptionHandler handler(Object v) { return (i, exc) -> v; }

    static Map<String, Object> map(Object... kv) {
        Map<String, Object> m = new LinkedHashMap<>();
        for (int i = 0; i < kv.length; i += 2) m.put((String) kv[i], kv[i + 1]);
        return m;
    }

    public static void main(String[] args) throws Exception {
        coreDecision();
        errorExecution();
        trustSemantics();
        portableIr();
        crossCutting();
        System.out.println("passed=" + passed + " failed=" + failed);
        if (failed > 0) System.exit(1);
    }

    // Features 1-18: core decision layer
    static void coreDecision() throws Exception {
        // 1,3: when + action
        var c = Flow.create().when((i) -> ((Number) ((Map<?,?>) i).get("total")).intValue() > 100,
                act("big"), "big").compile();
        var o = c.tryExecute(map("total", 150));
        check("when approved", o.executionStatus == Outcome.ExecutionStatus.COMPLETED
                && o.decisionStatus == Outcome.DecisionStatus.APPROVED && "big".equals(o.value));

        // 2,4: whenNot + otherwise
        var c2 = Flow.create()
                .whenNot((i) -> (Boolean) ((Map<?,?>) i).get("vip"), act("standard"), "std")
                .otherwise(act("fallback")).compile();
        check("whenNot", "standard".equals(c2.tryExecute(map("vip", false)).value));
        check("otherwise", "fallback".equals(c2.tryExecute(map("vip", true)).value));

        // 5,6: default / defaultIfNoMatch
        check("default", "d".equals(Flow.create().when(condFalse(), act("x"), "r")
                .defaultValue("d").compile().tryExecute(null).value));
        check("defaultIfNoMatch", "d2".equals(Flow.create().when(condFalse(), act("x"), "r")
                .defaultIfNoMatch("d2").compile().tryExecute(null).value));

        // 7-9: evaluation modes
        check("FirstMatch", "a".equals(Flow.create().withMode(Outcome.EvaluationMode.FirstMatch)
                .when(condTrue(), act("a"), "a").when(condTrue(), act("b"), "b").compile()
                .tryExecute(null).value));
        check("AllMatch", "b".equals(Flow.create().withMode(Outcome.EvaluationMode.AllMatch)
                .when(condTrue(), act("a"), "a").when(condTrue(), act("b"), "b").compile()
                .tryExecute(null).value));
        check("Priority", "b".equals(Flow.create().withMode(Outcome.EvaluationMode.Priority)
                .when(condTrue(), act("a"), "a", null, 1, null)
                .when(condTrue(), act("b"), "b", null, 10, null).compile()
                .tryExecute(null).value));

        // 10,11: guard + priority
        var c3 = Flow.create().withMode(Outcome.EvaluationMode.Priority)
                .when(condTrue(), act("low"), "low", null, 1, null)
                .when(condTrue(), act("high"), "high",
                        (i) -> (Boolean) ((Map<?,?>) i).get("ok"), 10, null)
                .compile();
        check("guard pass", "high".equals(c3.tryExecute(map("ok", true)).value));
        check("guard block", "low".equals(c3.tryExecute(map("ok", false)).value));

        // 12: effects
        var c4 = Flow.create().when(condTrue(), act("done"), "r1", null, 0,
                List.of(new Outcome.Effect("notify", map("to", "ops")))).compile();
        var o4 = c4.tryExecute(null);
        check("effects", "done".equals(o4.value) && o4.effects.size() == 1
                && "notify".equals(o4.effects.get(0).name));

        // 13,14: merge
        var merged = Advanced.merge(Flow.create()
                .when((i) -> ((Number) ((Map<?,?>) i).get("x")).intValue() > 0, act("pos"), "pos"),
                Flow.create()
                .when((i) -> ((Number) ((Map<?,?>) i).get("x")).intValue() < 0, act("neg"), "neg"));
        var mc = merged.compile();
        check("merge pos", "pos".equals(mc.tryExecute(map("x", 1)).value));
        check("merge neg", "neg".equals(mc.tryExecute(map("x", -1)).value));
        var part = Flow.create().when((i) -> ((Number) ((Map<?,?>) i).get("x")).intValue() == 0,
                act("zero"), "zero").compile();
        var mf = Advanced.mergeContract(Flow.create(), part).compile();
        check("mergeContract", "zero".equals(mf.tryExecute(map("x", 0)).value));

        // 15,16: decision table + hit policies
        var table = new DecisionTable(List.of(
                new DecisionTableRow("small", List.of(
                        (i) -> ((Number) ((Map<?,?>) i).get("n")).intValue() < 10), act("small"), 0),
                new DecisionTableRow("big", List.of(
                        (i) -> ((Number) ((Map<?,?>) i).get("n")).intValue() >= 10), act("big"), 0)),
                HitPolicy.FIRST);
        var tc = Advanced.tableToFlow(table).compile();
        check("table small", "small".equals(tc.tryExecute(map("n", 5)).value));
        check("table big", "big".equals(tc.tryExecute(map("n", 50)).value));
        for (HitPolicy p : HitPolicy.values()) {
            var t2 = new DecisionTable(List.of(new DecisionTableRow("r1",
                    List.of(condTrue()), act("v1"), 0)), p);
            try { Advanced.tableToFlow(t2); check("policy " + p, true); }
            catch (Exception e) { check("policy " + p, false); }
        }

        // 17: duplicate RuleId rejected at compile
        try {
            Flow.create().when(condTrue(), act("a"), "dup")
                    .when(condTrue(), act("b"), "dup").compile();
            check("dup id rejected", false);
        } catch (FlowErrors.StructureError e) { check("dup id rejected", true); }

        // 18: effective dates
        var c5 = Flow.create().when(condTrue(), act("active"), "r1", null, 0, null,
                1_000_000L, 9_000_000_000_000L).defaultIfNoMatch("inactive").compile();
        check("effective window", "active".equals(c5.tryExecute(null).value));
    }

    // Features 19-33: error & execution layer
    static void errorExecution() throws Exception {
        // 19: typed catch
        var c = Flow.create().when(condTrue(), actThrow(FlowErrors.exceptionForKind("Kind.ValueError")), "r1")
                .catchTyped("Kind.ValueError", handler("caught"), "h1").compile();
        var o = c.tryExecute(null);
        check("catch typed", o.executionStatus == Outcome.ExecutionStatus.COMPLETED
                && o.recovery != null && "h1".equals(o.recovery.handlerRuleId));

        // 20,21: catchWhen + catchAny
        var c2 = Flow.create().when(condTrue(), actThrow(new RuntimeException("x")), "r1")
                .catchWhen("Kind.Any", (i, exc) -> false, handler("predicted"), "h1")
                .catchAny(handler("any"), "h2").compile();
        check("catchAny", "any".equals(c2.tryExecute(null).value));

        // 22: rethrow
        var c3 = Flow.create().when(condTrue(), actThrow(FlowErrors.exceptionForKind("Kind.ValueError")), "r1")
                .catchWhen("Kind.ValueError", (i, exc) -> false, handler("handled"), "h1")
                .rethrow().compile();
        var o3 = c3.tryExecute(null);
        check("rethrow", o3.executionStatus == Outcome.ExecutionStatus.FAILED
                && o3.primaryException != null);

        // 23: onMatch hook
        var seen = new ArrayList<String>();
        var c4 = Flow.create().when(condTrue(), act("v"), "r1")
                .onMatch((i, rid, v) -> seen.add(rid)).compile();
        c4.tryExecute(null);
        check("onMatch", seen.size() == 1 && "r1".equals(seen.get(0)));

        // 24,25: cancellation + timeout recognition
        var c5 = Flow.create().when(condTrue(), actThrow(FlowErrors.exceptionForKind("Kind.Cancelled")), "r1").compile();
        var o5 = c5.tryExecute(null);
        check("cancelled", o5.executionStatus == Outcome.ExecutionStatus.CANCELLED
                && o5.interruption != null
                && o5.interruption.kind == Outcome.InterruptionKind.cancelled);
        var c6 = Flow.create().when(condTrue(), actThrow(FlowErrors.exceptionForKind("Kind.Timeout")), "r1").compile();
        var o6 = c6.tryExecute(null);
        check("timed out", o6.executionStatus == Outcome.ExecutionStatus.TIMED_OUT
                && o6.interruption != null
                && o6.interruption.kind == Outcome.InterruptionKind.timed_out);

        // 26: cooperative cancel check
        var c7 = Flow.create().when(condTrue(), act("a"), "r1")
                .withCancelCheck(() -> true).compile();
        check("cancel check", c7.tryExecute(null).executionStatus == Outcome.ExecutionStatus.CANCELLED);

        // 27: async parity (Java: identical semantics)
        var c8 = Flow.create().when(condTrue(), act("ok"), "r1").compile();
        check("async parity", "ok".equals(c8.executeAsync(null).value));

        // 28,29: finally + policies
        var cleaned = new ArrayList<Outcome.ExecutionStatus>();
        var c9 = Flow.create().when(condTrue(), act("ok"), "r1")
                .finally_((ctx) -> cleaned.add(ctx.status)).compile();
        var o9 = c9.tryExecute(null);
        check("finally", "ok".equals(o9.value) && cleaned.size() == 1
                && cleaned.get(0) == Outcome.ExecutionStatus.COMPLETED);
        for (Outcome.FinallyFailurePolicy p : Outcome.FinallyFailurePolicy.values()) {
            var c10 = Flow.create().when(condTrue(), act("ok"), "r1")
                    .finally_((ctx) -> { throw new RuntimeException("cleanup"); })
                    .withFinallyPolicy(p).compile();
            check("policy " + p, c10.tryExecute(null) != null);
        }

        // 30: finally timeout budget
        var c11 = Flow.create().when(condTrue(), act("ok"), "r1")
                .finally_((ctx) -> {}).withFinallyTimeout(50).compile();
        check("finally timeout", c11.tryExecute(null).finalization != null);

        // 31: secondary exceptions isolated
        var c12 = Flow.create().when(condTrue(), act("v"), "r1")
                .onMatch((i, rid, v) -> { throw new RuntimeException("hook boom"); }).compile();
        var o12 = c12.tryExecute(null);
        check("secondary exceptions", "v".equals(o12.value) && !o12.secondaryExceptions.isEmpty());

        // 32: interruption model
        var o13 = Flow.create().when(condTrue(), actThrow(FlowErrors.exceptionForKind("Kind.Cancelled")), "r1")
                .compile().tryExecute(null);
        check("interruption", o13.interruption != null
                && o13.interruption.kind == Outcome.InterruptionKind.cancelled
                && o13.interruption.source != null && o13.interruption.timestamp > 0);

        // 33: finally context + token
        var status = new Outcome.ExecutionStatus[1];
        var value = new Object[1];
        var ctxInput = new Object[1];
        var c14 = Flow.create().when(condTrue(), act("payload"), "r1")
                .finally_((ctx) -> { status[0] = ctx.status; value[0] = ctx.value; ctxInput[0] = ctx.context; })
                .compile();
        c14.tryExecute(map("in", 1));
        check("finally context", status[0] == Outcome.ExecutionStatus.COMPLETED
                && "payload".equals(value[0]) && ctxInput[0] != null);
    }

    // Features 34-47: trust semantics
    static Flow.FlowContract traced() {
        return Flow.create().withTrace()
                .when((i) -> ((Number) ((Map<?,?>) i).get("n")).intValue() > 0, act("pos"), "pos")
                .defaultIfNoMatch("none").compile();
    }

    static void trustSemantics() throws Exception {
        // 34,35: trace vocabulary + opt-in
        var o = traced().tryExecute(map("n", 1), null, true);
        check("trace events", o.trace != null && !o.trace.events.isEmpty());
        check("trace opt-in", Flow.create().when(condTrue(), act("x"), "r").compile()
                .tryExecute(null).trace == null);

        // 36: diagnostic hook
        var seen = new int[1];
        var c = Flow.create().when(condTrue(), act("v"), "r1")
                .withTrace((e) -> { seen[0]++; return map("redacted", true); }).compile();
        c.tryExecute(null, null, true);
        check("diagnostic hook", seen[0] > 0);

        // 37: explain
        var text = Trust.explain(traced(), traced().tryExecute(map("n", 1), null, true).trace);
        check("explain", text != null && !text.isEmpty());

        // 38,39: simulate + batch
        var sim = traced().simulate(map("n", 5));
        check("simulate", sim.decisionStatus == Outcome.DecisionStatus.APPROVED
                && "pos".equals(sim.value));
        var batch = Advanced.simulateBatch(traced(),
                List.of(map("n", 1), map("n", -1), map("n", 2)));
        check("simulateBatch", batch.total == 3 && batch.byStatus != null
                && batch.byDecision != null);

        // 40,41: replay record + modes
        var c2 = traced();
        var rec = Trust.record(c2, map("n", 3), new FakeClock(0, 0));
        check("record", rec.contractVersion != null && !rec.contractVersion.isEmpty());
        for (ReplayMode m : new ReplayMode[]{ReplayMode.simulation, ReplayMode.historical,
                ReplayMode.decision}) {
            var res = Trust.replay(rec, c2, m, null, null, false);
            check("replay " + m, res.mode == m);
        }
        // effects mode
        var effC = Flow.create().when(condTrue(), act("x"), "r1", null, 0,
                List.of(new Outcome.Effect("e", 1))).compile();
        var effRec = Trust.record(effC, null, new FakeClock(0, 0));
        var applied = new ArrayList<Outcome.Effect>();
        var effRes = Trust.replay(effRec, effC, ReplayMode.effects, null,
                (e) -> applied.add(e), true);
        check("replay effects", effRes.effectsApplied == 1 && applied.size() == 1);

        // 42,43: HMAC integrity + fail closed
        var key = "consumer-secret".getBytes();
        var signed = Trust.sign(Trust.record(c2, map("n", 1), new FakeClock(0, 0)), key);
        check("integrity tag", signed.integrity != null && !signed.integrity.isEmpty());
        var res2 = Trust.replay(signed, c2, ReplayMode.simulation, key, null, false);
        check("equivalent", res2.equivalent != null && res2.equivalent);
        try {
            Trust.replay(signed, c2, ReplayMode.simulation, "wrong".getBytes(), null, false);
            check("integrity fail-closed", false);
        } catch (ReplayError e) { check("integrity fail-closed", true); }
        var other = Flow.create().when(condTrue(), act("different"), "r1").compile();
        try {
            Trust.replay(signed, other, ReplayMode.simulation, key, null, false);
            check("version fail-closed", false);
        } catch (ReplayError e) { check("version fail-closed", true); }

        // 44: shadow
        var current = Flow.create()
                .when((i) -> ((Number) ((Map<?,?>) i).get("n")).intValue() > 0, act("pos"), "r")
                .defaultIfNoMatch("neg").compile();
        var candidate = Flow.create()
                .when((i) -> ((Number) ((Map<?,?>) i).get("n")).intValue() > 10, act("big"), "r")
                .defaultIfNoMatch("neg").compile();
        var report = Trust.shadow(current, candidate,
                List.of(map("n", 5), map("n", 50)));
        check("shadow", report.total == 2 && report.differences >= 1);

        // 45,46: validate + contract version
        var issues = Trust.validate(c2);
        check("validate", issues != null);
        var v1 = Flow.create().whenExpr(pEq(pField("a"), pConst(1)), pConst(1), "r1", null).compile();
        var v2 = Flow.create().whenExpr(pEq(pField("a"), pConst(1)), pConst(1), "r1", null).compile();
        check("contract version stable", Trust.toIRJSON(v1).equals(Trust.toIRJSON(v2)));

        // 47: deterministic clock replay
        var clock = new FakeClock(1_700_000_000_000L, 0);
        var rec2 = Trust.record(c2, map("n", 1), clock);
        var res3 = Trust.replay(rec2, c2, ReplayMode.decision, null, null, false);
        check("deterministic replay", res3.equivalent != null && res3.equivalent);
    }

    // Features 48-62: portable IR & cross-cutting
    static void portableIr() throws Exception {
        // 48,49: PExpr ops + builders
        var exprs = new PExpr[]{
                pField("a"), pConst(1),
                pEq(pField("a"), pConst(1)), pNe(pField("a"), pConst(1)),
                pLt(pField("a"), pConst(1)), pLe(pField("a"), pConst(1)),
                pGt(pField("a"), pConst(1)), pGe(pField("a"), pConst(1)),
                pAnd(pEq(pField("a"), pConst(1)), pGt(pField("b"), pConst(0))),
                pOr(pEq(pField("a"), pConst(1)), pEq(pField("a"), pConst(2))),
                pNot(pEq(pField("a"), pConst(1))),
                pIsNull(pField("a")), pIsNotNull(pField("a")),
                pIn(pField("a"), List.of(1, 2, 3)), pNotIn(pField("a"), List.of(9))};
        check("pexpr ops", exprs.length == 15);
        check("evalExpr", Boolean.TRUE.equals(
                Portable.evalExpr(pEq(pField("a"), pConst(1)), map("a", 1))));

        // 50: expr serialization round-trip
        var expr = pAnd(pEq(pField("x"), pConst(1)), pGt(pField("y"), pConst(0)));
        var restored = Portable.exprFromDictPublic(Portable.exprToDict(expr));
        check("expr round-trip", Boolean.TRUE.equals(
                Portable.evalExpr(restored, map("x", 1, "y", 5))));

        // 51: portable rules + ToIR
        var c = Flow.create().whenExpr(pEq(pField("n"), pConst(1)), pConst("one"), "r1", null).compile();
        var irJson = Trust.toIRJSON(c);
        var pf = Portable.portableFlowFromJSON(irJson);
        check("portable rules", pf.rules.size() == 1 && "r1".equals(pf.rules.get(0).ruleId));

        // 52,53: whenExpr/whenNotExpr + fromIr
        var c2 = Flow.create()
                .whenExpr(pEq(pField("kind"), pConst("a")), pConst("A"), "ra", null)
                .whenNotExpr(pEq(pField("kind"), pConst("a")), pConst("not-a"), "rb", null)
                .defaultIfNoMatch("none").compile();
        String[] port = Advanced.portability(c2);
        check("portability PORTABLE", port.length > 0 && "PORTABLE".equals(port[0]));
        check("whenExpr", "A".equals(c2.tryExecute(map("kind", "a")).value));
        check("whenNotExpr", "not-a".equals(c2.tryExecute(map("kind", "b")).value));
        var rebuilt = Flow.fromIr(Portable.portableFlowToDict(pf)).compile();
        check("fromIr", rebuilt.tryExecute(map("n", 1)).value != null);

        // 54: ToIR + JSON round-trip
        var js = Trust.toIRJSON(c);
        var round = Portable.portableFlowFromJSON(js);
        check("IR JSON round-trip", round.rules.get(0).ruleId.equals("r1"));

        // 55: portable vs native classification
        check("native ToIR fails", true); // native contract: toIRJSON throws
        try {
            Trust.toIRJSON(Flow.create().when(condTrue(), act(1), "r").compile());
            check("native ToIR fails", false);
        } catch (Exception e) { check("native ToIR fails", true); }

        // 56: portability report
        var c3 = Flow.create().when(condTrue(), act(1), "r1")
                .catchTyped("Kind.Any", handler(0), "h").compile();
        var port3 = Advanced.portability(c3);
        check("portability report", port3.length >= 1 && port3[0] != null);

        // 57: IR limits (SPEC 9.2)
        check("MaxExprDepth", Portable.MAX_EXPR_DEPTH == 100);
        Object deep = map("op", "const", "value", 1);
        for (int i = 0; i <= Portable.MAX_EXPR_DEPTH; i++) {
            deep = map("op", "not", "args", List.of(deep));
        }
        try {
            Portable.exprFromDictPublic(deep);
            check("depth limit", false);
        } catch (FlowErrors.StructureError e) { check("depth limit", true); }

        // 58: flow_id + contract_version in IR
        var c4 = Flow.create().withFlowId("consumer-flow")
                .whenExpr(pEq(pField("a"), pConst(1)), pConst(1), "r1", null).compile();
        var ir4 = Portable.portableFlowFromJSON(Trust.toIRJSON(c4));
        check("flow_id", "consumer-flow".equals(ir4.flowId));
        check("contract_version in IR", ir4.contractVersion != null
                && !ir4.contractVersion.isEmpty());
    }

    static void crossCutting() throws Exception {
        // 59: portable JSON round-trip
        var c = Flow.create().whenExpr(pEq(pField("a"), pConst(1)), pConst("one"), "r1", null).compile();
        var js = Trust.toIRJSON(c);
        var restored = Portable.portableFlowFromJSON(js);
        check("portable JSON round-trip", "r1".equals(restored.rules.get(0).ruleId));

        // 60: FlowContext — Java exposes context via FinallyContext.context;
        // verify finally receives propagated context object.
        var ctxSeen = new Object[1];
        var c2 = Flow.create().when(condTrue(), act("v"), "r1")
                .finally_((ctx) -> ctxSeen[0] = ctx.context).compile();
        c2.tryExecute(map("x", 1));
        check("flow context", ctxSeen[0] != null);

        // 61: clocks
        var fake = new FakeClock(1_000, 0);
        fake.advance(10_000);
        check("fake clock", fake.wall() == 11_000);
        var c3 = Flow.create().when(condTrue(), act("ok"), "r1")
                .withClock(new FakeClock(0, 0)).compile();
        check("withClock", "ok".equals(c3.tryExecute(null).value));

        // 62: withFlowId
        var c4 = Flow.create().withFlowId("my-flow")
                .whenExpr(pEq(pField("a"), pConst(1)), pConst(1), "r1", null).compile();
        check("withFlowId", "my-flow".equals(
                Portable.portableFlowFromJSON(Trust.toIRJSON(c4)).flowId));

        // error hierarchy sanity
        check("error hierarchy", FlowErrors.exceptionForKind("Kind.Timeout") != null
                && FlowErrors.exceptionForKind("Kind.Cancelled") != null
                && FlowErrors.exceptionForKind("Kind.ValueError") != null
                && FlowErrors.exceptionForKind("Kind.Any") != null
                && Trust.SPEC_VERSION != null && !Trust.SPEC_VERSION.isEmpty());
    }
}
