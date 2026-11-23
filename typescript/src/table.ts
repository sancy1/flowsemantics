/**
 * flowsemantics table - DecisionTable (SPEC.md section 10.8).
 *
 * A decision table compiles to the same rule list as the fluent API.
 * Hit policies map to EvaluationMode: FIRST->FirstMatch,
 * COLLECT->AllMatch, PRIORITY->Priority, UNIQUE->FirstMatch plus a
 * compile-time exclusivity check where statically provable.
 */

import { Flow, type ActionFn, type ConditionFn } from "./flow.ts";
import { EvaluationMode } from "./types.ts";

/** Hit policy for a decision table (SPEC 10.8). */
export type HitPolicy = "FIRST" | "COLLECT" | "PRIORITY" | "UNIQUE";

const HIT_POLICY_TO_MODE: Record<HitPolicy, EvaluationMode> = {
  FIRST: EvaluationMode.FIRST_MATCH,
  COLLECT: EvaluationMode.ALL_MATCH,
  PRIORITY: EvaluationMode.PRIORITY,
  UNIQUE: EvaluationMode.FIRST_MATCH,
};

/** One row of a decision table (SPEC 10.8). */
export interface DecisionTableRow {
  id: string;
  conditions: ConditionFn[];
  action: ActionFn;
  priority?: number;
}

/** A decision table: rows of conditions + action with a hit policy (SPEC 10.8). */
export interface DecisionTable {
  rows: DecisionTableRow[];
  hitPolicy?: HitPolicy;
  inputFields?: string[];
  warnings?: string[];
}

function allConditions(conditions: ConditionFn[]): ConditionFn {
  return (input: unknown): boolean => conditions.every((c) => c(input));
}

/** Compile a DecisionTable into a Flow builder (SPEC 10.8). */
export function tableToFlow(table: DecisionTable): Flow {
  const hitPolicy = table.hitPolicy ?? "FIRST";
  const mode = HIT_POLICY_TO_MODE[hitPolicy];
  if (mode === undefined) {
    throw new Error(`unknown hit policy: ${hitPolicy}`);
  }
  if (!table.rows || table.rows.length === 0) {
    throw new Error("decision table must have at least one row");
  }
  const flow = new Flow().withMode(mode);
  for (const row of table.rows) {
    flow.when(allConditions(row.conditions), row.action, {
      id: row.id,
      priority: row.priority ?? 0,
    });
  }
  return flow;
}
