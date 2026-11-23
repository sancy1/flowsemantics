using System.Globalization;

namespace FlowSemantics;

/// Advanced composition &amp; analysis — SPEC 10.7 (merge), 10.8 (decision
/// table), 12.5 (simulate batch), 4.4 (portability report), 12.9
/// (effective-date parsing).
public static class Advanced
{
    /// Parse an ISO-8601 effective-date string into epoch ms; null/empty → null.
    public static long? ParseEffective(string? s)
    {
        if (string.IsNullOrEmpty(s)) return null;
        return DateTimeOffset.Parse(s, CultureInfo.InvariantCulture,
            DateTimeStyles.RoundtripKind).ToUnixTimeMilliseconds();
    }

    // --- Merge (SPEC 10.7) -------------------------------------------------

    /// Splice another flow's rules, catches, hooks, and finalizers at the
    /// call site. Modes must match; RuleIds must be unique; the outer
    /// (self) fallback wins when both flows define one.
    public static Flow Merge(Flow self, Flow other)
    {
        if (self.Mode != other.Mode)
            throw new StructureError(
                $"cannot merge flows with different EvaluationMode: {self.Mode} vs {other.Mode} (SPEC 10.7)");
        var existing = new HashSet<string>();
        foreach (var r in self.Rules) existing.Add(r.Id);
        foreach (var r in other.Rules)
            if (!existing.Add(r.Id))
                throw new StructureError($"merge would produce duplicate RuleId: {r.Id} (SPEC 10.7)");
        self.Rules.AddRange(other.Rules);
        self.Catches.AddRange(other.Catches);
        self.Hooks.AddRange(other.Hooks);
        self.Finalizers.AddRange(other.Finalizers);
        if (self.FallbackRule is null && other.FallbackRule is not null) self.FallbackRule = other.FallbackRule;
        return self;
    }

    /// Splice a compiled FlowContract's rules, catches, hooks, and
    /// finalizers at the call site (SPEC 10.7). Same mode/uniqueness
    /// rules as Merge.
    public static Flow MergeContract(Flow self, Flow.FlowContract other)
    {
        if (self.Mode != other.Mode)
            throw new StructureError(
                $"cannot merge flows with different EvaluationMode: {self.Mode} vs {other.Mode} (SPEC 10.7)");
        var existing = new HashSet<string>();
        foreach (var r in self.Rules) existing.Add(r.Id);
        foreach (var r in other.Rules)
            if (!existing.Add(r.Id))
                throw new StructureError($"merge would produce duplicate RuleId: {r.Id} (SPEC 10.7)");
        self.Rules.AddRange(other.Rules);
        self.Catches.AddRange(other.Catches);
        self.Hooks.AddRange(other.Hooks);
        self.Finalizers.AddRange(other.Finalizers);
        if (self.FallbackRule is null && other.Fallback is not null) self.FallbackRule = other.Fallback;
        return self;
    }

    // --- DecisionTable (SPEC 10.8) -----------------------------------------

    /// Hit policy for a decision table (SPEC 10.8).
    public enum HitPolicy { FIRST, COLLECT, PRIORITY, UNIQUE }

    /// One row of a decision table (SPEC 10.8).
    public sealed record DecisionTableRow(string Id, List<Flow.ConditionFn> Conditions,
        Flow.ActionFn Action, int Priority = 0);

    /// A decision table: rows of conditions + action with a hit policy (SPEC 10.8).
    public sealed class DecisionTable
    {
        /// Table rows in declaration order.
        public required List<DecisionTableRow> Rows { get; init; }
        /// Hit policy determining the evaluation mode.
        public HitPolicy Policy { get; init; } = HitPolicy.FIRST;
        /// Declared input field names (documentation only).
        public List<string> InputFields { get; init; } = new();
        /// Static-analysis warnings (e.g. unreachable rows).
        public List<string> Warnings { get; init; } = new();
    }

    /// Compile a DecisionTable into a Flow builder (SPEC 10.8).
    public static Flow TableToFlow(DecisionTable table)
    {
        if (table.Rows.Count == 0)
            throw new StructureError("decision table must have at least one row");
        var mode = table.Policy switch
        {
            HitPolicy.FIRST or HitPolicy.UNIQUE => EvaluationMode.FirstMatch,
            HitPolicy.COLLECT => EvaluationMode.AllMatch,
            HitPolicy.PRIORITY => EvaluationMode.Priority,
            _ => throw new StructureError($"unknown hit policy: {table.Policy}"),
        };
        var flow = Flow.Create().WithMode(mode);
        for (var i = 0; i < table.Rows.Count; i++)
        {
            var row = table.Rows[i];
            var id = !string.IsNullOrEmpty(row.Id) ? row.Id : $"row{i}";
            var conds = row.Conditions;
            Flow.ConditionFn combined = input =>
            {
                foreach (var c in conds) if (!c(input)) return false;
                return true;
            };
            flow.When(combined, row.Action, id, priority: row.Priority);
        }
        return flow;
    }

    // --- Simulate batch (SPEC 12.5) ----------------------------------------

    /// Firing-distribution report from batch simulation (SPEC 12.5).
    public sealed class SimulateReport
    {
        /// Number of inputs evaluated.
        public required int Total { get; init; }
        /// Count by execution status.
        public Dictionary<string, int> ByStatus { get; } = new();
        /// Count by decision status.
        public Dictionary<string, int> ByDecision { get; } = new();
        /// Count by produced value.
        public Dictionary<string, int> ByValue { get; } = new();
        /// Individual outcomes in input order.
        public List<FlowOutcome> Outcomes { get; } = new();
    }

    /// Evaluate representative inputs with no side effects, producing a
    /// firing distribution report (SPEC 12.5).
    public static SimulateReport SimulateBatch(Flow.FlowContract contract, List<object?> inputs)
    {
        var rep = new SimulateReport { Total = inputs.Count };
        foreach (var input in inputs)
        {
            var o = contract.Simulate(input);
            rep.Outcomes.Add(o);
            var s = o.ExecutionStatus.ToString();
            rep.ByStatus[s] = rep.ByStatus.GetValueOrDefault(s) + 1;
            var d = o.DecisionStatus?.ToString() ?? "null";
            rep.ByDecision[d] = rep.ByDecision.GetValueOrDefault(d) + 1;
            var v = o.Value?.ToString() ?? "null";
            rep.ByValue[v] = rep.ByValue.GetValueOrDefault(v) + 1;
        }
        return rep;
    }

    // --- Portability report (SPEC 4.4) -------------------------------------

    /// Returns (classification, offenders): "PORTABLE" with empty
    /// offenders, or "NATIVE" naming the components that make it native.
    public static (string Classification, string Offenders) Portability(Flow.FlowContract contract)
    {
        if (!contract.HasPortable) return ("NATIVE", "native rules");
        var offenders = new List<string>();
        if (contract.Catches.Count > 0) offenders.Add("catches");
        if (contract.Finalizers.Count > 0) offenders.Add("finalizers");
        if (contract.Hooks.Count > 0) offenders.Add("hooks");
        return offenders.Count == 0 ? ("PORTABLE", "") : ("NATIVE", string.Join(",", offenders));
    }
}
