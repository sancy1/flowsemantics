package flowsemantics

import (
	"encoding/json"
	"fmt"
)

// SPEC 9.2 limits.
const (
	// MaxExprDepth is the maximum expression nesting depth (SPEC 9.2).
	MaxExprDepth = 100
	// MaxIRBytes is the maximum portable IR size in bytes (SPEC 9.2).
	MaxIRBytes   = 1_000_000
	// MaxRules is the maximum rule count in portable IR (SPEC 9.2).
	MaxRules     = 10_000
)

// PExpr is a node in the portable expression subset (SPEC 14.2).
type PExpr struct {
	Op    string
	Args  []*PExpr
	Value any
}

// PExprOps is the closed set of portable expression operators (SPEC 14.2).
var PExprOps = map[string]bool{
	"field": true, "const": true, "eq": true, "ne": true, "lt": true,
	"le": true, "gt": true, "ge": true, "and": true, "or": true,
	"not": true, "is_null": true, "is_not_null": true, "in": true, "not_in": true,
}

// -- expression builders (SPEC 14.2) -----------------------------------------

// PField builds a named field access (read-only).
func PField(name string) *PExpr { return &PExpr{Op: "field", Value: name} }
// PConst builds a literal constant.
func PConst(value any) *PExpr { return &PExpr{Op: "const", Value: value} }
// PEq builds an equality comparison.
func PEq(a, b *PExpr) *PExpr { return &PExpr{Op: "eq", Args: []*PExpr{a, b}} }
// PNe builds an inequality comparison.
func PNe(a, b *PExpr) *PExpr { return &PExpr{Op: "ne", Args: []*PExpr{a, b}} }
// PLt builds a less-than comparison.
func PLt(a, b *PExpr) *PExpr { return &PExpr{Op: "lt", Args: []*PExpr{a, b}} }
// PLe builds a less-than-or-equal comparison.
func PLe(a, b *PExpr) *PExpr { return &PExpr{Op: "le", Args: []*PExpr{a, b}} }
// PGt builds a greater-than comparison.
func PGt(a, b *PExpr) *PExpr { return &PExpr{Op: "gt", Args: []*PExpr{a, b}} }
// PGe builds a greater-than-or-equal comparison.
func PGe(a, b *PExpr) *PExpr { return &PExpr{Op: "ge", Args: []*PExpr{a, b}} }
// PAnd builds a boolean AND over all arguments.
func PAnd(args ...*PExpr) *PExpr { return &PExpr{Op: "and", Args: args} }
// POr builds a boolean OR over all arguments.
func POr(args ...*PExpr) *PExpr { return &PExpr{Op: "or", Args: args} }
// PNot builds a boolean NOT.
func PNot(a *PExpr) *PExpr { return &PExpr{Op: "not", Args: []*PExpr{a}} }
// PIsNull builds a null check.
func PIsNull(a *PExpr) *PExpr { return &PExpr{Op: "is_null", Args: []*PExpr{a}} }
// PIsNotNull builds a non-null check.
func PIsNotNull(a *PExpr) *PExpr { return &PExpr{Op: "is_not_null", Args: []*PExpr{a}} }
// PIn builds an enum membership (in) expression.
func PIn(a *PExpr, values []any) *PExpr { return &PExpr{Op: "in", Args: []*PExpr{a}, Value: values} }
// PNotIn builds an enum non-membership (not in) expression.
func PNotIn(a *PExpr, values []any) *PExpr { return &PExpr{Op: "not_in", Args: []*PExpr{a}, Value: values} }

