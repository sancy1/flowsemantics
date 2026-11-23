package flowsemantics;

import java.util.*;

/** Portable IR — SPEC 14.2, 9.2. */
public final class Portable {
    /** Maximum expression nesting depth (SPEC 9.2). */
    public static final int MAX_EXPR_DEPTH = 100;
    /** Maximum portable IR size in bytes (SPEC 9.2). */
    public static final int MAX_IR_BYTES = 1_000_000;
    /** Maximum rule count in portable IR (SPEC 9.2). */
    public static final int MAX_RULES = 10_000;

    /** A node in the portable expression subset (SPEC 14.2). */
    public static final class PExpr {
        /** Operator name (one of OPS). */
        public final String op;
        /** Child expressions. */
        public final List<PExpr> args;
        /** Literal value or enum list, depending on op. */
        public final Object value;
        /** Create a PExpr. */
        public PExpr(String op, List<PExpr> args, Object value) {
            this.op = op; this.args = args; this.value = value;
        }
    }

    /** Closed set of portable expression operators (SPEC 14.2). */
    public static final Set<String> OPS = Set.of(
        "field", "const", "eq", "ne", "lt", "le", "gt", "ge",
        "and", "or", "not", "is_null", "is_not_null", "in", "not_in");

    // -- expression builders (SPEC 14.2) ------------------------------------

    /** Named field access (read-only). */
    public static PExpr pField(String name) { return new PExpr("field", List.of(), name); }
    /** Literal constant. */
    public static PExpr pConst(Object value) { return new PExpr("const", List.of(), value); }
    /** Equality comparison. */
    public static PExpr pEq(PExpr a, PExpr b) { return new PExpr("eq", List.of(a, b), null); }
    /** Inequality comparison. */
    public static PExpr pNe(PExpr a, PExpr b) { return new PExpr("ne", List.of(a, b), null); }
    /** Less-than comparison. */
    public static PExpr pLt(PExpr a, PExpr b) { return new PExpr("lt", List.of(a, b), null); }
    /** Less-than-or-equal comparison. */
    public static PExpr pLe(PExpr a, PExpr b) { return new PExpr("le", List.of(a, b), null); }
    /** Greater-than comparison. */
    public static PExpr pGt(PExpr a, PExpr b) { return new PExpr("gt", List.of(a, b), null); }
    /** Greater-than-or-equal comparison. */
    public static PExpr pGe(PExpr a, PExpr b) { return new PExpr("ge", List.of(a, b), null); }
    /** Boolean AND over all arguments. */
    public static PExpr pAnd(PExpr... args) { return new PExpr("and", List.of(args), null); }
    /** Boolean OR over all arguments. */
    public static PExpr pOr(PExpr... args) { return new PExpr("or", List.of(args), null); }
    /** Boolean NOT. */
    public static PExpr pNot(PExpr a) { return new PExpr("not", List.of(a), null); }
    /** Null check. */
    public static PExpr pIsNull(PExpr a) { return new PExpr("is_null", List.of(a), null); }
    /** Non-null check. */
    public static PExpr pIsNotNull(PExpr a) { return new PExpr("is_not_null", List.of(a), null); }
    /** Enum membership (in). */
    public static PExpr pIn(PExpr a, List<Object> values) { return new PExpr("in", List.of(a), values); }
    /** Enum non-membership (not in). */
    public static PExpr pNotIn(PExpr a, List<Object> values) { return new PExpr("not_in", List.of(a), values); }

    /** Serialize a PExpr to a JSON-safe map. */
    @SuppressWarnings("unchecked")
    public static Map<String, Object> exprToDict(PExpr e) {
        if (e == null) return null;
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("op", e.op);
        switch (e.op) {
            case "field", "const" -> m.put("value", e.value);
            case "in", "not_in" -> {
                m.put("args", List.of(exprToDict(e.args.get(0))));
                m.put("value", e.value);
            }
            case "and", "or" -> {
                List<Object> args = new ArrayList<>();
                for (PExpr a : e.args) args.add(exprToDict(a));
                m.put("args", args);
            }
            case "not", "is_null", "is_not_null" ->
                m.put("args", List.of(exprToDict(e.args.get(0))));
            default -> m.put("args", List.of(exprToDict(e.args.get(0)), exprToDict(e.args.get(1))));
        }
        return m;
    }

    /** Deserialize a PExpr from its map form (SPEC 9.2 depth limit). */
    public static PExpr exprFromDictPublic(Object data) { return exprFromDict(data, 0); }

