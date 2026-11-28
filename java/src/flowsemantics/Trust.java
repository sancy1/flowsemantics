package flowsemantics;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

/** Trust layer — SPEC 12.4-12.10: contract versioning, explain,
 *  validate, replay (4 modes), shadow. */
public final class Trust {
    /** SPEC version this implementation conforms to. */
    public static final String SPEC_VERSION = "0.1.0";

    // --- Contract version (SPEC 12.9, algorithm v1) ---

    public static String contractVersion(List<Flow.Rule> rules, Flow.Fallback fallback,
            Outcome.EvaluationMode mode, List<Flow.CatchRule> catches,
            int finalizerCount, Outcome.FinallyFailurePolicy policy,
            long finallyTimeoutMs, boolean traceEnabled,
            List<Portable.PortableRule> portableRules) {
        List<Map<String, Object>> ruleList = new ArrayList<>();
        for (int i = 0; i < rules.size(); i++) {
            Flow.Rule r = rules.get(i);
            Portable.PortableRule pr = i < portableRules.size() ? portableRules.get(i) : null;
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("id", r.id); m.put("kind", r.kind); m.put("priority", r.priority);
            m.put("effective_from", r.effectiveFrom); m.put("effective_until", r.effectiveUntil);
            m.put("native", pr == null);
            m.put("condition", pr != null && pr.condition != null ? Portable.exprToDict(pr.condition) : null);
            m.put("guard", pr != null && pr.guard != null ? Portable.exprToDict(pr.guard) : null);
            m.put("transform", pr != null && pr.transform != null ? Portable.exprToDict(pr.transform) : null);
            List<Map<String, Object>> effs = new ArrayList<>();
            for (Outcome.Effect e : r.effects) {
                Map<String, Object> em = new LinkedHashMap<>();
                em.put("name", e.name); em.put("payload", e.payload);
                effs.add(em);
            }
            m.put("effects", effs);
            ruleList.add(m);
        }
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("algorithm", "flowsemantics-contract-v2");
        payload.put("rules", ruleList);
        payload.put("fallback", fallback == null ? null : fallback.kind);
        payload.put("mode", mode.name());
        List<String> catchKinds = new ArrayList<>();
        for (Flow.CatchRule c : catches) catchKinds.add(c.kind);
        payload.put("catches", catchKinds);
        payload.put("finalizer_count", finalizerCount);
        payload.put("finally_policy", policy.name());
        payload.put("finally_timeout_ms", finallyTimeoutMs);
        payload.put("trace_enabled", traceEnabled);
        String canonical = CanonicalJson.write(payload);
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] hash = md.digest(canonical.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < 16; i++) sb.append(String.format("%02x", hash[i]));
            return sb.toString();
        } catch (Exception e) { throw new RuntimeException(e); }
    }

    // --- Canonical JSON (sorted keys, no whitespace) ---

    static final class CanonicalJson {
        static String write(Object v) {
            StringBuilder sb = new StringBuilder();
            writeValue(sb, v);
            return sb.toString();
        }
        @SuppressWarnings("unchecked")
        static void writeValue(StringBuilder sb, Object v) {
            if (v == null) { sb.append("null"); return; }
            if (v instanceof String s) { sb.append('"').append(escape(s)).append('"'); return; }
            if (v instanceof Boolean b) { sb.append(b); return; }
            if (v instanceof Number n) { sb.append(n); return; }
            if (v instanceof Map<?, ?> m) {
                List<String> keys = new ArrayList<>();
                for (Object k : m.keySet()) keys.add(String.valueOf(k));
                Collections.sort(keys);
                sb.append('{');
                for (int i = 0; i < keys.size(); i++) {
                    if (i > 0) sb.append(',');
                    sb.append('"').append(escape(keys.get(i))).append("\":");
                    writeValue(sb, ((Map<String, Object>) m).get(keys.get(i)));
                }
                sb.append('}');
                return;
            }
            if (v instanceof List<?> l) {
                sb.append('[');
                for (int i = 0; i < l.size(); i++) {
                    if (i > 0) sb.append(',');
                    writeValue(sb, l.get(i));
                }
                sb.append(']');
                return;
            }
            sb.append('"').append(escape(v.toString())).append('"');
        }
        static String escape(String s) {
            StringBuilder sb = new StringBuilder();
            for (char c : s.toCharArray()) {
                switch (c) {
                    case '"' -> sb.append("\\\"");
                    case '\\' -> sb.append("\\\\");
                    case '\n' -> sb.append("\\n");
                    case '\r' -> sb.append("\\r");
                    case '\t' -> sb.append("\\t");
                    default -> sb.append(c);
                }
            }
            return sb.toString();
        }
    }

    // --- Validation (SPEC 12.8) ---

    /** A static-analysis finding (SPEC 12.8). */
    public static final class ValidationIssue {
        /** Severity: error | warning. */
        public final String severity;
        /** Issue code (e.g. empty_flow, duplicate_rule_id). */
        public final String code;
        /** Human-readable message. */
        public final String message;
        /** Rule ID associated with the issue, or "". */
        public final String ruleId;
        /** Create a ValidationIssue. */
        public ValidationIssue(String sev, String code, String msg, String rid) {
            severity = sev; this.code = code; message = msg; ruleId = rid;
        }
    }

    /** Perform static analysis on a contract without executing it (SPEC 12.8). */
    public static List<ValidationIssue> validate(Flow.FlowContract c) {
        List<ValidationIssue> issues = new ArrayList<>();
        if (c.rules.isEmpty() && c.fallback == null) {
            issues.add(new ValidationIssue("error", "empty_flow",
                "flow has neither rules nor a fallback", ""));
        }
        Set<String> seen = new HashSet<>();
        for (Flow.Rule r : c.rules) {
            if (!seen.add(r.id)) {
                issues.add(new ValidationIssue("error", "duplicate_rule_id",
                    "duplicate RuleId: " + r.id, r.id));
            }
        }
        boolean seenAny = false;
        for (Flow.CatchRule cr : c.catches) {
            if ("any".equals(cr.kind)) seenAny = true;
            else if (seenAny && ("typed".equals(cr.kind) || "when".equals(cr.kind))) {
                issues.add(new ValidationIssue("error", "catch_any_ordering",
                    "typed catch registered after catch_any", ""));
            }
        }
        // effective date inversion (SPEC 12.9)
        for (Flow.Rule r : c.rules) {
            if (r.effectiveFrom != null && r.effectiveUntil != null && r.effectiveFrom >= r.effectiveUntil) {
                issues.add(new ValidationIssue("error", "invalid_effective_window",
                    "effective_from must be before effective_until", r.id));
            }
        }
        // unreachable rules: provable only for portable const-true (SPEC 12.8)
        if (c.mode != Outcome.EvaluationMode.AllMatch && c.hasPortable) {
            boolean unconditional = false;
            for (int i = 0; i < c.rules.size(); i++) {
                Flow.Rule r = c.rules.get(i);
                if ("then".equals(r.kind)) continue;
                if (unconditional) {
                    issues.add(new ValidationIssue("warning", "unreachable_rule",
                        "rule cannot match: an earlier unconditional rule always matches first", r.id));
                    continue;
                }
                if (i < c.portableRules.size() && c.portableRules.get(i).condition != null &&
                    "const".equals(c.portableRules.get(i).condition.op) &&
                    Boolean.TRUE.equals(c.portableRules.get(i).condition.value)) {
                    unconditional = true;
                }
            }
        }
        // overlap warning: identical portable conditions. O(n) grouping
        // by (kind, canonical condition JSON); pairwise compare only
        // within each group (SPEC 12.8).
        if (c.hasPortable) {
            Map<String, List<Integer>> groups = new LinkedHashMap<>();
            for (int i = 0; i < c.portableRules.size(); i++) {
                Portable.PortableRule pr = c.portableRules.get(i);
                String condJson = pr.condition != null
                    ? CanonicalJson.write(Portable.exprToDict(pr.condition)) : "null";
                String key = pr.kind + "\u0000" + condJson;
                groups.computeIfAbsent(key, k -> new ArrayList<>()).add(i);
            }
            for (List<Integer> idxs : groups.values()) {
                for (int a = 0; a < idxs.size(); a++) {
                    for (int b = a + 1; b < idxs.size(); b++) {
                        issues.add(new ValidationIssue("warning", "overlapping_rules",
                            "rules have structurally identical conditions",
                            c.portableRules.get(idxs.get(b)).ruleId));
                    }
                }
            }
        }
        // gap warning
        if (c.fallback == null && !c.rules.isEmpty()) {
            issues.add(new ValidationIssue("warning", "possible_gap",
                "no fallback configured; some inputs may produce NO_MATCH", ""));
        }
        return issues;
    }

    static boolean exprEqual(Portable.PExpr a, Portable.PExpr b) {
        if (a == b) return true;
        if (a == null || b == null) return false;
        if (!a.op.equals(b.op)) return false;
        if (!Objects.equals(a.value, b.value)) return false;
        if (a.args.size() != b.args.size()) return false;
        for (int i = 0; i < a.args.size(); i++) {
            if (!exprEqual(a.args.get(i), b.args.get(i))) return false;
        }
        return true;
    }

    // --- Explain (SPEC 12.4) ---

    /** Render an execution trace as human-readable lines (SPEC 12.4). */
    public static String explain(Flow.FlowContract c, Outcome.ExecutionTrace trace) {
        StringBuilder sb = new StringBuilder();
        sb.append("FlowContract ").append(c.contractVersion)
          .append(": ").append(trace.events.size()).append(" event(s)\n");
        for (Outcome.TraceEvent e : trace.events) {
            String rid = e.ruleId != null ? e.ruleId : "-";
            String reason = e.reason != null ? " (" + e.reason + ")" : "";
            sb.append("  [").append(e.type).append("] rule=").append(rid).append(reason).append('\n');
        }
        return sb.toString().stripTrailing();
    }

    // --- Replay (SPEC 12.6) ---

    /** The four replay operations (SPEC 12.6). */
    public enum ReplayMode { simulation, historical, decision, effects }

    /** Raised when a replay record cannot be safely replayed. */
    public static final class ReplayError extends RuntimeException {
        /** Create a ReplayError with the given message. */
        public ReplayError(String msg) { super(msg); }
    }

    /** A recorded decision tuple (SPEC 12.6, 12.10). */
    public static final class ReplayRecord {
        /** SPEC version that produced the record. */
        public String specVersion;
        /** Contract version that produced the record. */
        public String contractVersion;
        /** Recorded input. */
        public Object input;
        /** Recorded wall-clock time (epoch ms). */
        public long clockWall;
        /** Recorded monotonic time (ms). */
        public long clockMonotonic;
        /** Recorded outcome. */
        public Outcome.FlowOutcome outcome;
        /** Recorded trace, if collected. */
        public Outcome.ExecutionTrace trace;
        /** Recorded proposed effects. */
        public List<Outcome.Effect> effects = new ArrayList<>();
        /** Optional HMAC-SHA256 integrity tag. */
        public String integrity;
    }

    /** Result of a replay operation (SPEC 12.6). */
    public static final class ReplayResult {
        /** The replay mode used. */
        public ReplayMode mode;
        /** Replayed or recorded outcome. */
        public Outcome.FlowOutcome outcome;
        /** Semantic equivalence vs the recorded outcome (decision mode). */
        public Boolean equivalent;
        /** Number of effects applied (effects mode). */
        public int effectsApplied;
    }

    static Map<String, Object> canonicalPayload(ReplayRecord rec) {
        Map<String, Object> outcome = new LinkedHashMap<>();
        outcome.put("execution_status", rec.outcome.executionStatus.name());
        outcome.put("decision_status", rec.outcome.decisionStatus != null ? rec.outcome.decisionStatus.name() : null);
        outcome.put("value", rec.outcome.value);
        outcome.put("has_recovery", rec.outcome.recovery != null);
        outcome.put("interruption_kind", rec.outcome.interruption != null ? rec.outcome.interruption.kind.name() : null);
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("spec_version", rec.specVersion);
        payload.put("contract_version", rec.contractVersion);
        payload.put("input", rec.input);
        payload.put("clock_wall", rec.clockWall);
        payload.put("clock_monotonic", rec.clockMonotonic);
        payload.put("outcome", outcome);
        List<Map<String, Object>> effs = new ArrayList<>();
        for (Outcome.Effect e : rec.effects) {
            Map<String, Object> em = new LinkedHashMap<>();
            em.put("name", e.name); em.put("payload", e.payload);
            effs.add(em);
        }
        payload.put("effects", effs);
        return payload;
    }

    static byte[] hexToBytes(String hex) {
        if (hex == null || hex.length() % 2 != 0) throw new IllegalArgumentException("bad hex");
        byte[] out = new byte[hex.length() / 2];
        for (int i = 0; i < out.length; i++) {
            out[i] = (byte) Integer.parseInt(hex.substring(2 * i, 2 * i + 2), 16);
        }
        return out;
    }

    static String hmacSha256Hex(byte[] key, String data) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(key, "HmacSHA256"));
            byte[] digest = mac.doFinal(data.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (byte b : digest) sb.append(String.format("%02x", b));
            return sb.toString();
        } catch (Exception e) { throw new RuntimeException(e); }
    }

    /** Return a copy of the record with an HMAC-SHA256 integrity tag (SPEC 9.5). */
    public static ReplayRecord sign(ReplayRecord rec, byte[] key) {
        ReplayRecord cp = new ReplayRecord();
        cp.specVersion = rec.specVersion; cp.contractVersion = rec.contractVersion;
        cp.input = rec.input; cp.clockWall = rec.clockWall; cp.clockMonotonic = rec.clockMonotonic;
        cp.outcome = rec.outcome; cp.trace = rec.trace; cp.effects = rec.effects;
        cp.integrity = hmacSha256Hex(key, CanonicalJson.write(canonicalPayload(rec)));
        return cp;
    }

    /** Execute with tracing and capture a ReplayRecord (SPEC 12.6). */
    public static ReplayRecord record(Flow.FlowContract c, Object input, Clock clock) {
        if (clock == null) clock = c.clock();
        Outcome.FlowOutcome outcome = c.tryExecute(input, clock, true);
        ReplayRecord rec = new ReplayRecord();
        rec.specVersion = SPEC_VERSION;
        rec.contractVersion = c.contractVersion;
        rec.input = input;
        rec.clockWall = clock.wall();
        rec.clockMonotonic = clock.monotonic();
        rec.outcome = outcome;
        rec.trace = outcome.trace;
        rec.effects = outcome.effects;
        return rec;
    }

    static void verifyIntegrity(ReplayRecord rec, byte[] key) {
        if (rec.integrity == null) return;
        if (key == null) throw new ReplayError("record carries an integrity tag; an integrity_key is required");
        String expected = hmacSha256Hex(key, CanonicalJson.write(canonicalPayload(rec)));
        byte[] expectedBytes;
        byte[] actualBytes;
        try {
            expectedBytes = hexToBytes(expected);
            actualBytes = hexToBytes(rec.integrity);
        } catch (IllegalArgumentException e) {
            throw new ReplayError("replay record integrity check failed");
        }
        if (!MessageDigest.isEqual(expectedBytes, actualBytes)) {
            throw new ReplayError("replay record integrity check failed");
        }
    }

    static void checkVersions(ReplayRecord rec, Flow.FlowContract c) {
        if (!rec.specVersion.equals(SPEC_VERSION)) {
            throw new ReplayError("record spec_version does not match current; replay fails closed (SPEC 9.5)");
        }
        if (!rec.contractVersion.equals(c.contractVersion)) {
            throw new ReplayError("record contract_version does not match the current contract; replay fails closed (SPEC 12.6)");
        }
    }

    static boolean semanticallyEquivalent(Outcome.FlowOutcome a, Outcome.FlowOutcome b) {
        if (a.executionStatus != b.executionStatus) return false;
        if (a.decisionStatus != b.decisionStatus) return false;
        if (!Objects.equals(a.value, b.value)) return false;
        if ((a.recovery == null) != (b.recovery == null)) return false;
        if (a.recovery != null && b.recovery != null
                && !Objects.equals(a.recovery.handlerRuleId, b.recovery.handlerRuleId)) return false;
        String ka = a.interruption != null ? a.interruption.kind.name() : null;
        String kb = b.interruption != null ? b.interruption.kind.name() : null;
        return Objects.equals(ka, kb);
    }

    /** Callback that applies a recorded effect (effects replay mode only). */
    public interface EffectExecutor { void execute(Outcome.Effect effect); }

    /** Replay a recorded decision (SPEC 12.6). Fails closed on version or
     *  integrity mismatch; effects mode requires explicit authorization. */
    public static ReplayResult replay(ReplayRecord rec, Flow.FlowContract c, ReplayMode mode,
            byte[] integrityKey, EffectExecutor executor, boolean authorizeEffects) {
        verifyIntegrity(rec, integrityKey);
        checkVersions(rec, c);
        ReplayResult res = new ReplayResult();
        res.mode = mode;
        switch (mode) {
            case historical -> { res.outcome = rec.outcome; return res; }
            case simulation, decision -> {
                Clock clk = new FakeClock(rec.clockWall, rec.clockMonotonic);
                Outcome.FlowOutcome outcome = c.simulateWithClock(rec.input, clk);
                res.outcome = outcome;
                res.equivalent = semanticallyEquivalent(outcome, rec.outcome);
                return res;
            }
            case effects -> {
                if (!authorizeEffects) throw new ReplayError("effect re-execution requires explicit authorization");
                if (executor == null) throw new ReplayError("EFFECTS mode requires an effect_executor");
                int applied = 0;
                for (Outcome.Effect e : rec.effects) { executor.execute(e); applied++; }
                res.effectsApplied = applied;
                return res;
            }
        }
        throw new ReplayError("unknown replay mode: " + mode);
    }

    // --- Portable IR export (SPEC 14.2) ---

    /** Export a PORTABLE contract as a PortableFlow IR document (SPEC 14.2). */
    public static Portable.PortableFlow toIR(Flow.FlowContract c) {
        if (!c.hasPortable) {
            throw new FlowErrors.StructureError(
                "contract is NATIVE; only PORTABLE contracts can be exported to the Portable IR (SPEC 14.2)");
        }
        Portable.PortableFlow pf = new Portable.PortableFlow();
        pf.specVersion = SPEC_VERSION;
        pf.flowId = c.flowId != null ? c.flowId : "flow";
        pf.portability = "PORTABLE";
        pf.mode = c.mode;
        pf.contractVersion = c.contractVersion;
        for (Portable.PortableRule pr : c.portableRules) pf.rules.add(pr);
        return pf;
    }

    /** Export a PORTABLE contract as canonical Portable IR JSON (SPEC 14.2). */
    public static String toIRJSON(Flow.FlowContract c) {
        return Portable.portableFlowToJSON(toIR(c));
    }

    static String exprJSON(Portable.PExpr e) {
        StringBuilder sb = new StringBuilder();
        sb.append("{\"op\":\"").append(e.op).append("\"");
        if (!e.args.isEmpty()) {
            sb.append(",\"args\":[");
            for (int i = 0; i < e.args.size(); i++) {
                if (i > 0) sb.append(',');
                sb.append(exprJSON(e.args.get(i)));
            }
            sb.append(']');
        }
        if (e.value != null) {
            sb.append(",\"value\":");
            if (e.value instanceof String s) sb.append('"').append(s).append('"');
            else if (e.value instanceof Boolean b) sb.append(b);
            else sb.append(e.value);
        }
        sb.append('}');
        return sb.toString();
    }

    // --- Shadow (SPEC 12.7) ---

    /** One shadow-comparison entry (SPEC 12.7). */
    public static final class ShadowEntry {
        /** Input index. */
        public int index;
        /** The input evaluated. */
        public Object input;
        /** Outcome from the current contract. */
        public Outcome.FlowOutcome current;
        /** Outcome from the candidate contract. */
        public Outcome.FlowOutcome candidate;
        /** Whether the outcomes differ. */
        public boolean differs;
        /** Names of differing outcome fields. */
        public List<String> differingFields = new ArrayList<>();
    }

    /** Shadow comparison report (SPEC 12.7). */
    public static final class ShadowReport {
        /** Per-input comparison entries. */
        public List<ShadowEntry> entries = new ArrayList<>();
        /** Total inputs compared. */
        public int total;
        /** Number of inputs where outcomes differ. */
        public int differences;
    }

    static List<String> diffFields(Outcome.FlowOutcome a, Outcome.FlowOutcome b) {
        List<String> fields = new ArrayList<>();
        if (a.executionStatus != b.executionStatus) fields.add("execution_status");
        if (a.decisionStatus != b.decisionStatus) fields.add("decision_status");
        if (!Objects.equals(a.value, b.value)) fields.add("value");
        if ((a.recovery == null) != (b.recovery == null)) fields.add("recovery");
        String ka = a.interruption != null ? a.interruption.kind.name() : null;
        String kb = b.interruption != null ? b.interruption.kind.name() : null;
        if (!Objects.equals(ka, kb)) fields.add("interruption");
        return fields;
    }

    /** Compare a candidate contract against the current one over inputs (SPEC 12.7). */
    public static ShadowReport shadow(Flow.FlowContract current, Flow.FlowContract candidate,
            List<Object> inputs) {
        return shadow(current, candidate, inputs, null);
    }

    /** Shadow with an optional clock for deterministic comparison (SPEC 12.7). */
    public static ShadowReport shadow(Flow.FlowContract current, Flow.FlowContract candidate,
            List<Object> inputs, Clock clock) {
        ShadowReport report = new ShadowReport();
        for (int i = 0; i < inputs.size(); i++) {
            Object inp = inputs.get(i);
            Outcome.FlowOutcome co = clock != null ? current.simulateWithClock(inp, clock) : current.simulate(inp);
            Outcome.FlowOutcome cand = clock != null ? candidate.simulateWithClock(inp, clock) : candidate.simulate(inp);
            ShadowEntry e = new ShadowEntry();
            e.index = i; e.input = inp; e.current = co; e.candidate = cand;
            e.differingFields = diffFields(co, cand);
            e.differs = !e.differingFields.isEmpty();
            report.entries.add(e);
            if (e.differs) report.differences++;
        }
        report.total = report.entries.size();
        return report;
    }
}
