using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;

namespace FlowSemantics;

/// Trust layer — SPEC 12.4-12.10: contract versioning, explain,
/// validate, replay (4 modes), shadow.
public static class Trust
{
    /// SPEC version this implementation conforms to.
    public const string SpecVersion = "0.1.0";

    // --- Contract version (SPEC 12.9, algorithm v1) ---

    internal static string ContractVersion(
        IReadOnlyList<Flow.Rule> rules, Flow.Fallback? fallback,
        EvaluationMode mode, IReadOnlyList<Flow.CatchRule> catches,
        int finalizerCount, FinallyFailurePolicy policy,
        long finallyTimeoutMs, bool traceEnabled,
        IReadOnlyList<Portable.PortableRule>? portableRules = null)
    {
        var prs = portableRules ?? Array.Empty<Portable.PortableRule>();
        var ruleList = rules.Select((r, i) =>
        {
            var pr = i < prs.Count ? prs[i] : null;
            return (object)new Dictionary<string, object?>
            {
                ["id"] = r.Id, ["kind"] = r.Kind, ["priority"] = r.Priority,
                ["effective_from"] = r.EffectiveFrom, ["effective_until"] = r.EffectiveUntil,
                ["native"] = pr is null,
                ["condition"] = pr?.Condition is not null ? Portable.ExprToNode(pr.Condition) : null,
                ["guard"] = pr?.Guard is not null ? Portable.ExprToNode(pr.Guard) : null,
                ["transform"] = pr?.Transform is not null ? Portable.ExprToNode(pr.Transform) : null,
                ["effects"] = r.Effects.Select(e => (object)new Dictionary<string, object?>
                {
                    ["name"] = e.Name, ["payload"] = e.Payload,
                }).ToList(),
            };
        }).ToList();
        var payload = new Dictionary<string, object?>
        {
            ["algorithm"] = "flowsemantics-contract-v2",
            ["rules"] = ruleList,
            ["fallback"] = fallback?.Kind,
            ["mode"] = mode.ToString(),
            ["catches"] = catches.Select(c => (object)c.Kind).ToList(),
            ["finalizer_count"] = finalizerCount,
            ["finally_policy"] = policy.ToString(),
            ["finally_timeout_ms"] = finallyTimeoutMs,
            ["trace_enabled"] = traceEnabled,
        };
        var canonical = CanonicalJson.Write(payload);
        var hash = SHA256.HashData(Encoding.UTF8.GetBytes(canonical));
        return Convert.ToHexString(hash)[..32].ToLowerInvariant();
    }

    // --- Canonical JSON (sorted keys, no whitespace) ---

    internal static class CanonicalJson
    {
        public static string Write(object? v)
        {
            var sb = new StringBuilder();
            WriteValue(sb, v);
            return sb.ToString();
        }

        static void WriteValue(StringBuilder sb, object? v)
        {
            switch (v)
            {
                case null: sb.Append("null"); break;
                case string s: sb.Append('"').Append(Escape(s)).Append('"'); break;
                case bool b: sb.Append(b ? "true" : "false"); break;
                case JsonNode jn: WriteValue(sb, Portable.ToClr(jn)); break;
                case System.Text.Json.JsonElement je: WriteValue(sb, je); break;
                case IDictionary<string, object?> d:
                    sb.Append('{');
                    var keys = d.Keys.OrderBy(k => k, StringComparer.Ordinal).ToList();
                    for (var i = 0; i < keys.Count; i++)
                    {
                        if (i > 0) sb.Append(',');
                        sb.Append('"').Append(Escape(keys[i])).Append("\":");
                        WriteValue(sb, d[keys[i]]);
                    }
                    sb.Append('}');
                    break;
                case IEnumerable<object?> list when v is not string:
                    sb.Append('[');
                    var first = true;
                    foreach (var item in list)
                    {
                        if (!first) sb.Append(',');
                        first = false;
                        WriteValue(sb, item);
                    }
                    sb.Append(']');
                    break;
                case IEnumerable<object> list2:
                    sb.Append('[');
                    var f2 = true;
                    foreach (var item in list2)
                    {
                        if (!f2) sb.Append(',');
                        f2 = false;
                        WriteValue(sb, item);
                    }
                    sb.Append(']');
                    break;
                default:
                    if (v is IFormattable f) { sb.Append(f.ToString(null, System.Globalization.CultureInfo.InvariantCulture)); break; }
                    sb.Append('"').Append(Escape(v.ToString()!)).Append('"');
                    break;
            }
        }