// ExprToDict serializes a PExpr to a JSON-safe map.
func ExprToDict(e *PExpr) map[string]any {
	if e == nil { return nil }
	switch e.Op {
	case "field", "const":
		return map[string]any{"op": e.Op, "value": e.Value}
	case "in", "not_in":
		return map[string]any{"op": e.Op, "args": []any{ExprToDict(e.Args[0])}, "value": e.Value}
	case "and", "or":
		args := make([]any, 0, len(e.Args))
		for _, a := range e.Args { args = append(args, ExprToDict(a)) }
		return map[string]any{"op": e.Op, "args": args}
	case "not", "is_null", "is_not_null":
		return map[string]any{"op": e.Op, "args": []any{ExprToDict(e.Args[0])}}
	default:
		return map[string]any{"op": e.Op, "args": []any{ExprToDict(e.Args[0]), ExprToDict(e.Args[1])}}
	}
}

// ExprFromDict deserializes a PExpr from its map form (SPEC 9.2 depth limit).
func ExprFromDict(data any) (*PExpr, error) { return exprFromDict(data, 0) }

// EvalExpr evaluates a portable expression against the input (SPEC 14.2).
func EvalExpr(e *PExpr, input any) (any, error) {
	switch e.Op {
	case "const":
		return e.Value, nil
	case "field":
		m, ok := input.(map[string]any)
		if !ok {
			return nil, NewStructureError("field access requires mapping input")
		}
		name, _ := e.Value.(string)
		return m[name], nil
	case "eq":
		a, err := EvalExpr(e.Args[0], input); if err != nil { return nil, err }
		b, err := EvalExpr(e.Args[1], input); if err != nil { return nil, err }
		return a == b, nil
	case "ne":
		a, err := EvalExpr(e.Args[0], input); if err != nil { return nil, err }
		b, err := EvalExpr(e.Args[1], input); if err != nil { return nil, err }
		return a != b, nil
	case "lt", "le", "gt", "ge":
		a, err := EvalExpr(e.Args[0], input); if err != nil { return nil, err }
		b, err := EvalExpr(e.Args[1], input); if err != nil { return nil, err }
		return compareNums(e.Op, a, b)
	case "and":
		for _, a := range e.Args {
			v, err := EvalExpr(a, input); if err != nil { return nil, err }
			if !truthy(v) { return false, nil }
		}
		return true, nil
	case "or":
		for _, a := range e.Args {
			v, err := EvalExpr(a, input); if err != nil { return nil, err }
			if truthy(v) { return true, nil }
		}
		return false, nil
	case "not":
		v, err := EvalExpr(e.Args[0], input); if err != nil { return nil, err }
		return !truthy(v), nil
	case "is_null":
		v, err := EvalExpr(e.Args[0], input); if err != nil { return nil, err }
		return v == nil, nil
	case "is_not_null":
		v, err := EvalExpr(e.Args[0], input); if err != nil { return nil, err }
		return v != nil, nil
	case "in", "not_in":
		v, err := EvalExpr(e.Args[0], input); if err != nil { return nil, err }
		list, _ := e.Value.([]any)
		found := false
		for _, item := range list {
			if item == v { found = true; break }
		}
		if e.Op == "in" { return found, nil }
		return !found, nil
	}
	return nil, NewStructureError(fmt.Sprintf("unknown op: %s", e.Op))
}

func truthy(v any) bool {
	b, ok := v.(bool)
	return ok && b
}

func compareNums(op string, a, b any) (any, error) {
	ai, aok := toFloat(a)
	bi, bok := toFloat(b)
	if !aok || !bok {
		return nil, NewStructureError("comparison requires numbers")
	}
	switch op {
	case "lt": return ai < bi, nil
	case "le": return ai <= bi, nil
	case "gt": return ai > bi, nil
	case "ge": return ai >= bi, nil
	}
	return nil, NewStructureError("bad op")
}

func toFloat(v any) (float64, bool) {
	switch n := v.(type) {
	case float64: return n, true
	case int: return float64(n), true
	case int64: return float64(n), true
	case json.Number: f, err := n.Float64(); return f, err == nil
	}
	return 0, false
}

