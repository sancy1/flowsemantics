using System.Text.Json;
using System.Text.Json.Nodes;

namespace FlowSemantics;

/// Portable IR — SPEC 14.2, 9.2.
public static class Portable
{
    /// Maximum expression nesting depth (SPEC 9.2).
    public const int MaxExprDepth = 100;
    /// Maximum portable IR size in bytes (SPEC 9.2).
    public const int MaxIRBytes = 1_000_000;
    /// Maximum rule count in portable IR (SPEC 9.2).
    public const int MaxRules = 10_000;

    /// A node in the portable expression subset (SPEC 14.2).
    public sealed record PExpr(string Op, IReadOnlyList<PExpr> Args, object? Value);

    /// Closed set of portable expression operators (SPEC 14.2).
    public static readonly IReadOnlySet<string> Ops = new HashSet<string>
    {
        "field", "const", "eq", "ne", "lt", "le", "gt", "ge",
        "and", "or", "not", "is_null", "is_not_null", "in", "not_in",
    };

    // -- expression builders (SPEC 14.2) ------------------------------------

    /// Named field access (read-only).
    public static PExpr PField(string name) => new("field", Array.Empty<PExpr>(), name);
    /// Literal constant.
    public static PExpr PConst(object? value) => new("const", Array.Empty<PExpr>(), value);
    /// Equality comparison.
    public static PExpr PEq(PExpr a, PExpr b) => new("eq", new[] { a, b }, null);
    /// Inequality comparison.
    public static PExpr PNe(PExpr a, PExpr b) => new("ne", new[] { a, b }, null);
    /// Less-than comparison.
    public static PExpr PLt(PExpr a, PExpr b) => new("lt", new[] { a, b }, null);
    /// Less-than-or-equal comparison.
    public static PExpr PLe(PExpr a, PExpr b) => new("le", new[] { a, b }, null);
    /// Greater-than comparison.
    public static PExpr PGt(PExpr a, PExpr b) => new("gt", new[] { a, b }, null);
    /// Greater-than-or-equal comparison.
    public static PExpr PGe(PExpr a, PExpr b) => new("ge", new[] { a, b }, null);
    /// Boolean AND over all arguments.
    public static PExpr PAnd(params PExpr[] args) => new("and", args, null);
    /// Boolean OR over all arguments.
    public static PExpr POr(params PExpr[] args) => new("or", args, null);
    /// Boolean NOT.
    public static PExpr PNot(PExpr a) => new("not", new[] { a }, null);
    /// Null check.
    public static PExpr PIsNull(PExpr a) => new("is_null", new[] { a }, null);
    /// Non-null check.
    public static PExpr PIsNotNull(PExpr a) => new("is_not_null", new[] { a }, null);
    /// Enum membership (in).
    public static PExpr PIn(PExpr a, IReadOnlyList<object?> values) => new("in", new[] { a }, values);
    /// Enum non-membership (not in).
    public static PExpr PNotIn(PExpr a, IReadOnlyList<object?> values) => new("not_in", new[] { a }, values);

    /// Serialize a PExpr to a JsonObject (SPEC 14.2).
    public static JsonObject ExprToNode(PExpr? e)
    {
        if (e is null) return null!;
        var obj = new JsonObject { ["op"] = e.Op };
        switch (e.Op)
        {
            case "field":
            case "const":
                obj["value"] = e.Value is string s ? JsonValue.Create(s) : JsonValue.Create(e.Value);
                break;
            case "in":
            case "not_in":
                obj["args"] = new JsonArray(ExprToNode(e.Args[0]));
                obj["value"] = e.Value is IReadOnlyList<object?> list
                    ? new JsonArray(list.Select(v => v is string sv ? JsonValue.Create(sv) : JsonValue.Create(v)).ToArray())
                    : JsonValue.Create(e.Value);
                break;
            case "and":
            case "or":
                obj["args"] = new JsonArray(e.Args.Select(a => (JsonNode?)ExprToNode(a)).ToArray());
                break;
            case "not":
            case "is_null":
            case "is_not_null":
                obj["args"] = new JsonArray(ExprToNode(e.Args[0]));
                break;
            default:
                obj["args"] = new JsonArray(ExprToNode(e.Args[0]), ExprToNode(e.Args[1]));
                break;
        }
        return obj;
    }