    /** Evaluate a portable expression against the input (SPEC 14.2). */
    @SuppressWarnings("unchecked")
    public static Object evalExpr(PExpr e, Object input) {
        return switch (e.op) {
            case "const" -> e.value;
            case "field" -> {
                if (!(input instanceof Map)) throw new FlowErrors.StructureError("field access requires mapping input");
                yield ((Map<String, Object>) input).get((String) e.value);
            }
            case "eq" -> valueEquals(evalExpr(e.args.get(0), input), evalExpr(e.args.get(1), input));
            case "ne" -> !valueEquals(evalExpr(e.args.get(0), input), evalExpr(e.args.get(1), input));
            case "lt", "le", "gt", "ge" -> {
                double a = Json.num(evalExpr(e.args.get(0), input));
                double b = Json.num(evalExpr(e.args.get(1), input));
                yield switch (e.op) {
                    case "lt" -> a < b;
                    case "le" -> a <= b;
                    case "gt" -> a > b;
                    default -> a >= b;
                };
            }
            case "and" -> {
                for (PExpr a : e.args) if (!truthy(evalExpr(a, input))) { yield false; }
                yield true;
            }
            case "or" -> {
                for (PExpr a : e.args) if (truthy(evalExpr(a, input))) { yield true; }
                yield false;
            }
            case "not" -> !truthy(evalExpr(e.args.get(0), input));
            case "is_null" -> evalExpr(e.args.get(0), input) == null;
            case "is_not_null" -> evalExpr(e.args.get(0), input) != null;
            case "in", "not_in" -> {
                Object v = evalExpr(e.args.get(0), input);
                boolean found = false;
                if (e.value instanceof List<?> list) {
                    for (Object item : list) if (valueEquals(item, v)) { found = true; break; }
                }
                yield e.op.equals("in") ? found : !found;
            }
            default -> throw new FlowErrors.StructureError("unknown op: " + e.op);
        };
    }

    private static boolean truthy(Object v) { return Boolean.TRUE.equals(v); }

    /** Numeric-aware equality: Integer 1 equals Double 1.0 across IR round-trips. */
    private static boolean valueEquals(Object a, Object b) {
        if (Objects.equals(a, b)) return true;
        if (a instanceof Number && b instanceof Number) {
            return Double.compare(((Number) a).doubleValue(), ((Number) b).doubleValue()) == 0;
        }
        return false;
    }

    @SuppressWarnings("unchecked")
    static PExpr exprFromDict(Object data, int depth) {
        if (depth > MAX_EXPR_DEPTH) throw new FlowErrors.StructureError("expression nesting exceeds maximum depth");
        if (!(data instanceof Map)) throw new FlowErrors.StructureError("expression must be an object");
        Map<String, Object> m = (Map<String, Object>) data;
        String op = Json.str(m.get("op"));
        if (!OPS.contains(op)) throw new FlowErrors.StructureError("unknown op: " + op);
        List<PExpr> args = new ArrayList<>();
        Object rawArgs = m.get("args");
        if (rawArgs instanceof List<?> list) {
            for (Object a : list) args.add(exprFromDict(a, depth + 1));
        }
        Object value = m.get("value");
        return new PExpr(op, args, value);
    }

    /** One rule in the Portable IR (SPEC 14.2). */
    public static final class PortableRule {
        /** Unique rule identifier. */
        public String ruleId;
        /** Rule kind: when | when_not. */
        public String kind;
        /** Condition expression. */
        public PExpr condition;
        /** Optional guard expression. */
        public PExpr guard;
        /** Transform expression producing the value. */
        public PExpr transform;
        /** Evaluation priority. */
        public int priority;
        /** Effective-from timestamp (ISO-8601 string). */
        public String effectiveFrom;
        /** Effective-until timestamp (ISO-8601 string). */
        public String effectiveUntil;
        /** Proposed effects. */
        public List<Outcome.Effect> effects = new ArrayList<>();
    }

    /** Canonical Portable IR document (SPEC 14.2). */
    public static final class PortableFlow {
        /** SPEC version that produced the IR. */
        public String specVersion;
        /** Flow identifier. */
        public String flowId;
        /** Portability classification. */
        public String portability;
        /** Evaluation mode. */
        public Outcome.EvaluationMode mode;
        /** Rules in evaluation order. */
        public List<PortableRule> rules = new ArrayList<>();
        /** Fallback rule, if any. */
        public Map<String, Object> fallback;
        /** Contract version carried from the source contract. */
        public String contractVersion;
    }

