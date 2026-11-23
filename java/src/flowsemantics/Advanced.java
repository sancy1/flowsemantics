package flowsemantics;

import java.time.Instant;
import java.util.*;

/** Advanced composition and analysis — SPEC 10.7 (merge), 10.8 (decision
 *  table), 12.5 (simulate batch), 4.4 (portability report), 12.9
 *  (effective-date parsing). */
public final class Advanced {

    /** Parse an ISO-8601 effective-date string into epoch ms; null/empty → null. */
    public static Long parseEffective(String s) {
        if (s == null || s.isEmpty()) return null;
        return Instant.parse(s).toEpochMilli();
    }

    // --- Merge (SPEC 10.7) -------------------------------------------------

    /** Splice another flow's rules, catches, hooks, and finalizers at the
     *  call site. Modes must match; RuleIds must be unique; the outer
     *  (self) fallback wins when both flows define one. */
    public static Flow merge(Flow self, Flow other) {
        if (self.mode != other.mode) {
            throw new FlowErrors.StructureError(
                "cannot merge flows with different EvaluationMode: " + self.mode + " vs " + other.mode + " (SPEC 10.7)");
        }
        Set<String> existing = new HashSet<>();
        for (Flow.Rule r : self.rules) existing.add(r.id);
        for (Flow.Rule r : other.rules) {
            if (!existing.add(r.id)) {
                throw new FlowErrors.StructureError("merge would produce duplicate RuleId: " + r.id + " (SPEC 10.7)");
            }
        }
        self.rules.addAll(other.rules);
        self.catches.addAll(other.catches);
        self.hooks.addAll(other.hooks);
        self.finalizers.addAll(other.finalizers);
        if (self.fallback == null && other.fallback != null) self.fallback = other.fallback;
        return self;
    }

    /** Splice a compiled FlowContract's rules, catches, hooks, and
     *  finalizers at the call site (SPEC 10.7). Same mode/uniqueness
     *  rules as merge(Flow, Flow). */
    public static Flow mergeContract(Flow self, Flow.FlowContract other) {
        if (self.mode != other.mode) {
            throw new FlowErrors.StructureError(
                "cannot merge flows with different EvaluationMode: " + self.mode + " vs " + other.mode + " (SPEC 10.7)");
        }
        Set<String> existing = new HashSet<>();
        for (Flow.Rule r : self.rules) existing.add(r.id);
        for (Flow.Rule r : other.rules) {
            if (!existing.add(r.id)) {
                throw new FlowErrors.StructureError("merge would produce duplicate RuleId: " + r.id + " (SPEC 10.7)");
            }
        }
        self.rules.addAll(other.rules);
        self.catches.addAll(other.catches);
        self.hooks.addAll(other.hooks);
        self.finalizers.addAll(other.finalizers);
        if (self.fallback == null && other.fallback != null) self.fallback = other.fallback;
        return self;
    }

    // --- DecisionTable (SPEC 10.8) -----------------------------------------

    /** Hit policy for a decision table (SPEC 10.8). */
    public enum HitPolicy { FIRST, COLLECT, PRIORITY, UNIQUE }

    /** One row of a decision table (SPEC 10.8). */
    public static final class DecisionTableRow {
        /** Row identifier. */
        public final String id;
        /** Condition callbacks; all must hold for the row to match. */
        public final List<Flow.ConditionFn> conditions;
        /** Action callback producing the row's value. */
        public final Flow.ActionFn action;
        /** Evaluation priority (used by PRIORITY policy). */
        public final int priority;
        /** Create a DecisionTableRow. */
        public DecisionTableRow(String id, List<Flow.ConditionFn> conditions,
                                Flow.ActionFn action, int priority) {
            this.id = id; this.conditions = conditions; this.action = action; this.priority = priority;
        }
    }