    /// Deserialize a PExpr from its node form (SPEC 9.2 depth limit).
    public static PExpr ExprFromNodePublic(JsonNode? node) => ExprFromNode(node, 0);

    /// Evaluate a portable expression against the input (SPEC 14.2).
    public static object? EvalExpr(PExpr e, object? input) => e.Op switch
    {
        "const" => e.Value,
        "field" => input is IDictionary<string, object?> m
            ? m.TryGetValue((string)e.Value!, out var v) ? v : null
            : throw new StructureError("field access requires mapping input"),
        "eq" => ValueEquals(EvalExpr(e.Args[0], input), EvalExpr(e.Args[1], input)),
        "ne" => !ValueEquals(EvalExpr(e.Args[0], input), EvalExpr(e.Args[1], input)),
        "lt" or "le" or "gt" or "ge" => Compare(e, input),
        "and" => e.Args.All(a => Truthy(EvalExpr(a, input))),
        "or" => e.Args.Any(a => Truthy(EvalExpr(a, input))),
        "not" => !Truthy(EvalExpr(e.Args[0], input)),
        "is_null" => EvalExpr(e.Args[0], input) is null,
        "is_not_null" => EvalExpr(e.Args[0], input) is not null,
        "in" or "not_in" => In(e, input),
        _ => throw new StructureError("unknown op: " + e.Op),
    };

    private static object Compare(PExpr e, object? input)
    {
        var a = EvalExpr(e.Args[0], input);
        var b = EvalExpr(e.Args[1], input);
        // Two strings compare lexicographically (Python parity).
        if (a is string sa && b is string sb)
        {
            var c = string.CompareOrdinal(sa, sb);
            return e.Op switch
            {
                "lt" => c < 0, "le" => c <= 0, "gt" => c > 0, _ => c >= 0,
            };
        }
        double da = ToDouble(a), db = ToDouble(b);
        return e.Op switch
        {
            "lt" => da < db,
            "le" => da <= db,
            "gt" => da > db,
            _ => da >= db,
        };
    }

    private static object In(PExpr e, object? input)
    {
        var v = EvalExpr(e.Args[0], input);
        var found = false;
        if (e.Value is IEnumerable<object?> list)
        {
            foreach (var item in list)
                if (ValueEquals(item, v)) { found = true; break; }
        }
        return e.Op == "in" ? found : !found;
    }

    /// Python-style truthiness: false, null, numeric zero, empty string,
    /// and empty collections are falsy; every other value is truthy.
    public static bool Truthy(object? v)
    {
        switch (v)
        {
            case null: return false;
            case bool b: return b;
            case string s: return s.Length > 0;
            case System.Collections.IEnumerable en when v is not string:
                var it = en.GetEnumerator();
                try { return it.MoveNext(); } finally { (it as IDisposable)?.Dispose(); }
        }
        if (IsNumber(v)) return ToDouble(v) != 0;
        return true;
    }

    /// Numeric-aware equality: int 1 equals double 1.0 across IR round-trips;
    /// booleans equal 0/1 like Python (true == 1, true != false).
    private static bool ValueEquals(object? a, object? b)
    {
        if (Equals(a, b)) return true;
        if (a is bool ab)
        {
            if (b is bool bb) return ab == bb;
            if (b is not null && IsNumber(b)) return (ab ? 1.0 : 0.0) == ToDouble(b);
            return false;
        }
        if (b is bool bb2)
        {
            if (a is not null && IsNumber(a)) return ToDouble(a) == (bb2 ? 1.0 : 0.0);
            return false;
        }
        if (a is not null && b is not null && IsNumber(a) && IsNumber(b))
            return ToDouble(a) == ToDouble(b);
        return false;
    }

    private static bool IsNumber(object v) => v is sbyte or byte or short or ushort or int or uint
        or long or ulong or float or double or decimal or JsonValue;

    private static double ToDouble(object? v) => v switch
    {
        null => throw new StructureError("comparison operand cannot be null"),
        bool b => b ? 1.0 : 0.0,
        double d => d,
        float f => f,
        int i => i,
        long l => l,
        decimal m => (double)m,
        JsonValue jv when jv.TryGetValue<double>(out var d) => d,
        _ => ToDoubleStrict(v),
    };

