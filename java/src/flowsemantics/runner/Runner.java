package flowsemantics.runner;

import flowsemantics.*;
import java.nio.file.*;
import java.util.*;

/** Conformance runner — conformance/runner-protocol.md.
 *  Usage: java flowsemantics.runner.Runner --vectors &lt;dir&gt; */
public final class Runner {
    record Result(String id, boolean passed, String reason) {}

    public static void main(String[] args) throws Exception {
        String dir = null;
        for (int i = 0; i < args.length - 1; i++) {
            if ("--vectors".equals(args[i])) dir = args[i + 1];
        }
        if (dir == null) { System.err.println("usage: Runner --vectors <dir>"); System.exit(2); }
        List<Path> paths = new ArrayList<>();
        try (var stream = Files.walk(Paths.get(dir))) {
            stream.filter(p -> p.toString().endsWith(".json")).sorted().forEach(paths::add);
        }
        if (paths.isEmpty()) { System.out.println("RESULT: 0/0 passed (no vectors discovered)"); return; }
        int passed = 0;
        for (Path p : paths) {
            Result r = runVector(p);
            if (r.passed()) { passed++; System.out.println("PASS " + r.id()); }
            else System.out.println("FAIL " + r.id() + ": " + r.reason());
        }
        System.out.printf("RESULT: %d/%d passed%n", passed, paths.size());
        if (passed != paths.size()) System.exit(1);
    }

    @SuppressWarnings("unchecked")
    static Result runVector(Path path) {
        String id = path.toString();
        Map<String, Object> vector;
        try {
            vector = Json.obj(Json.parse(Files.readString(path)));
        } catch (Exception e) {
            return new Result(id, false, "parse: " + e.getMessage());
        }
        id = Json.str(vector.get("id")) != null ? Json.str(vector.get("id")) : id;
        Map<String, Object> pipeline = Json.obj(vector.get("pipeline"));
        if (!pipeline.containsKey("rules") && !pipeline.containsKey("portable_ir")) {
            return new Result(id, false, "pipeline.rules or portable_ir missing");
        }
        String expectedError = Json.str(vector.get("expected_error"));
        Flow flow;
        try {
            flow = buildFlow(pipeline);
        } catch (Exception e) {
            if (expectedError != null) return new Result(id, e.getMessage() != null && e.getMessage().contains(expectedError), e.getMessage());
            return new Result(id, false, e.getMessage());
        }
        Object input;
        try {
            input = Fixtures.resolveFixture(Json.obj(vector.get("input")), new Fixtures.FixtureContext());
        } catch (Exception e) {
            String msg = "input fixture: " + e.getMessage();
            if (expectedError != null) return new Result(id, msg.contains(expectedError), msg);
            return new Result(id, false, msg);
        }
        Flow.FlowContract contract;
        try {
            contract = flow.compile();
        } catch (Exception e) {
            String msg = "compile: " + e.getMessage();
            if (expectedError != null) return new Result(id, msg.contains(expectedError), msg);
            return new Result(id, false, msg);
        }
        FakeClock clock = new FakeClock(1700000000000L, 0);
        boolean traceEnabled = vector.get("trace") != null;
        Outcome.FlowOutcome outcome;
        try {
            outcome = contract.tryExecute(input, clock, traceEnabled);
        } catch (Exception e) {
            String msg = "execution threw: " + e.getMessage();
            if (expectedError != null) return new Result(id, msg.contains(expectedError), msg);
            return new Result(id, false, msg);
        }
        if (expectedError != null) {
            return new Result(id, false, "expected rejection containing " + expectedError + " but execution completed");
        }
        String mismatch = compareExpected(outcome, Json.obj(vector.get("expected")));
        if (mismatch != null) return new Result(id, false, mismatch);
        String terr = compareTrace(vector, outcome);
        if (terr != null) return new Result(id, false, terr);
        return new Result(id, true, "");
    }

