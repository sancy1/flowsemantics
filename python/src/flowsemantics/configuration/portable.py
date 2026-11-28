"""flowsemantics.configuration.portable - Portable IR and expression subset.

Layer:      Composition
Module:     flowsemantics.configuration.portable
Since:      0.4.0
Implements: SPEC.md section 14.2 (Portable IR), 5.1 (pure conditions)
Depends on: stdlib only
Used by:    Flow.when_expr, FlowContract.to_ir/from_ir, conformance
See also:   SPEC.md sections 14.2, 5.1

Notes:
  - The portable expression subset is deliberately small and inspectable
    (SPEC 14.2): named field access, six comparisons, and/or/not,
    is-null/is-not-null, in/not-in. Nothing else.
  - The IR MUST NOT carry host-language lambdas, serialized code, or
    host types outside the subset.
  - Schema: spec/ir.schema.json.
"""

from __future__ import annotations

import datetime
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from flowsemantics._spec import SPEC_VERSION
from flowsemantics.errors import StructureError

# -- IR hardening limits (SPEC 9.2) ---------------------------------------------
#
# Documented in docs/threat-model.md. A depth greater than 100 MUST be
# rejected; 10 is the recommended minimum supported depth.
MAX_EXPR_DEPTH = 100
MAX_IR_BYTES = 1_000_000  # 1 MiB serialized IR
MAX_RULES = 10_000

# -- expression subset ---------------------------------------------------------


@dataclass(frozen=True)
class PExpr:
    """A node in the portable expression subset (SPEC 14.2).

    op is one of: field, const, eq, ne, lt, le, gt, ge, and, or, not,
    is_null, is_not_null, in, not_in.
    """

    op: str
    args: tuple[Any, ...] = ()
    value: Any = None


OPS: frozenset[str] = frozenset(
    {
        "field",
        "const",
        "eq",
        "ne",
        "lt",
        "le",
        "gt",
        "ge",
        "and",
        "or",
        "not",
        "is_null",
        "is_not_null",
        "in",
        "not_in",
    }
)


def pfield(name: str) -> PExpr:
    """Named field access (read-only)."""
    return PExpr(op="field", value=name)


def pconst(value: Any) -> PExpr:
    """Literal constant."""
    return PExpr(op="const", value=value)


def peq(a: PExpr, b: PExpr) -> PExpr:
    """Equality comparison."""
    return PExpr(op="eq", args=(a, b))


def pne(a: PExpr, b: PExpr) -> PExpr:
    """Inequality comparison."""
    return PExpr(op="ne", args=(a, b))


def plt(a: PExpr, b: PExpr) -> PExpr:
    """Less-than comparison."""
    return PExpr(op="lt", args=(a, b))


def ple(a: PExpr, b: PExpr) -> PExpr:
    """Less-than-or-equal comparison."""
    return PExpr(op="le", args=(a, b))


def pgt(a: PExpr, b: PExpr) -> PExpr:
    """Greater-than comparison."""
    return PExpr(op="gt", args=(a, b))


def pge(a: PExpr, b: PExpr) -> PExpr:
    """Greater-than-or-equal comparison."""
    return PExpr(op="ge", args=(a, b))


def pand(*args: PExpr) -> PExpr:
    """Boolean AND over all arguments."""
    return PExpr(op="and", args=tuple(args))


def por(*args: PExpr) -> PExpr:
    """Boolean OR over all arguments."""
    return PExpr(op="or", args=tuple(args))


def pnot(a: PExpr) -> PExpr:
    """Boolean NOT."""
    return PExpr(op="not", args=(a,))


def pis_null(a: PExpr) -> PExpr:
    """Null check (is None)."""
    return PExpr(op="is_null", args=(a,))


def pis_not_null(a: PExpr) -> PExpr:
    """Non-null check."""
    return PExpr(op="is_not_null", args=(a,))


def pin(a: PExpr, values: list[Any]) -> PExpr:
    """Enum membership (in)."""
    return PExpr(op="in", args=(a,), value=tuple(values))


def pnot_in(a: PExpr, values: list[Any]) -> PExpr:
    """Enum non-membership (not in)."""
    return PExpr(op="not_in", args=(a,), value=tuple(values))


