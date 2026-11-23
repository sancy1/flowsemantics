// Portable IR — SPEC.md section 14.2, 9.2.

import { StructureError } from "./errors.ts";

/** Maximum expression nesting depth (SPEC 9.2). */
export const MAX_EXPR_DEPTH = 100;
/** Maximum portable IR size in bytes (SPEC 9.2). */
export const MAX_IR_BYTES = 1_000_000;
/** Maximum rule count in portable IR (SPEC 9.2). */
export const MAX_RULES = 10_000;

/** A node in the portable expression subset (SPEC 14.2). */
export interface PExpr {
  op: string;
  args?: PExpr[];
  value?: unknown;
}

/** Closed set of portable expression operators (SPEC 14.2). */
export const OPS: ReadonlySet<string> = new Set([
  "field", "const", "eq", "ne", "lt", "le", "gt", "ge",
  "and", "or", "not", "is_null", "is_not_null", "in", "not_in",
]);

// -- expression builders (SPEC 14.2) -------------------------------------------

/** Named field access (read-only). */
export function pfield(name: string): PExpr { return { op: "field", value: name }; }
/** Literal constant. */
export function pconst(value: unknown): PExpr { return { op: "const", value }; }
/** Equality comparison. */
export function peq(a: PExpr, b: PExpr): PExpr { return { op: "eq", args: [a, b] }; }
/** Inequality comparison. */
export function pne(a: PExpr, b: PExpr): PExpr { return { op: "ne", args: [a, b] }; }
/** Less-than comparison. */
export function plt(a: PExpr, b: PExpr): PExpr { return { op: "lt", args: [a, b] }; }
/** Less-than-or-equal comparison. */
export function ple(a: PExpr, b: PExpr): PExpr { return { op: "le", args: [a, b] }; }
/** Greater-than comparison. */
export function pgt(a: PExpr, b: PExpr): PExpr { return { op: "gt", args: [a, b] }; }
/** Greater-than-or-equal comparison. */
export function pge(a: PExpr, b: PExpr): PExpr { return { op: "ge", args: [a, b] }; }
/** Boolean AND over all arguments. */
export function pand(...args: PExpr[]): PExpr { return { op: "and", args }; }
/** Boolean OR over all arguments. */
export function por(...args: PExpr[]): PExpr { return { op: "or", args }; }
/** Boolean NOT. */
export function pnot(a: PExpr): PExpr { return { op: "not", args: [a] }; }
/** Null check. */
export function pis_null(a: PExpr): PExpr { return { op: "is_null", args: [a] }; }
/** Non-null check. */
export function pis_not_null(a: PExpr): PExpr { return { op: "is_not_null", args: [a] }; }
/** Enum membership (in). */
export function pin(a: PExpr, values: unknown[]): PExpr { return { op: "in", args: [a], value: values }; }
/** Enum non-membership (not in). */
export function pnot_in(a: PExpr, values: unknown[]): PExpr { return { op: "not_in", args: [a], value: values }; }

/** Serialize a PExpr to a JSON-safe map. */
export function exprToDict(expr: PExpr): Record<string, unknown> {
  if (expr.op === "field" || expr.op === "const") {
    return { op: expr.op, value: expr.value };
  }
  if (expr.op === "in" || expr.op === "not_in") {
    return { op: expr.op, args: [exprToDict(expr.args![0]!)], value: expr.value ?? [] };
  }
  if (expr.op === "and" || expr.op === "or") {
    return { op: expr.op, args: expr.args!.map(exprToDict) };
  }
  if (expr.op === "not" || expr.op === "is_null" || expr.op === "is_not_null") {
    return { op: expr.op, args: [exprToDict(expr.args![0]!)] };
  }
  return { op: expr.op, args: [exprToDict(expr.args![0]!), exprToDict(expr.args![1]!)] };
}