    @SuppressWarnings("unchecked")
    static Flow buildFlow(Map<String, Object> pipeline) {
        if (pipeline.containsKey("portable_ir")) {
            try {
                return Flow.fromIr(pipeline.get("portable_ir"));
            } catch (Exception e) {
                throw new RuntimeException("portable_ir rejected: " + e.getMessage());
            }
        }
        Flow flow = Flow.create();
        String mode = Json.str(pipeline.get("mode"));
        if (mode != null) flow.withMode(Outcome.EvaluationMode.valueOf(mode));
        Fixtures.FixtureContext ctx = new Fixtures.FixtureContext();

        List<Object> rules = pipeline.get("rules") instanceof List ? (List<Object>) pipeline.get("rules") : List.of();
        for (Object ro : rules) {
            Map<String, Object> r = Json.obj(ro);
            String kind = Json.str(r.get("kind")); if (kind == null) kind = "when";
            String id = Json.str(r.get("id"));
            Fixtures.FixtureValue av = Fixtures.asFixture(Fixtures.resolveFixture(Json.obj(r.get("action")), ctx));
            List<Outcome.Effect> effects = new ArrayList<>();
            if (r.get("effects") instanceof List<?> es) {
                for (Object ev : es) {
                    Map<String, Object> em = Json.obj(ev);
                    effects.add(new Outcome.Effect(Json.str(em.get("name")), em.get("payload")));
                }
            }
            Flow.GuardFn guard = null;
            if (r.get("guard") != null) {
                guard = Fixtures.asFixture(Fixtures.resolveFixture(Json.obj(r.get("guard")), ctx)).guard;
            }
            int priority = r.get("priority") instanceof Number n ? n.intValue() : 0;
            if ("then".equals(kind)) {
                flow.then(av.action, id);
                continue;
            }
            Flow.ConditionFn cond = Fixtures.asFixture(Fixtures.resolveFixture(Json.obj(r.get("condition")), ctx)).cond;
            if ("when_not".equals(kind)) flow.whenNot(cond, av.action, id);
            else flow.when(cond, av.action, id, guard, priority, effects);
        }

        if (pipeline.get("catches") instanceof List<?> cs) {
            for (Object co : cs) {
                Map<String, Object> c = Json.obj(co);
                String ckind = Json.str(c.get("kind"));
                String cid = Json.str(c.get("id"));
                String excKind = Json.str(c.get("exc_kind"));
                if ("rethrow".equals(ckind)) { flow.rethrow(); continue; }
                Fixtures.FixtureValue hv = Fixtures.asFixture(Fixtures.resolveFixture(Json.obj(c.get("handler")), ctx));
                if ("any".equals(ckind)) { flow.catchAny(hv.handler, cid); continue; }
                if ("typed".equals(ckind)) { flow.catchTyped(excKind, hv.handler, cid); continue; }
                if ("when".equals(ckind)) {
                    Flow.ConditionFn predCond = Fixtures.asFixture(Fixtures.resolveFixture(Json.obj(c.get("predicate")), ctx)).cond;
                    flow.catchWhen(excKind, (i, e) -> {
                        try { return predCond.test(i); } catch (Exception ex) { throw new RuntimeException(ex); }
                    }, hv.handler, cid);
                    continue;
                }
                throw new RuntimeException("unknown catch kind: " + ckind);
            }
        }

        if (pipeline.get("on_match") instanceof List<?> hs) {
            for (Object ho : hs) {
                Map<String, Object> href = Json.obj(ho);
                flow.onMatch(Fixtures.asFixture(Fixtures.resolveFixture(href, ctx)).hook);
            }
        }

        if (pipeline.get("finally") != null) {
            Object fraw = pipeline.get("finally");
            Map<String, Object> fref;
            if (fraw instanceof String s) fref = Map.of("fixture", s);
            else fref = Json.obj(fraw);
            flow.finally_(Fixtures.asFixture(Fixtures.resolveFixture(fref, ctx)).cleanup);
        }
        if (pipeline.get("finally_policy") != null) {
            flow.withFinallyPolicy(Outcome.FinallyFailurePolicy.valueOf(Json.str(pipeline.get("finally_policy"))));
        }

        if (pipeline.get("fallback") instanceof Map) {
            Map<String, Object> fb = Json.obj(pipeline.get("fallback"));
            String fkind = Json.str(fb.get("kind"));
            if ("otherwise".equals(fkind)) {
                Fixtures.FixtureValue av = Fixtures.asFixture(Fixtures.resolveFixture(Json.obj(fb.get("action")), ctx));
                flow.otherwise(av.action);
            } else if ("default_if_no_match".equals(fkind)) {
                flow.defaultIfNoMatch(fb.get("value"));
            } else {
                throw new RuntimeException("unknown fallback kind: " + fkind);
            }
        }
        return flow;
    }