def eval_expr(expr: PExpr, input: Any) -> Any:
    """Evaluate a portable expression against the input (SPEC 14.2).

    Field access requires the input to be a mapping; anything else
    raises StructureError at evaluation time.
    """
    op = expr.op
    if op == "field":
        if not isinstance(input, Mapping):
            raise StructureError("portable field access requires a mapping input")
        return input.get(expr.value)
    if op == "const":
        return expr.value
    if op == "and":
        return all(bool(eval_expr(a, input)) for a in expr.args)
    if op == "or":
        return any(bool(eval_expr(a, input)) for a in expr.args)
    if op == "not":
        return not bool(eval_expr(expr.args[0], input))
    if op == "is_null":
        return eval_expr(expr.args[0], input) is None
    if op == "is_not_null":
        return eval_expr(expr.args[0], input) is not None
    if op == "in":
        return eval_expr(expr.args[0], input) in (expr.value or ())
    if op == "not_in":
        return eval_expr(expr.args[0], input) not in (expr.value or ())
    # binary comparisons
    left = eval_expr(expr.args[0], input)
    right = eval_expr(expr.args[1], input)
    if op == "eq":
        return left == right
    if op == "ne":
        return left != right
    if op == "lt":
        return left < right
    if op == "le":
        return left <= right
    if op == "gt":
        return left > right
    if op == "ge":
        return left >= right
    raise StructureError(f"unknown portable expression op: {op!r}")


def expr_to_dict(expr: PExpr) -> dict[str, Any]:
    """Serialize a PExpr to a JSON-safe dict."""
    if expr.op in ("field", "const"):
        return {"op": expr.op, "value": expr.value}
    if expr.op in ("in", "not_in"):
        return {
            "op": expr.op,
            "args": [expr_to_dict(expr.args[0])],
            "value": list(expr.value or ()),
        }
    if expr.op in ("and", "or"):
        return {"op": expr.op, "args": [expr_to_dict(a) for a in expr.args]}
    if expr.op in ("not", "is_null", "is_not_null"):
        return {"op": expr.op, "args": [expr_to_dict(expr.args[0])]}
    return {
        "op": expr.op,
        "args": [expr_to_dict(expr.args[0]), expr_to_dict(expr.args[1])],
    }


def expr_from_dict(data: dict[str, Any], _depth: int = 0) -> PExpr:
    """Deserialize a PExpr from its dict form.

    Rejects nesting deeper than MAX_EXPR_DEPTH (SPEC 9.2).
    """
    if _depth > MAX_EXPR_DEPTH:
        raise StructureError(
            f"portable expression nesting exceeds maximum depth {MAX_EXPR_DEPTH} (SPEC 9.2)"
        )
    op = data["op"]
    if op not in OPS:
        raise StructureError(f"unknown portable expression op in IR: {op!r}")
    if op in ("field", "const"):
        return PExpr(op=op, value=data.get("value"))
    if op in ("in", "not_in"):
        args = [expr_from_dict(a, _depth + 1) for a in data.get("args", [])]
        return PExpr(op=op, args=tuple(args), value=tuple(data.get("value", [])))
    if op in ("and", "or"):
        return PExpr(
            op=op,
            args=tuple(expr_from_dict(a, _depth + 1) for a in data["args"]),
        )
    if op in ("not", "is_null", "is_not_null"):
        return PExpr(op=op, args=(expr_from_dict(data["args"][0], _depth + 1),))
    return PExpr(
        op=op,
        args=(
            expr_from_dict(data["args"][0], _depth + 1),
            expr_from_dict(data["args"][1], _depth + 1),
        ),
    )


# -- IR types -------------------------------------------------------------------