/** Evaluate a portable expression against the input (SPEC 14.2). */
export function evalExpr(expr: PExpr, input: unknown): unknown {
  switch (expr.op) {
    case "const": return expr.value;
    case "field": {
      if (typeof input !== "object" || input === null) {
        throw new StructureError("field access requires a mapping input");
      }
      return (input as Record<string, unknown>)[expr.value as string];
    }
    case "eq": return evalExpr(expr.args![0]!, input) === evalExpr(expr.args![1]!, input);
    case "ne": return evalExpr(expr.args![0]!, input) !== evalExpr(expr.args![1]!, input);
    case "lt": return (evalExpr(expr.args![0]!, input) as number) < (evalExpr(expr.args![1]!, input) as number);
    case "le": return (evalExpr(expr.args![0]!, input) as number) <= (evalExpr(expr.args![1]!, input) as number);
    case "gt": return (evalExpr(expr.args![0]!, input) as number) > (evalExpr(expr.args![1]!, input) as number);
    case "ge": return (evalExpr(expr.args![0]!, input) as number) >= (evalExpr(expr.args![1]!, input) as number);
    case "and": return expr.args!.every((a) => Boolean(evalExpr(a, input)));
    case "or": return expr.args!.some((a) => Boolean(evalExpr(a, input)));
    case "not": return !evalExpr(expr.args![0]!, input);
    case "is_null": return evalExpr(expr.args![0]!, input) === null || evalExpr(expr.args![0]!, input) === undefined;
    case "is_not_null": { const v = evalExpr(expr.args![0]!, input); return v !== null && v !== undefined; }
    case "in": {
      const v = evalExpr(expr.args![0]!, input);
      const list = expr.value as unknown[];
      return list.includes(v);
    }
    case "not_in": {
      const v = evalExpr(expr.args![0]!, input);
      const list = expr.value as unknown[];
      return !list.includes(v);
    }
    default: throw new StructureError(`unknown portable expression op: ${expr.op}`);
  }
}

/** Deserialize a PExpr from its map form (SPEC 9.2 depth limit). */
export function exprFromDict(data: unknown, depth = 0): PExpr {
  if (depth > MAX_EXPR_DEPTH) {
    throw new StructureError(`expression nesting exceeds ${MAX_EXPR_DEPTH}`);
  }
  if (typeof data !== "object" || data === null) {
    throw new StructureError("expression must be an object");
  }
  const d = data as Record<string, unknown>;
  const op = d.op as string;
  if (!OPS.has(op)) throw new StructureError(`unknown op: ${op}`);
  const out: PExpr = { op };
  if (op === "field" || op === "const") {
    out.value = d.value;
    return out;
  }
  if (op === "in" || op === "not_in") {
    out.args = (d.args as unknown[]).map((a) => exprFromDict(a, depth + 1));
    out.value = d.value;
    return out;
  }
  if (op === "and" || op === "or") {
    out.args = (d.args as unknown[]).map((a) => exprFromDict(a, depth + 1));
    return out;
  }
  if (op === "not" || op === "is_null" || op === "is_not_null") {
    out.args = [exprFromDict((d.args as unknown[])[0], depth + 1)];
    return out;
  }
  out.args = [
    exprFromDict((d.args as unknown[])[0], depth + 1),
    exprFromDict((d.args as unknown[])[1], depth + 1),
  ];
  return out;
}

/** One rule in the Portable IR (SPEC 14.2). */
export interface PortableRule {
  rule_id: string;
  kind: "when" | "when_not" | "then";
  condition?: PExpr | undefined;
  guard?: PExpr | undefined;
  transform?: PExpr | undefined;
  priority: number;
  effective_from?: string | null | undefined;
  effective_until?: string | null | undefined;
  effects: { name: string; payload?: unknown }[];
}