    /** A decision table: rows of conditions + action with a hit policy (SPEC 10.8). */
    public static final class DecisionTable {
        /** Table rows in declaration order. */
        public final List<DecisionTableRow> rows;
        /** Hit policy determining the evaluation mode. */
        public final HitPolicy policy;
        /** Declared input field names (documentation only). */
        public final List<String> inputFields;
        /** Static-analysis warnings (e.g. unreachable rows). */
        public final List<String> warnings;
        /** Create a DecisionTable with rows and policy. */
        public DecisionTable(List<DecisionTableRow> rows, HitPolicy policy) {
            this(rows, policy, List.of(), List.of());
        }
        /** Create a DecisionTable with rows, policy, input fields, and warnings. */
        public DecisionTable(List<DecisionTableRow> rows, HitPolicy policy,
                             List<String> inputFields, List<String> warnings) {
            if (rows.isEmpty()) throw new FlowErrors.StructureError("decision table must have at least one row");
            this.rows = rows; this.policy = policy;
            this.inputFields = inputFields; this.warnings = warnings;
        }
    }

    /** Compile a DecisionTable into a Flow builder (SPEC 10.8). */
    public static Flow tableToFlow(DecisionTable table) {
        Outcome.EvaluationMode mode = switch (table.policy) {
            case FIRST, UNIQUE -> Outcome.EvaluationMode.FirstMatch;
            case COLLECT -> Outcome.EvaluationMode.AllMatch;
            case PRIORITY -> Outcome.EvaluationMode.Priority;
        };
        Flow flow = Flow.create().withMode(mode);
        for (int i = 0; i < table.rows.size(); i++) {
            DecisionTableRow row = table.rows.get(i);
            String id = row.id != null && !row.id.isEmpty() ? row.id : "row" + i;
            List<Flow.ConditionFn> conds = row.conditions;
            Flow.ConditionFn combined = input -> {
                for (Flow.ConditionFn c : conds) {
                    if (!c.test(input)) return false;
                }
                return true;
            };
            flow.when(combined, row.action, id, null, row.priority, null);
        }
        return flow;
    }

    // --- Simulate batch (SPEC 12.5) ----------------------------------------

    /** Firing-distribution report from batch simulation (SPEC 12.5). */
    public static final class SimulateReport {
        /** Number of inputs evaluated. */
        public final int total;
        /** Count by execution status. */
        public final Map<String, Integer> byStatus = new LinkedHashMap<>();
        /** Count by decision status. */
        public final Map<String, Integer> byDecision = new LinkedHashMap<>();
        /** Count by produced value. */
        public final Map<String, Integer> byValue = new LinkedHashMap<>();
        /** Individual outcomes in input order. */
        public final List<Outcome.FlowOutcome> outcomes = new ArrayList<>();
        SimulateReport(int total) { this.total = total; }
    }

    /** Evaluate representative inputs with no side effects, producing a
     *  firing distribution report (SPEC 12.5). */
    public static SimulateReport simulateBatch(Flow.FlowContract contract, List<Object> inputs) {
        SimulateReport rep = new SimulateReport(inputs.size());
        for (Object in : inputs) {
            Outcome.FlowOutcome o = contract.simulate(in);
            rep.outcomes.add(o);
            rep.byStatus.merge(String.valueOf(o.executionStatus), 1, Integer::sum);
            String d = o.decisionStatus == null ? "null" : o.decisionStatus.name();
            rep.byDecision.merge(d, 1, Integer::sum);
            rep.byValue.merge(String.valueOf(o.value), 1, Integer::sum);
        }
        return rep;
    }

    // --- Portability report (SPEC 4.4) -------------------------------------

    /** Returns {classification, offenders}: "PORTABLE" with empty
     *  offenders, or "NATIVE" naming the components that make it native. */
    public static String[] portability(Flow.FlowContract contract) {
        if (!contract.hasPortable) return new String[]{"NATIVE", "native rules"};
        List<String> offenders = new ArrayList<>();
        if (!contract.catches.isEmpty()) offenders.add("catches");
        if (!contract.finalizers.isEmpty()) offenders.add("finalizers");
        if (!contract.hooks.isEmpty()) offenders.add("hooks");
        if (offenders.isEmpty()) return new String[]{"PORTABLE", ""};
        return new String[]{"NATIVE", String.join(",", offenders)};
    }
}