    private static double ToDoubleStrict(object v)
    {
        try { return Convert.ToDouble(v); }
        catch (Exception ex) when (ex is FormatException or InvalidCastException or OverflowException)
        {
            throw new StructureError("comparison operand is not numeric: " + v);
        }
    }

    /// Deserialize a PExpr from its node form with depth tracking (SPEC 9.2).
    public static PExpr ExprFromNode(JsonNode? node, int depth)
    {
        if (depth > MaxExprDepth) throw new StructureError("expression nesting exceeds maximum depth");
        if (node is not JsonObject obj) throw new StructureError("expression must be an object");
        var op = obj["op"]?.GetValue<string>();
        if (op is null || !Ops.Contains(op)) throw new StructureError("unknown op: " + op);
        var args = new List<PExpr>();
        if (obj["args"] is JsonArray arr)
            foreach (var a in arr) args.Add(ExprFromNode(a, depth + 1));
        var value = ToClr(obj["value"]);
        return new PExpr(op, args, value);
    }

    /// One rule in the Portable IR (SPEC 14.2).
    public sealed class PortableRule
    {
        /// Unique rule identifier.
        public required string RuleId { get; init; }
        /// Rule kind: when | when_not.
        public required string Kind { get; init; }
        /// Condition expression.
        public PExpr? Condition { get; set; }
        /// Optional guard expression.
        public PExpr? Guard { get; set; }
        /// Transform expression producing the value.
        public PExpr? Transform { get; set; }
        /// Evaluation priority.
        public int Priority { get; init; }
        /// Effective-from timestamp (ISO-8601 string).
        public string? EffectiveFrom { get; set; }
        /// Effective-until timestamp (ISO-8601 string).
        public string? EffectiveUntil { get; set; }
        /// Proposed effects.
        public List<Effect> Effects { get; } = new();
    }

    /// Canonical Portable IR document (SPEC 14.2).
    public sealed class PortableFlow
    {
        /// SPEC version that produced the IR.
        public string? SpecVersion { get; init; }
        /// Flow identifier.
        public string? FlowId { get; init; }
        /// Portability classification.
        public string? Portability { get; init; }
        /// Evaluation mode.
        public EvaluationMode Mode { get; init; }
        /// Rules in evaluation order.
        public List<PortableRule> Rules { get; } = new();
        /// Fallback rule, if any.
        public JsonObject? Fallback { get; init; }
        /// Contract version carried from the source contract.
        public string? ContractVersion { get; init; }
    }

    /// Deserialize a PortableFlow from its node form, enforcing SPEC 9.2 limits.
    public static PortableFlow PortableFlowFromNode(JsonNode? node)
    {
        if (node is not JsonObject d) throw new StructureError("portable IR must be an object");
        if (d["spec_version"]?.GetValue<string>() is { Length: > 0 } sv && sv != Trust.SpecVersion)
            throw new StructureError($"portable IR spec_version {sv} does not match current {Trust.SpecVersion} (SPEC 9.5)");
        if (d["portability"]?.GetValue<string>() is { Length: > 0 } portv && portv != "PORTABLE")
            throw new StructureError("portable IR portability must be PORTABLE");
        var pf = new PortableFlow
        {
            SpecVersion = d["spec_version"]?.GetValue<string>(),
            FlowId = d["flow_id"]?.GetValue<string>(),
            Portability = d["portability"]?.GetValue<string>(),
            Mode = Enum.Parse<EvaluationMode>(d["mode"]!.GetValue<string>()),
            Fallback = d["fallback"] as JsonObject,
            ContractVersion = d["contract_version"]?.GetValue<string>(),
        };
        if (d["rules"] is JsonArray rules)
        {
            if (rules.Count > MaxRules) throw new StructureError("rule count exceeds maximum");
            var seen = new HashSet<string>();
            foreach (var r in rules)
            {
                if (r is not JsonObject rm) throw new StructureError("rule entries must be objects");
                var rid = rm["rule_id"]?.GetValue<string>();
                if (string.IsNullOrEmpty(rid)) throw new StructureError("rule_id must be non-empty string");
                if (!seen.Add(rid)) throw new StructureError("duplicate rule_id: " + rid);
                var kind = rm["kind"]?.GetValue<string>();
                if (kind == "then") throw new StructureError("portable IR cannot carry then stages (ADR-0003)");
                if (kind is not ("when" or "when_not")) throw new StructureError("unknown rule kind: " + kind);
                var prioClr = ToClr(rm["priority"]);
                var pr = new PortableRule
                {
                    RuleId = rid, Kind = kind!,
                    Priority = prioClr is int pi ? pi
                        : prioClr is long pl ? (int)pl
                        : prioClr is string ps && int.TryParse(ps, out var pv) ? pv : 0,
                };
                pr.EffectiveFrom = rm["effective_from"]?.GetValue<string>();
                pr.EffectiveUntil = rm["effective_until"]?.GetValue<string>();
                if (rm["condition"] is not null) pr.Condition = ExprFromNode(rm["condition"], 0);
                if (rm["guard"] is not null) pr.Guard = ExprFromNode(rm["guard"], 0);
                if (rm["transform"] is not null) pr.Transform = ExprFromNode(rm["transform"], 0);
                if (rm["effects"] is JsonArray es)
                    foreach (var ev in es)
                        if (ev is JsonObject em)
                            pr.Effects.Add(new Effect(em["name"]?.GetValue<string>() ?? "", ToClr(em["payload"])));
                pf.Rules.Add(pr);
            }
        }
        return pf;
    }