type pexprJSON struct {
	Op    string          `json:"op"`
	Args  []pexprJSON     `json:"args"`
	Value json.RawMessage `json:"value"`
}

func exprFromDict(data any, depth int) (*PExpr, error) {
	if depth > MaxExprDepth {
		return nil, NewStructureError("expression nesting exceeds maximum depth")
	}
	m, ok := data.(map[string]any)
	if !ok {
		return nil, NewStructureError("expression must be an object")
	}
	op, _ := m["op"].(string)
	if !PExprOps[op] {
		return nil, NewStructureError(fmt.Sprintf("unknown op: %v", m["op"]))
	}
	e := &PExpr{Op: op}
	switch op {
	case "field", "const":
		e.Value = m["value"]
		return e, nil
	case "in", "not_in":
		args, _ := m["args"].([]any)
		for _, a := range args {
			ea, err := exprFromDict(a, depth+1); if err != nil { return nil, err }
			e.Args = append(e.Args, ea)
		}
		e.Value = m["value"]
		return e, nil
	case "and", "or":
		args, _ := m["args"].([]any)
		for _, a := range args {
			ea, err := exprFromDict(a, depth+1); if err != nil { return nil, err }
			e.Args = append(e.Args, ea)
		}
		return e, nil
	case "not", "is_null", "is_not_null":
		args, _ := m["args"].([]any)
		if len(args) == 0 { return nil, NewStructureError("missing arg") }
		ea, err := exprFromDict(args[0], depth+1); if err != nil { return nil, err }
		e.Args = []*PExpr{ea}
		return e, nil
	default:
		args, _ := m["args"].([]any)
		if len(args) < 2 { return nil, NewStructureError("binary op needs 2 args") }
		a0, err := exprFromDict(args[0], depth+1); if err != nil { return nil, err }
		a1, err := exprFromDict(args[1], depth+1); if err != nil { return nil, err }
		e.Args = []*PExpr{a0, a1}
		return e, nil
	}
}

// PortableRule is one rule in the Portable IR (SPEC 14.2).
type PortableRule struct {
	RuleID        string
	Kind          string // when | when_not
	Condition     *PExpr
	Guard         *PExpr
	Transform     *PExpr
	Priority      int
	EffectiveFrom *string
	EffectiveUntil *string
	Effects       []Effect
}

// PortableFlow is the canonical Portable IR document (SPEC 14.2).
type PortableFlow struct {
	SpecVersion    string
	FlowID         string
	Portability    string
	Mode           EvaluationMode
	Rules          []PortableRule
	Fallback       map[string]any
	ContractVersion string
}