/** Canonical Portable IR document (SPEC 14.2). */
export interface PortableFlow {
  spec_version: string;
  flow_id: string;
  portability: string;
  mode: string;
  rules: PortableRule[];
  fallback?: { kind: string; value?: unknown; action?: unknown } | null | undefined;
  contract_version?: string | undefined;
}

/** Deserialize a PortableFlow from its map form, enforcing SPEC 9.2 limits. */
export function portableFlowFromDict(data: unknown): PortableFlow {
  if (typeof data !== "object" || data === null) {
    throw new StructureError("portable IR must be an object");
  }
  const d = data as Record<string, unknown>;
  const rawRules = (d.rules ?? []) as unknown[];
  if (!Array.isArray(rawRules)) throw new StructureError("rules must be an array");
  if (rawRules.length > MAX_RULES) {
    throw new StructureError(`rule count exceeds ${MAX_RULES}`);
  }
  const seen = new Set<string>();
  const rules: PortableRule[] = rawRules.map((r) => {
    const rd = r as Record<string, unknown>;
    const rid = rd.rule_id as string;
    if (typeof rid !== "string" || !rid) {
      throw new StructureError("rule_id must be a non-empty string");
    }
    if (seen.has(rid)) throw new StructureError(`duplicate rule_id: ${rid}`);
    seen.add(rid);
    const kind = rd.kind as PortableRule["kind"];
    if (kind === "then") throw new StructureError("portable IR cannot carry then stages (ADR-0003)");
    if (kind !== "when" && kind !== "when_not") {
      throw new StructureError(`unknown rule kind: ${kind}`);
    }
    return {
      rule_id: rid,
      kind,
      condition: rd.condition ? exprFromDict(rd.condition) : undefined,
      guard: rd.guard ? exprFromDict(rd.guard) : undefined,
      transform: rd.transform ? exprFromDict(rd.transform) : undefined,
      priority: (rd.priority as number) ?? 0,
      effective_from: (rd.effective_from as string | null) ?? null,
      effective_until: (rd.effective_until as string | null) ?? null,
      effects: ((rd.effects as { name: string; payload?: unknown }[]) ?? []).map((e) => ({
        name: e.name,
        payload: e.payload,
      })),
    };
  });
  return {
    spec_version: d.spec_version as string,
    flow_id: d.flow_id as string,
    portability: d.portability as string,
    mode: d.mode as string,
    rules,
    fallback: (d.fallback as PortableFlow["fallback"]) ?? null,
    contract_version: (d.contract_version as string | undefined) ?? undefined,
  };
}

/** Serialize a PortableFlow to a JSON-safe map. */
export function portableFlowToDict(pf: PortableFlow): Record<string, unknown> {
  return {
    spec_version: pf.spec_version,
    flow_id: pf.flow_id,
    portability: pf.portability,
    mode: pf.mode,
    rules: pf.rules.map((r) => ({
      rule_id: r.rule_id,
      kind: r.kind,
      condition: r.condition ? exprToDict(r.condition) : null,
      guard: r.guard ? exprToDict(r.guard) : null,
      transform: r.transform ? exprToDict(r.transform) : null,
      priority: r.priority,
      effective_from: r.effective_from ?? null,
      effective_until: r.effective_until ?? null,
      effects: r.effects.map((e) => ({ ...e })),
    })),
    fallback: pf.fallback ?? null,
    contract_version: pf.contract_version ?? "",
  };
}

/** Serialize a PortableFlow to canonical JSON. */
export function portableFlowToJson(pf: PortableFlow): string {
  return JSON.stringify(portableFlowToDict(pf));
}

/** Deserialize a PortableFlow from JSON, enforcing the SPEC 9.2 size limit. */
export function portableFlowFromJson(text: string): PortableFlow {
  if (new TextEncoder().encode(text).length > MAX_IR_BYTES) {
    throw new StructureError(`portable IR exceeds maximum size ${MAX_IR_BYTES} bytes (SPEC 9.2)`);
  }
  return portableFlowFromDict(JSON.parse(text));
}