    /// Serialize a PortableFlow to a JsonObject.
    public static JsonObject PortableFlowToNode(PortableFlow pf)
    {
        var obj = new JsonObject
        {
            ["spec_version"] = pf.SpecVersion,
            ["flow_id"] = pf.FlowId,
            ["portability"] = pf.Portability,
            ["mode"] = pf.Mode.ToString(),
            ["fallback"] = pf.Fallback?.DeepClone(),
            ["contract_version"] = pf.ContractVersion,
        };
        var rules = new JsonArray();
        foreach (var r in pf.Rules)
        {
            var rm = new JsonObject
            {
                ["rule_id"] = r.RuleId,
                ["kind"] = r.Kind,
                ["condition"] = r.Condition is null ? null : ExprToNode(r.Condition),
                ["guard"] = r.Guard is null ? null : ExprToNode(r.Guard),
                ["transform"] = r.Transform is null ? null : ExprToNode(r.Transform),
                ["priority"] = r.Priority,
                ["effective_from"] = r.EffectiveFrom,
                ["effective_until"] = r.EffectiveUntil,
            };
            var es = new JsonArray();
            foreach (var e in r.Effects)
                es.Add(new JsonObject { ["name"] = e.Name, ["payload"] = e.Payload is string ps ? JsonValue.Create(ps) : JsonValue.Create(e.Payload) });
            rm["effects"] = es;
            rules.Add(rm);
        }
        obj["rules"] = rules;
        return obj;
    }

    /// Serialize a PortableFlow to canonical JSON.
    public static string PortableFlowToJSON(PortableFlow pf) =>
        Trust.CanonicalJson.Write(PortableFlowToNode(pf));

    /// Deserialize a PortableFlow from JSON, enforcing the SPEC 9.2 size limit.
    public static PortableFlow PortableFlowFromJSON(string text)
    {
        if (text.Length > MaxIRBytes)
            throw new StructureError($"portable IR exceeds maximum size {MaxIRBytes} bytes (SPEC 9.2)");
        return PortableFlowFromNode(JsonNode.Parse(text));
    }

    /// Convert JsonNode to CLR values (dictionaries/lists/primitives).
    public static object? ToClr(JsonNode? node) => node switch
    {
        null => null,
        JsonObject o => o.ToDictionary(kv => kv.Key, kv => ToClr(kv.Value)),
        JsonArray a => a.Select(ToClr).ToList(),
        JsonValue v when v.TryGetValue<bool>(out var b) => b,
        JsonValue v when v.TryGetValue<long>(out var l) => l,
        JsonValue v when v.TryGetValue<double>(out var d) => d,
        JsonValue v when v.TryGetValue<object>(out var o) && o is not JsonElement => o,
        JsonValue v when v.TryGetValue<string>(out var s) => s,
        _ => node?.ToString(),
    };
}