// PortableFlowFromDict deserializes a PortableFlow from its map form,
// enforcing SPEC 9.2 limits.
func PortableFlowFromDict(data any) (*PortableFlow, error) {
	d, ok := data.(map[string]any)
	if !ok {
		return nil, NewStructureError("portable IR must be an object")
	}
	rawRules, _ := d["rules"].([]any)
	if len(rawRules) > MaxRules {
		return nil, NewStructureError("rule count exceeds maximum")
	}
	seen := map[string]bool{}
	var rules []PortableRule
	for _, r := range rawRules {
		rm, ok := r.(map[string]any)
		if !ok {
			return nil, NewStructureError("rule entries must be objects")
		}
		rid, _ := rm["rule_id"].(string)
		if rid == "" {
			return nil, NewStructureError("rule_id must be non-empty string")
		}
		if seen[rid] {
			return nil, NewStructureError("duplicate rule_id: " + rid)
		}
		seen[rid] = true
		kind, _ := rm["kind"].(string)
		if kind == "then" {
			return nil, NewStructureError("portable IR cannot carry then stages (ADR-0003)")
		}
		if kind != "when" && kind != "when_not" {
			return nil, NewStructureError("unknown rule kind: " + kind)
		}
		pr := PortableRule{RuleID: rid, Kind: kind}
		if c, ok := rm["condition"]; ok && c != nil {
			e, err := exprFromDict(c, 0); if err != nil { return nil, err }
			pr.Condition = e
		}
		if g, ok := rm["guard"]; ok && g != nil {
			e, err := exprFromDict(g, 0); if err != nil { return nil, err }
			pr.Guard = e
		}
		if t, ok := rm["transform"]; ok && t != nil {
			e, err := exprFromDict(t, 0); if err != nil { return nil, err }
			pr.Transform = e
		}
		if p, ok := rm["priority"].(float64); ok { pr.Priority = int(p) }
		if ef, ok := rm["effective_from"].(string); ok && ef != "" { pr.EffectiveFrom = &ef }
		if eu, ok := rm["effective_until"].(string); ok && eu != "" { pr.EffectiveUntil = &eu }
		var effects []Effect
		if es, ok := rm["effects"].([]any); ok {
			for _, ev := range es {
				em, _ := ev.(map[string]any)
				name, _ := em["name"].(string)
				effects = append(effects, Effect{Name: name, Payload: em["payload"]})
			}
		}
		pr.Effects = effects
		rules = append(rules, pr)
	}
	pf := &PortableFlow{
		SpecVersion: strOf(d["spec_version"]),
		FlowID:      strOf(d["flow_id"]),
		Portability: strOf(d["portability"]),
		Mode:        EvaluationMode(strOf(d["mode"])),
		Rules:       rules,
		ContractVersion: strOf(d["contract_version"]),
	}
	if fb, ok := d["fallback"].(map[string]any); ok { pf.Fallback = fb }
	return pf, nil
}

// PortableFlowToDict serializes a PortableFlow to a JSON-safe map.
func PortableFlowToDict(pf *PortableFlow) map[string]any {
	rules := make([]any, 0, len(pf.Rules))
	for _, r := range pf.Rules {
		rm := map[string]any{
			"rule_id": r.RuleID, "kind": r.Kind,
			"condition": nil, "guard": nil, "transform": nil,
			"priority":  r.Priority,
			"effective_from":  nil,
			"effective_until": nil,
			"effects":   r.Effects,
		}
		if r.Condition != nil { rm["condition"] = ExprToDict(r.Condition) }
		if r.Guard != nil { rm["guard"] = ExprToDict(r.Guard) }
		if r.Transform != nil { rm["transform"] = ExprToDict(r.Transform) }
		if r.EffectiveFrom != nil { rm["effective_from"] = *r.EffectiveFrom }
		if r.EffectiveUntil != nil { rm["effective_until"] = *r.EffectiveUntil }
		rules = append(rules, rm)
	}
	return map[string]any{
		"spec_version":    pf.SpecVersion,
		"flow_id":         pf.FlowID,
		"portability":     pf.Portability,
		"mode":            string(pf.Mode),
		"rules":           rules,
		"fallback":        pf.Fallback,
		"contract_version": pf.ContractVersion,
	}
}

// PortableFlowToJSON serializes a PortableFlow to canonical JSON.
func PortableFlowToJSON(pf *PortableFlow) (string, error) {
	b, err := json.Marshal(PortableFlowToDict(pf))
	if err != nil { return "", err }
	return string(b), nil
}

// PortableFlowFromJSON deserializes a PortableFlow from JSON, enforcing
// the SPEC 9.2 size limit.
func PortableFlowFromJSON(text string) (*PortableFlow, error) {
	if len(text) > MaxIRBytes {
		return nil, NewStructureError(fmt.Sprintf("portable IR exceeds maximum size %d bytes (SPEC 9.2)", MaxIRBytes))
	}
	var data any
	if err := json.Unmarshal([]byte(text), &data); err != nil {
		return nil, NewStructureError("portable IR is not valid JSON: " + err.Error())
	}
	return PortableFlowFromDict(data)
}

func strOf(v any) string { s, _ := v.(string); return s }