        static void WriteValue(StringBuilder sb, System.Text.Json.JsonElement je)
        {
            switch (je.ValueKind)
            {
                case System.Text.Json.JsonValueKind.Object:
                    sb.Append('{');
                    var props = je.EnumerateObject().OrderBy(p => p.Name, StringComparer.Ordinal).ToList();
                    for (var i = 0; i < props.Count; i++)
                    {
                        if (i > 0) sb.Append(',');
                        sb.Append('"').Append(Escape(props[i].Name)).Append("\":");
                        WriteValue(sb, props[i].Value);
                    }
                    sb.Append('}');
                    break;
                case System.Text.Json.JsonValueKind.Array:
                    sb.Append('[');
                    var ai = 0;
                    foreach (var item in je.EnumerateArray())
                    {
                        if (ai++ > 0) sb.Append(',');
                        WriteValue(sb, item);
                    }
                    sb.Append(']');
                    break;
                case System.Text.Json.JsonValueKind.String:
                    sb.Append('"').Append(Escape(je.GetString()!)).Append('"');
                    break;
                case System.Text.Json.JsonValueKind.True: sb.Append("true"); break;
                case System.Text.Json.JsonValueKind.False: sb.Append("false"); break;
                case System.Text.Json.JsonValueKind.Null: sb.Append("null"); break;
                default: sb.Append(je.GetRawText()); break;
            }
        }