@dataclass(frozen=True)
class PortableRule:
    """One rule in the Portable IR (SPEC 14.2)."""

    rule_id: str
    kind: str  # "when" | "when_not" | "then"
    condition: PExpr | None = None
    guard: PExpr | None = None
    transform: PExpr | None = None
    priority: int = 0
    effective_from: str | None = None
    effective_until: str | None = None
    effects: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class PortableFlow:
    """Canonical Portable IR document (SPEC 14.2)."""

    spec_version: str
    flow_id: str
    portability: str  # "PORTABLE"
    mode: str
    rules: tuple[PortableRule, ...]
    fallback: dict[str, Any] | None = None
    contract_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict."""
        return {
            "spec_version": self.spec_version,
            "flow_id": self.flow_id,
            "portability": self.portability,
            "mode": self.mode,
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "kind": r.kind,
                    "condition": (expr_to_dict(r.condition) if r.condition else None),
                    "guard": expr_to_dict(r.guard) if r.guard else None,
                    "transform": (expr_to_dict(r.transform) if r.transform else None),
                    "priority": r.priority,
                    "effective_from": r.effective_from,
                    "effective_until": r.effective_until,
                    "effects": [dict(e) for e in r.effects],
                }
                for r in self.rules
            ],
            "fallback": self.fallback,
            "contract_version": self.contract_version,
        }

    def to_json(self) -> str:
        """Serialize to a canonical JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PortableFlow:
        """Deserialize from a dict.

        Enforces SPEC 9.2 hardening: maximum rule count and duplicate
        RuleId rejection at deserialization time.
        """
        if not isinstance(data, dict):
            raise StructureError("portable IR must be a JSON object")
        sv = data.get("spec_version")
        if sv is not None and sv != SPEC_VERSION:
            raise StructureError(
                f"portable IR spec_version {sv!r} does not match current {SPEC_VERSION!r} (SPEC 9.5)"
            )
        port = data.get("portability")
        if port is not None and port != "PORTABLE":
            raise StructureError("portable IR portability must be PORTABLE")
        raw_rules = data.get("rules", [])
        if not isinstance(raw_rules, list):
            raise StructureError("portable IR 'rules' must be an array")
        if len(raw_rules) > MAX_RULES:
            raise StructureError(
                f"portable IR rule count {len(raw_rules)} exceeds maximum {MAX_RULES} (SPEC 9.2)"
            )
        seen: set[str] = set()
        for r in raw_rules:
            if not isinstance(r, dict):
                raise StructureError("portable IR rule entries must be objects")
            rid = r.get("rule_id")
            if not isinstance(rid, str) or not rid:
                raise StructureError("portable IR rule_id must be a non-empty string")
            if rid in seen:
                raise StructureError(f"duplicate RuleId in portable IR: {rid!r} (SPEC 9.2)")
            seen.add(rid)
        rules = tuple(
            PortableRule(
                rule_id=r["rule_id"],
                kind=r["kind"],
                condition=(expr_from_dict(r["condition"]) if r.get("condition") else None),
                guard=(expr_from_dict(r["guard"]) if r.get("guard") else None),
                transform=(expr_from_dict(r["transform"]) if r.get("transform") else None),
                priority=r.get("priority", 0),
                effective_from=r.get("effective_from"),
                effective_until=r.get("effective_until"),
                effects=tuple(dict(e) for e in r.get("effects", [])),
            )
            for r in data.get("rules", [])
        )
        return cls(
            spec_version=data["spec_version"],
            flow_id=data["flow_id"],
            portability=data["portability"],
            mode=data["mode"],
            rules=rules,
            fallback=data.get("fallback"),
            contract_version=data.get("contract_version", ""),
        )

    @classmethod
    def from_json(cls, text: str) -> PortableFlow:
        """Deserialize from a JSON string.

        Rejects payloads larger than MAX_IR_BYTES (SPEC 9.2).
        """
        if len(text.encode("utf-8")) > MAX_IR_BYTES:
            raise StructureError(
                f"portable IR exceeds maximum size {MAX_IR_BYTES} bytes (SPEC 9.2)"
            )
        return cls.from_dict(json.loads(text))


def _parse_dt(value: str | None) -> datetime.datetime | None:
    if value is None:
        return None
    return datetime.datetime.fromisoformat(value)


__all__: list[str] = [
    "MAX_EXPR_DEPTH",
    "MAX_IR_BYTES",
    "MAX_RULES",
    "OPS",
    "PExpr",
    "PortableFlow",
    "PortableRule",
    "_parse_dt",
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
]
