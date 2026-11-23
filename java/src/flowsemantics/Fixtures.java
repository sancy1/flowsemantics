package flowsemantics;

import java.util.*;

/** Fixture vocabulary — spec/fixtures.md, Java adapter. */
public final class Fixtures {
    /** A resolved fixture: one or more callable slots depending on the fixture kind. */
    public static final class FixtureValue {
        /** Condition callback (cond.* fixtures). */
        public Flow.ConditionFn cond;
        /** Action callback (action.* fixtures). */
        public Flow.ActionFn action;
        /** Guard callback (guard.* fixtures). */
        public Flow.GuardFn guard;
        /** Exception handler callback (catch.* fixtures). */
        public Flow.ExceptionHandler handler;
        /** Match hook callback (hook.* fixtures). */
        public Flow.HookFn hook;
        /** Finalizer cleanup callback (cleanup.* fixtures). */
        public Flow.CleanupFn cleanup;
    }

    /** Mutable context shared across fixture resolutions within one vector run. */
    public static final class FixtureContext {
        /** Records captured by hook.records fixtures. */
        public final List<Map<String, Object>> records = new ArrayList<>();
    }

    private static final Map<String, Object> INPUTS = Map.of(
        "input.empty", Map.of(),
        "input.order_50", Map.of("total", 50.0),
        "input.order_0", Map.of("total", 0.0),
        "input.order_large", Map.of("total", 10000.0)
    );

    /** Resolve a fixture reference (or nested action.returns ref) to a value. */
    @SuppressWarnings("unchecked")
    public static Object resolveFixture(Map<String, Object> ref, FixtureContext ctx) {
        String name = Json.str(ref.get("fixture"));
        Map<String, Object> params = ref.get("params") instanceof Map ? (Map<String, Object>) ref.get("params") : Map.of();
        Object input = INPUTS.get(name);
        if (input != null) return input;

        FixtureValue fv = new FixtureValue();
        switch (name) {
            case "cond.true" -> fv.cond = i -> true;
            case "cond.false" -> fv.cond = i -> false;
            case "cond.returns" -> { boolean v = Json.bool(params.get("value")); fv.cond = i -> v; }
            case "cond.throws" -> { String k = Json.str(params.get("kind")); fv.cond = i -> { throw FlowErrors.exceptionForKind(k); }; }
            case "cond.returns_per_call" -> {
                List<Object> vals = params.get("values") instanceof List ? (List<Object>) params.get("values") : List.of();
                int[] idx = {0};
                fv.cond = i -> {
                    int j = Math.min(idx[0]++, vals.size() - 1);
                    return Json.bool(vals.get(j));
                };
            }
            case "action.const" -> { Object v = params.get("v"); fv.action = (i, p) -> v; }
            case "action.throws" -> { String k = Json.str(params.get("kind")); fv.action = (i, p) -> { throw FlowErrors.exceptionForKind(k); }; }
            case "action.prev" -> fv.action = (i, p) -> p;
            case "action.returns" -> {
                Object sub = params.get("ref") != null ? params.get("ref") : params.get("fixture_ref");
                return resolveFixture((Map<String, Object>) sub, ctx);
            }
            case "guard.true" -> fv.guard = i -> true;
            case "guard.false" -> fv.guard = i -> false;
            case "catch.handles" -> { Object v = params.get("v"); fv.handler = (i, e) -> v; }
            case "catch.throws" -> { String k = Json.str(params.get("kind")); fv.handler = (i, e) -> { throw FlowErrors.exceptionForKind(k); }; }
            case "hook.records" -> fv.hook = (i, rid, v) -> ctx.records.add(Map.of("rule_id", rid, "value", v));
            case "hook.throws" -> { String k = Json.str(params.get("kind")); fv.hook = (i, rid, v) -> { throw FlowErrors.exceptionForKind(k); }; }
            case "cleanup.succeeds" -> fv.cleanup = ctx2 -> {};
            case "cleanup.throws" -> { String k = Json.str(params.get("kind")); fv.cleanup = ctx2 -> { throw FlowErrors.exceptionForKind(k); }; }
            case "cleanup.cooperative" -> fv.cleanup = ctx2 -> {};
            case "cleanup.ignores_token" -> fv.cleanup = ctx2 -> {};
            case "cleanup.delays" -> fv.cleanup = ctx2 -> {};
            case "enrichment.delayed" -> { double ms = Json.num(params.get("ms")); fv.action = (i, p) -> Map.of("delayed_ms", ms); }
            default -> throw new FlowErrors.StructureError("unknown fixture: " + name);
        }
        return fv;
    }

    /** Cast a resolved fixture value to FixtureValue; throws StructureError otherwise. */
    @SuppressWarnings("unchecked")
    public static FixtureValue asFixture(Object v) {
        if (v instanceof FixtureValue fv) return fv;
        throw new FlowErrors.StructureError("expected FixtureValue, got " + v.getClass());
    }
}