    static String compareExpected(Outcome.FlowOutcome o, Map<String, Object> exp) {
        if (!String.valueOf(o.executionStatus).equals(String.valueOf(exp.get("execution_status")))) {
            return "execution_status: expected " + exp.get("execution_status") + ", got " + o.executionStatus;
        }
        String gotDecision = o.decisionStatus != null ? o.decisionStatus.name() : null;
        Object expDecision = exp.get("decision_status");
        if (expDecision == null ? gotDecision != null : !String.valueOf(expDecision).equals(gotDecision)) {
            return "decision_status: expected " + expDecision + ", got " + gotDecision;
        }
        if (exp.containsKey("value") && !jsonEq(o.value, exp.get("value"))) {
            return "value: expected " + exp.get("value") + ", got " + o.value;
        }
        if (exp.get("has_recovery") instanceof Boolean b && b != (o.recovery != null)) return "has_recovery mismatch";
        if (exp.get("has_interruption") instanceof Boolean b && b != (o.interruption != null)) return "has_interruption mismatch";
        String gotKind = o.interruption != null ? o.interruption.kind.name() : null;
        Object expKind = exp.get("interruption_kind");
        if (expKind == null ? gotKind != null : !String.valueOf(expKind).equals(gotKind)) {
            return "interruption_kind: expected " + expKind + ", got " + gotKind;
        }
        if (exp.get("has_finalization") instanceof Boolean b && b != (o.finalization != null)) return "has_finalization mismatch";
        Object gotClean = o.finalization != null ? o.finalization.isClean : null;
        Object expClean = exp.get("is_clean");
        if (expClean == null ? gotClean != null : !expClean.equals(gotClean)) {
            return "is_clean: expected " + expClean + ", got " + gotClean;
        }
        if (exp.get("secondary_exceptions_count") instanceof Number n && n.intValue() != o.secondaryExceptions.size()) {
            return "secondary_exceptions_count: expected " + n + ", got " + o.secondaryExceptions.size();
        }
        String gotPrimary = o.primaryException != null ? FlowErrors.kindOfException(o.primaryException) : null;
        Object expPrimary = exp.get("primary_exception_kind");
        if (expPrimary == null ? gotPrimary != null && !gotPrimary.isEmpty() : !String.valueOf(expPrimary).equals(gotPrimary)) {
            return "primary_exception_kind: expected " + expPrimary + ", got " + gotPrimary;
        }
        if (exp.get("effects") instanceof List<?> want) {
            List<Map<String, Object>> got = new ArrayList<>();
            for (Outcome.Effect e : o.effects) {
                Map<String, Object> m = new LinkedHashMap<>();
                m.put("name", e.name);
                if (e.payload != null) m.put("payload", e.payload);
                got.add(m);
            }
            List<Map<String, Object>> wn = new ArrayList<>();
            for (Object w : want) {
                Map<String, Object> m = new LinkedHashMap<>(Json.obj(w));
                if (m.get("payload") == null) m.remove("payload");
                wn.add(m);
            }
            if (got.size() != wn.size() || !jsonEq(got, wn)) {
                return "effects: expected " + wn + ", got " + got;
            }
        }
        return null;
    }

    static String compareTrace(Map<String, Object> vector, Outcome.FlowOutcome o) {
        if (!(vector.get("trace") instanceof List<?> expected) || expected.isEmpty()) return null;
        if (o.trace == null) return "trace expected but not collected";
        List<Outcome.TraceEvent> observed = o.trace.events;
        boolean subset = Boolean.TRUE.equals(vector.get("trace_subset"));
        if (subset) {
            int pos = 0;
            for (Object eo : expected) {
                Map<String, Object> e = Json.obj(eo);
                boolean found = false;
                while (pos < observed.size()) {
                    if (matches(observed.get(pos), e)) { found = true; pos++; break; }
                    pos++;
                }
                if (!found) return "trace subset: missing " + e;
            }
            return null;
        }
        if (observed.size() != expected.size()) {
            return "trace length: expected " + expected.size() + ", got " + observed.size();
        }
        for (int i = 0; i < expected.size(); i++) {
            if (!matches(observed.get(i), Json.obj(expected.get(i)))) {
                return "trace[" + i + "]: expected " + expected.get(i) + ", got " + observed.get(i).type;
            }
        }
        return null;
    }

    static boolean matches(Outcome.TraceEvent o, Map<String, Object> e) {
        if (!String.valueOf(e.get("type")).equals(o.type)) return false;
        if (e.get("rule_id") != null && !String.valueOf(e.get("rule_id")).equals(o.ruleId)) return false;
        if (e.get("reason") != null && !String.valueOf(e.get("reason")).equals(o.reason)) return false;
        return true;
    }

    static boolean jsonEq(Object a, Object b) {
        return Objects.equals(normalize(a), normalize(b));
    }

    @SuppressWarnings("unchecked")
    static Object normalize(Object v) {
        if (v instanceof Map) {
            Map<String, Object> m = new TreeMap<>();
            for (var e : ((Map<String, Object>) v).entrySet()) m.put(e.getKey(), normalize(e.getValue()));
            return m;
        }
        if (v instanceof List) {
            List<Object> l = new ArrayList<>();
            for (Object item : (List<Object>) v) l.add(normalize(item));
            return l;
        }
        if (v instanceof Double d) return d;
        if (v instanceof Long l) return l.doubleValue();
        if (v instanceof Integer i) return i.doubleValue();
        return v;
    }
}
