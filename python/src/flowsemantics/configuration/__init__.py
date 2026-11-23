"""flowsemantics.configuration - Flow builder, options, registry.

Layer:      Composition
Module:     flowsemantics.configuration
Since:      0.0.0
Implements: SPEC.md sections 4.1, 10
Depends on: flowsemantics.configuration.{rule,flow}, flowsemantics.errors,
            flowsemantics.execution
Used by:    parent package; populated from Phase 1.0
See also:   SPEC.md section 10

Notes:
  - __all__ grows as features are implemented. Currently exports the
    decision-layer primitives (Flow, FlowContract, Rule, RuleId,
    EvaluationMode, Fallback, FlowPortability).
"""

from __future__ import annotations

from flowsemantics.configuration.catch import CatchRule
from flowsemantics.configuration.finalization import (
    FinallyCancellationToken,
    FinallyContext,
    FinallyFailurePolicy,
)
from flowsemantics.configuration.flow import (
    EvaluationMode,
    Fallback,
    Flow,
    FlowContract,
    FlowPortability,
    ValidationIssue,
)
from flowsemantics.configuration.portable import (
    OPS,
    PExpr,
    PortableFlow,
    PortableRule,
    eval_expr,
    expr_from_dict,
    expr_to_dict,
    pand,
    pconst,
    peq,
    pfield,
    pge,
    pgt,
    pin,
    pis_not_null,
    pis_null,
    ple,
    plt,
    pne,
    pnot,
    pnot_in,
    por,
)
from flowsemantics.configuration.rule import Rule, RuleId
from flowsemantics.configuration.table import (
    DecisionTable,
    DecisionTableRow,
    table_to_flow,
)

__all__: list[str] = [
    "OPS",
    "CatchRule",
    "DecisionTable",
    "DecisionTableRow",
    "EvaluationMode",
    "Fallback",
    "FinallyCancellationToken",
    "FinallyContext",
    "FinallyFailurePolicy",
    "Flow",
    "FlowContract",
    "FlowPortability",
    "PExpr",
    "PortableFlow",
    "PortableRule",
    "Rule",
    "RuleId",
    "ValidationIssue",
    "eval_expr",
    "expr_from_dict",
    "expr_to_dict",
    "pand",
    "pconst",
    "peq",
    "pfield",
    "pge",
    "pgt",
    "pin",
    "pis_not_null",
    "pis_null",
    "ple",
    "plt",
    "pne",
    "pnot",
    "pnot_in",
    "por",
    "table_to_flow",
]