        static string Escape(string s)
        {
            var sb = new StringBuilder(s.Length + 8);
            foreach (var c in s)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default: sb.Append(c); break;
                }
            }
            return sb.ToString();
        }
    }

    // --- Validation (SPEC 12.8) ---

    /// A static-analysis finding (SPEC 12.8).
    public sealed record ValidationIssue(string Severity, string Code, string Message, string RuleId);

    /// Perform static analysis on a contract without executing it (SPEC 12.8).
    public static List<ValidationIssue> Validate(Flow.FlowContract c)
    {
        var issues = new List<ValidationIssue>();
        if (c.Rules.Count == 0 && c.Fallback is null)
            issues.Add(new ValidationIssue("error", "empty_flow",
                "flow has neither rules nor a fallback", ""));
        var seen = new HashSet<string>();
        foreach (var r in c.Rules)
            if (!seen.Add(r.Id))
                issues.Add(new ValidationIssue("error", "duplicate_rule_id",
                    "duplicate RuleId: " + r.Id, r.Id));
        var seenAny = false;
        foreach (var cr in c.Catches)
        {
            if (cr.Kind == "any") seenAny = true;
            else if (seenAny && (cr.Kind == "typed" || cr.Kind == "when"))
                issues.Add(new ValidationIssue("error", "catch_any_ordering",
                    "typed catch registered after catch_any", ""));
        }
        // effective date inversion (SPEC 12.9)
        foreach (var r in c.Rules)
            if (r.EffectiveFrom is not null && r.EffectiveUntil is not null && r.EffectiveFrom >= r.EffectiveUntil)
                issues.Add(new ValidationIssue("error", "invalid_effective_window",
                    "effective_from must be before effective_until", r.Id));
        // unreachable rules: provable only for portable const-true (SPEC 12.8)
        if (c.Mode != EvaluationMode.AllMatch && c.HasPortable)
        {
            var unconditional = false;
            for (var i = 0; i < c.Rules.Count; i++)
            {
                var r = c.Rules[i];
                if (r.Kind == "then") continue;
                if (unconditional)
                {
                    issues.Add(new ValidationIssue("warning", "unreachable_rule",
                        "rule cannot match: an earlier unconditional rule always matches first", r.Id));
                    continue;
                }
                if (i < c.PortableRules.Count && c.PortableRules[i].Condition is { } pc &&
                    pc.Op == "const" && pc.Value is true)
                    unconditional = true;
            }
        }
        // overlap warning: identical portable conditions. O(n) grouping
        // by (kind, canonical condition JSON); pairwise compare only
        // within each group (SPEC 12.8).
        if (c.HasPortable)
        {
            var groups = new Dictionary<string, List<int>>();
            for (var i = 0; i < c.PortableRules.Count; i++)
            {
                var pr = c.PortableRules[i];
                var condJson = pr.Condition is not null
                    ? CanonicalJson.Write(Portable.ExprToNode(pr.Condition)) : "null";
                var key = pr.Kind + "\u0000" + condJson;
                if (!groups.TryGetValue(key, out var list)) { list = new List<int>(); groups[key] = list; }
                list.Add(i);
            }
            foreach (var idxs in groups.Values)
                for (var a = 0; a < idxs.Count; a++)
                    for (var b = a + 1; b < idxs.Count; b++)
                        issues.Add(new ValidationIssue("warning", "overlapping_rules",
                            "rules have structurally identical conditions", c.PortableRules[idxs[b]].RuleId));
        }
        // gap warning
        if (c.Fallback is null && c.Rules.Count > 0)
            issues.Add(new ValidationIssue("warning", "possible_gap",
                "no fallback configured; some inputs may produce NO_MATCH", ""));
        return issues;
    }

    static bool ExprEqual(Portable.PExpr? a, Portable.PExpr? b)
    {
        if (ReferenceEquals(a, b)) return true;
        if (a is null || b is null) return false;
        if (a.Op != b.Op) return false;
        if (!Equals(a.Value, b.Value)) return false;
        if (a.Args.Count != b.Args.Count) return false;
        for (var i = 0; i < a.Args.Count; i++)
            if (!ExprEqual(a.Args[i], b.Args[i])) return false;
        return true;
    }

    // --- Explain (SPEC 12.4) ---

    /// Render an execution trace as human-readable lines (SPEC 12.4).
    public static string Explain(Flow.FlowContract c, ExecutionTrace trace)
    {
        var sb = new StringBuilder();
        sb.Append("FlowContract ").Append(c.ContractVersion)
          .Append(": ").Append(trace.Events.Count).Append(" event(s)\n");
        foreach (var e in trace.Events)
        {
            var rid = e.RuleId ?? "-";
            var reason = e.Reason is not null ? " (" + e.Reason + ")" : "";
            sb.Append("  [").Append(e.Type).Append("] rule=").Append(rid).Append(reason).Append('\n');
        }
        return sb.ToString().TrimEnd('\n');
    }

    // --- Replay (SPEC 12.6) ---

    /// The four replay operations (SPEC 12.6).
    public enum ReplayMode { Simulation, Historical, Decision, Effects }

    /// Raised when a replay record cannot be safely replayed.
    public sealed class ReplayError : Exception
    {
        /// Create a ReplayError with the given message.
        public ReplayError(string msg) : base(msg) { }
    }

    /// A recorded decision tuple (SPEC 12.6, 12.10).
    public sealed class ReplayRecord
    {
        /// SPEC version that produced the record.
        public required string SpecVersion { get; set; }
        /// Contract version that produced the record.
        public required string ContractVersion { get; set; }
        /// Recorded input.
        public object? Input { get; set; }
        /// Recorded wall-clock time (epoch ms).
        public long ClockWall { get; set; }
        /// Recorded monotonic time (ms).
        public long ClockMonotonic { get; set; }
        /// Recorded outcome.
        public required FlowOutcome Outcome { get; set; }
        /// Recorded trace, if collected.
        public ExecutionTrace? Trace { get; set; }
        /// Recorded proposed effects.
        public List<Effect> Effects { get; set; } = new();
        /// Optional HMAC-SHA256 integrity tag.
        public string? Integrity { get; set; }
    }

    /// Result of a replay operation (SPEC 12.6).
    public sealed class ReplayResult
    {
        /// The replay mode used.
        public required ReplayMode Mode { get; set; }
        /// Replayed or recorded outcome.
        public FlowOutcome? Outcome { get; set; }
        /// Semantic equivalence vs the recorded outcome (DECISION mode).
        public bool? Equivalent { get; set; }
        /// Number of effects applied (EFFECTS mode).
        public int EffectsApplied { get; set; }
    }

    static Dictionary<string, object?> CanonicalPayload(ReplayRecord rec) => new()
    {
        ["spec_version"] = rec.SpecVersion,
        ["contract_version"] = rec.ContractVersion,
        ["input"] = rec.Input,
        ["clock_wall"] = rec.ClockWall,
        ["clock_monotonic"] = rec.ClockMonotonic,
        ["outcome"] = new Dictionary<string, object?>
        {
            ["execution_status"] = rec.Outcome.ExecutionStatus.ToString(),
            ["decision_status"] = rec.Outcome.DecisionStatus?.ToString(),
            ["value"] = rec.Outcome.Value,
            ["has_recovery"] = rec.Outcome.Recovery is not null,
            ["interruption_kind"] = rec.Outcome.Interruption?.Kind.ToString(),
        },
        ["effects"] = rec.Effects.Select(e => (object)new Dictionary<string, object?>
        {
            ["name"] = e.Name, ["payload"] = e.Payload,
        }).ToList(),
    };

    static string HmacSha256Hex(byte[] key, string data)
    {
        using var hmac = new HMACSHA256(key);
        return Convert.ToHexString(hmac.ComputeHash(Encoding.UTF8.GetBytes(data))).ToLowerInvariant();
    }

    /// Return a copy of the record with an HMAC-SHA256 integrity tag (SPEC 9.5).
    public static ReplayRecord Sign(ReplayRecord rec, byte[] key)
    {
        var cp = new ReplayRecord
        {
            SpecVersion = rec.SpecVersion, ContractVersion = rec.ContractVersion,
            Input = rec.Input, ClockWall = rec.ClockWall, ClockMonotonic = rec.ClockMonotonic,
            Outcome = rec.Outcome, Trace = rec.Trace, Effects = rec.Effects,
        };
        cp.Integrity = HmacSha256Hex(key, CanonicalJson.Write(CanonicalPayload(rec)));
        return cp;
    }

    /// Execute with tracing and capture a ReplayRecord (SPEC 12.6).
    public static ReplayRecord Record(Flow.FlowContract c, object? input, IClock? clock)
    {
        clock ??= c.ClockRef;
        var outcome = c.TryExecute(input, clock, true);
        return new ReplayRecord
        {
            SpecVersion = SpecVersion, ContractVersion = c.ContractVersion,
            Input = input, ClockWall = clock.Wall(), ClockMonotonic = clock.Monotonic(),
            Outcome = outcome, Trace = outcome.Trace, Effects = outcome.Effects,
        };
    }

    static void VerifyIntegrity(ReplayRecord rec, byte[]? key)
    {
        if (rec.Integrity is null) return;
        if (key is null) throw new ReplayError("record carries an integrity tag; an integrity_key is required");
        var expected = HmacSha256Hex(key, CanonicalJson.Write(CanonicalPayload(rec)));
        var expectedBytes = Convert.FromHexString(expected);
        byte[]? actualBytes = null;
        try { actualBytes = Convert.FromHexString(rec.Integrity); } catch (FormatException) { }
        if (actualBytes is null || actualBytes.Length != expectedBytes.Length ||
            !CryptographicOperations.FixedTimeEquals(actualBytes, expectedBytes))
            throw new ReplayError("replay record integrity check failed");
    }

    static void CheckVersions(ReplayRecord rec, Flow.FlowContract c)
    {
        if (rec.SpecVersion != SpecVersion)
            throw new ReplayError("record spec_version does not match current; replay fails closed (SPEC 9.5)");
        if (rec.ContractVersion != c.ContractVersion)
            throw new ReplayError("record contract_version does not match the current contract; replay fails closed (SPEC 12.6)");
    }

    static bool SemanticallyEquivalent(FlowOutcome a, FlowOutcome b)
    {
        if (a.ExecutionStatus != b.ExecutionStatus) return false;
        if (a.DecisionStatus != b.DecisionStatus) return false;
        if (!Equals(a.Value, b.Value)) return false;
        if ((a.Recovery is null) != (b.Recovery is null)) return false;
        if (a.Recovery is not null && b.Recovery is not null &&
            a.Recovery.HandlerRuleId != b.Recovery.HandlerRuleId) return false;
        var ka = a.Interruption?.Kind.ToString();
        var kb = b.Interruption?.Kind.ToString();
        return ka == kb;
    }

    /// Callback that applies a recorded effect (EFFECTS replay mode only).
    public delegate void EffectExecutor(Effect effect);

    /// Replay a recorded decision (SPEC 12.6). Fails closed on version or
    /// integrity mismatch; EFFECTS mode requires explicit authorization.
    public static ReplayResult Replay(ReplayRecord rec, Flow.FlowContract c, ReplayMode mode,
        byte[]? integrityKey, EffectExecutor? executor, bool authorizeEffects)
    {
        VerifyIntegrity(rec, integrityKey);
        CheckVersions(rec, c);
        var res = new ReplayResult { Mode = mode };
        switch (mode)
        {
            case ReplayMode.Historical:
                res.Outcome = rec.Outcome;
                return res;
            case ReplayMode.Simulation:
            case ReplayMode.Decision:
                var clk = new FakeClock(rec.ClockWall, rec.ClockMonotonic);
                var outcome = c.SimulateWithClock(rec.Input, clk);
                res.Outcome = outcome;
                res.Equivalent = SemanticallyEquivalent(outcome, rec.Outcome);
                return res;
            case ReplayMode.Effects:
                if (!authorizeEffects) throw new ReplayError("effect re-execution requires explicit authorization");
                if (executor is null) throw new ReplayError("EFFECTS mode requires an effect_executor");
                var applied = 0;
                foreach (var e in rec.Effects) { executor(e); applied++; }
                res.EffectsApplied = applied;
                return res;
            default:
                throw new ReplayError("unknown replay mode: " + mode);
        }
    }

    // --- Portable IR export (SPEC 14.2) ---

    /// Export a PORTABLE contract as a PortableFlow IR document (SPEC 14.2).
    public static Portable.PortableFlow ToIR(Flow.FlowContract c)
    {
        if (!c.HasPortable)
            throw new StructureError("contract is NATIVE; only PORTABLE contracts can be exported to the Portable IR (SPEC 14.2)");
        var pf = new Portable.PortableFlow
        {
            SpecVersion = SpecVersion,
            FlowId = c.FlowId ?? "flow",
            Portability = "PORTABLE", Mode = c.Mode,
            ContractVersion = c.ContractVersion,
        };
        foreach (var r in c.PortableRules) pf.Rules.Add(r);
        return pf;
    }

    /// Export a PORTABLE contract as canonical Portable IR JSON (SPEC 14.2).
    public static string ToIRJSON(Flow.FlowContract c) =>
        Portable.PortableFlowToJSON(ToIR(c));

    static string ExprJSON(Portable.PExpr e)
    {
        var sb = new StringBuilder();
        sb.Append("{\"op\":\"").Append(e.Op).Append("\"");
        if (e.Args.Count > 0)
        {
            sb.Append(",\"args\":[");
            for (var i = 0; i < e.Args.Count; i++)
            {
                if (i > 0) sb.Append(',');
                sb.Append(ExprJSON(e.Args[i]));
            }
            sb.Append(']');
        }
        if (e.Value is not null)
        {
            sb.Append(",\"value\":");
            if (e.Value is string s) sb.Append('"').Append(s).Append('"');
            else if (e.Value is bool b) sb.Append(b ? "true" : "false");
            else sb.Append(e.Value);
        }
        sb.Append('}');
        return sb.ToString();
    }

    // --- Shadow (SPEC 12.7) ---

    /// One shadow-comparison entry (SPEC 12.7).
    public sealed class ShadowEntry
    {
        /// Input index.
        public int Index { get; set; }
        /// The input evaluated.
        public object? Input { get; set; }
        /// Outcome from the current contract.
        public required FlowOutcome Current { get; set; }
        /// Outcome from the candidate contract.
        public required FlowOutcome Candidate { get; set; }
        /// Whether the outcomes differ.
        public bool Differs { get; set; }
        /// Names of differing outcome fields.
        public List<string> DifferingFields { get; set; } = new();
    }

    /// Shadow comparison report (SPEC 12.7).
    public sealed class ShadowReport
    {
        /// Per-input comparison entries.
        public List<ShadowEntry> Entries { get; } = new();
        /// Total inputs compared.
        public int Total => Entries.Count;
        /// Number of inputs where outcomes differ.
        public int Differences => Entries.Count(e => e.Differs);
    }

    static List<string> DiffFields(FlowOutcome a, FlowOutcome b)
    {
        var fields = new List<string>();
        if (a.ExecutionStatus != b.ExecutionStatus) fields.Add("execution_status");
        if (a.DecisionStatus != b.DecisionStatus) fields.Add("decision_status");
        if (!Equals(a.Value, b.Value)) fields.Add("value");
        if ((a.Recovery is null) != (b.Recovery is null)) fields.Add("recovery");
        var ka = a.Interruption?.Kind.ToString();
        var kb = b.Interruption?.Kind.ToString();
        if (ka != kb) fields.Add("interruption");
        return fields;
    }

    /// Compare a candidate contract against the current one over inputs (SPEC 12.7).
    public static ShadowReport Shadow(Flow.FlowContract current, Flow.FlowContract candidate, IEnumerable<object?> inputs)
        => Shadow(current, candidate, inputs, null);

    /// Shadow with an optional clock for deterministic comparison (SPEC 12.7).
    public static ShadowReport Shadow(Flow.FlowContract current, Flow.FlowContract candidate,
        IEnumerable<object?> inputs, IClock? clock)
    {
        var report = new ShadowReport();
        var i = 0;
        foreach (var inp in inputs)
        {
            var co = clock is not null ? current.SimulateWithClock(inp, clock) : current.Simulate(inp);
            var cand = clock is not null ? candidate.SimulateWithClock(inp, clock) : candidate.Simulate(inp);
            var fields = DiffFields(co, cand);
            report.Entries.Add(new ShadowEntry
            {
                Index = i++, Input = inp, Current = co, Candidate = cand,
                Differs = fields.Count > 0, DifferingFields = fields,
            });
        }
        return report;
    }
}