    /** Deserialize a PortableFlow from its map form, enforcing SPEC 9.2 limits. */
    @SuppressWarnings("unchecked")
    public static PortableFlow portableFlowFromDict(Object data) {
        if (!(data instanceof Map)) throw new FlowErrors.StructureError("portable IR must be an object");
        Map<String, Object> d = (Map<String, Object>) data;
        Object rawRules = d.get("rules");
        List<Object> ruleList = rawRules instanceof List<?> l ? (List<Object>) l : List.of();
        if (ruleList.size() > MAX_RULES) throw new FlowErrors.StructureError("rule count exceeds maximum");
        Set<String> seen = new HashSet<>();
        PortableFlow pf = new PortableFlow();
        pf.specVersion = Json.str(d.get("spec_version"));
        pf.flowId = Json.str(d.get("flow_id"));
        pf.portability = Json.str(d.get("portability"));
        pf.mode = Outcome.EvaluationMode.valueOf(Json.str(d.get("mode")));
        pf.contractVersion = Json.str(d.get("contract_version"));
        for (Object r : ruleList) {
            if (!(r instanceof Map)) throw new FlowErrors.StructureError("rule entries must be objects");
            Map<String, Object> rm = (Map<String, Object>) r;
            String rid = Json.str(rm.get("rule_id"));
            if (rid == null || rid.isEmpty()) throw new FlowErrors.StructureError("rule_id must be non-empty string");
            if (!seen.add(rid)) throw new FlowErrors.StructureError("duplicate rule_id: " + rid);
            String kind = Json.str(rm.get("kind"));
            if ("then".equals(kind)) throw new FlowErrors.StructureError("portable IR cannot carry then stages (ADR-0003)");
            if (!"when".equals(kind) && !"when_not".equals(kind)) {
                throw new FlowErrors.StructureError("unknown rule kind: " + kind);
            }
            PortableRule pr = new PortableRule();
            pr.ruleId = rid; pr.kind = kind;
            if (rm.get("condition") != null) pr.condition = exprFromDict(rm.get("condition"), 0);
            if (rm.get("guard") != null) pr.guard = exprFromDict(rm.get("guard"), 0);
            if (rm.get("transform") != null) pr.transform = exprFromDict(rm.get("transform"), 0);
            if (rm.get("priority") instanceof Number n) pr.priority = n.intValue();
            pr.effectiveFrom = Json.str(rm.get("effective_from"));
            pr.effectiveUntil = Json.str(rm.get("effective_until"));
            if (rm.get("effects") instanceof List<?> es) {
                for (Object ev : es) {
                    if (ev instanceof Map) {
                        Map<String, Object> em = (Map<String, Object>) ev;
                        pr.effects.add(new Outcome.Effect(Json.str(em.get("name")), em.get("payload")));
                    }
                }
            }
            pf.rules.add(pr);
        }
        if (d.get("fallback") instanceof Map) pf.fallback = (Map<String, Object>) d.get("fallback");
        return pf;
    }

    /** Serialize a PortableFlow to a JSON-safe map. */
    @SuppressWarnings("unchecked")
    public static Map<String, Object> portableFlowToDict(PortableFlow pf) {
        List<Object> rules = new ArrayList<>();
        for (PortableRule r : pf.rules) {
            Map<String, Object> rm = new LinkedHashMap<>();
            rm.put("rule_id", r.ruleId);
            rm.put("kind", r.kind);
            rm.put("condition", exprToDict(r.condition));
            rm.put("guard", exprToDict(r.guard));
            rm.put("transform", exprToDict(r.transform));
            rm.put("priority", r.priority);
            rm.put("effective_from", r.effectiveFrom);
            rm.put("effective_until", r.effectiveUntil);
            rm.put("effects", r.effects);
            rules.add(rm);
        }
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("spec_version", pf.specVersion);
        m.put("flow_id", pf.flowId);
        m.put("portability", pf.portability);
        m.put("mode", pf.mode != null ? pf.mode.name() : null);
        m.put("rules", rules);
        m.put("fallback", pf.fallback);
        m.put("contract_version", pf.contractVersion);
        return m;
    }

    /** Serialize a PortableFlow to canonical JSON. */
    public static String portableFlowToJSON(PortableFlow pf) {
        return Trust.CanonicalJson.write(portableFlowToDict(pf));
    }

    /** Deserialize a PortableFlow from JSON, enforcing the SPEC 9.2 size limit. */
    public static PortableFlow portableFlowFromJSON(String text) {
        if (text.length() > MAX_IR_BYTES) {
            throw new FlowErrors.StructureError("portable IR exceeds maximum size " + MAX_IR_BYTES + " bytes (SPEC 9.2)");
        }
        return portableFlowFromDict(Json.parse(text));
    }
}
