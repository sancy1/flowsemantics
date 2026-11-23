"""FlowSemantics conformance runner (conformance/runner-protocol.md).

Discovers *.json vectors recursively, resolves fixtures, builds a Flow
pipeline through the public API, executes it, and compares the observed
FlowOutcome against the vector's expected block.

Usage:
    python -m flowsemantics.testing.conformance.runner --vectors <dir>

Exit code 0 iff every discovered vector passes.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flowsemantics import (
    Effect,
    EvaluationMode,
    Flow,
    FlowOutcome,
)
from flowsemantics._spec import SPEC_VERSION
from flowsemantics.execution import FakeClock
from flowsemantics.testing.conformance.fixtures import (
    KIND_MAP,
    FixtureContext,
    kind_of_exception,
    resolve_fixture,
)

_SUPPORTED_SPEC = SPEC_VERSION


@dataclass(frozen=True)
class VectorResult:
    """Outcome of running one conformance vector."""

    vector_id: str
    passed: bool
    reason: str = ""


def _parse_version(text: str) -> tuple[int, int, int]:
    parts = text.split(".")
    if len(parts) != 3:
        raise ValueError(f"bad spec_version: {text!r}")
    return (int(parts[0]), int(parts[1]), int(parts[2]))


def _check_spec_version(vector: dict[str, Any]) -> str | None:
    """Return an error string if the vector spec_version is incompatible."""
    raw = vector.get("spec_version")
    if not isinstance(raw, str):
        return "missing or non-string spec_version"
    try:
        vec_v = _parse_version(raw)
        sup_v = _parse_version(_SUPPORTED_SPEC)
    except ValueError as exc:
        return str(exc)
    if vec_v > sup_v:
        return f"spec_version {raw} is newer than supported {_SUPPORTED_SPEC}"
    return None


def _validate_vector_shape(vector: dict[str, Any]) -> str | None:
    """Minimal structural validation (full JSON-Schema check is Phase 6+)."""
    for key in ("id", "spec_version", "spec_section", "pipeline", "input", "expected"):
        if key not in vector:
            return f"missing required key: {key!r}"
    pipeline = vector["pipeline"]
    if not isinstance(pipeline, dict):
        return "pipeline must be an object"
    if "portable_ir" not in pipeline and "rules" not in pipeline:
        return "pipeline.rules or pipeline.portable_ir missing"
    if "portable_ir" in pipeline:
        return None
    rules = pipeline["rules"]
    if not isinstance(rules, list):
        return "pipeline.rules must be an array"
    for i, rule in enumerate(rules):
        if not isinstance(rule, dict):
            return f"rules[{i}] must be an object"
        kind = rule.get("kind", "when")
        if kind not in ("when", "when_not", "then"):
            return f"rules[{i}] unknown kind: {kind!r}"
        if "id" not in rule or "action" not in rule:
            return f"rules[{i}] missing 'id' or 'action'"
        if kind != "then" and "condition" not in rule:
            return f"rules[{i}] missing 'condition'"
    expected = vector["expected"]
    if not isinstance(expected, dict):
        return "expected must be an object"
    if "execution_status" not in expected or "has_finalization" not in expected:
        return "expected missing execution_status or has_finalization"
    return None


def _build_flow(vector: dict[str, Any], ctx: FixtureContext) -> Flow | str:
    """Build a Flow from the vector pipeline. Returns error string on failure."""
    pipeline = vector["pipeline"]

    # Portable IR pipeline: the vector carries a canonical IR document
    # (SPEC 14.2) and the runner rebuilds an executable flow from it.
    if "portable_ir" in pipeline:
        try:
            return Flow.from_ir(pipeline["portable_ir"])
        except Exception as exc:
            return f"portable_ir rejected: {exc}"

    mode_raw = pipeline.get("mode", "FirstMatch")
    try:
        mode = EvaluationMode(mode_raw)
    except ValueError:
        return f"unknown evaluation mode: {mode_raw!r}"

    flow = Flow().with_mode(mode)

    for rule in pipeline["rules"]:
        kind = rule.get("kind", "when")
        try:
            action = resolve_fixture(rule["action"], ctx)
        except (KeyError, ValueError) as exc:
            return f"fixture resolution failed: {exc}"
        rule_effects = tuple(
            Effect(name=str(e["name"]), payload=e.get("payload")) for e in rule.get("effects", [])
        )
        if kind == "then":
            flow.then(action, id=str(rule["id"]), effects=rule_effects)
            continue
        try:
            condition = resolve_fixture(rule["condition"], ctx)
        except (KeyError, ValueError) as exc:
            return f"fixture resolution failed: {exc}"
        guard = None
        if rule.get("guard") is not None:
            try:
                guard = resolve_fixture(rule["guard"], ctx)
            except (KeyError, ValueError) as exc:
                return f"fixture resolution failed: {exc}"
        if kind == "when_not":
            flow.when_not(
                condition,
                then=action,
                id=str(rule["id"]),
                guard=guard,
                priority=int(rule.get("priority", 0)),
                effects=rule_effects,
            )
        else:
            flow.when(
                condition,
                then=action,
                id=str(rule["id"]),
                guard=guard,
                priority=int(rule.get("priority", 0)),
                effects=rule_effects,
            )

    # Exception handlers (SPEC 11.1-11.4). exc_kind names an abstract
    # error kind; the adapter maps it to the concrete exception type.
    for catch in pipeline.get("catches", []):
        ckind = catch.get("kind")
        if ckind == "rethrow":
            flow.rethrow()
            continue
        if ckind == "any":
            try:
                handler = resolve_fixture(catch["handler"], ctx)
            except (KeyError, ValueError) as exc:
                return f"fixture resolution failed: {exc}"
            flow.catch_any(handler, id=catch.get("id"))
            continue
        exc_kind = catch.get("exc_kind")
        exc_type = KIND_MAP.get(exc_kind or "")
        if exc_type is None or not issubclass(exc_type, Exception):
            return f"unknown or uncatchable exc_kind: {exc_kind!r}"
        try:
            handler = resolve_fixture(catch["handler"], ctx)
        except (KeyError, ValueError) as exc:
            return f"fixture resolution failed: {exc}"
        if ckind == "typed":
            flow.catch(exc_type, handler, id=catch.get("id"))
        elif ckind == "when":
            try:
                pred = resolve_fixture(catch["predicate"], ctx)
            except (KeyError, ValueError) as exc:
                return f"fixture resolution failed: {exc}"

            def _predicate(i: Any, e: BaseException, f: Any = pred) -> bool:
                return bool(f(i))

            flow.catch_when(exc_type, _predicate, handler, id=catch.get("id"))
        else:
            return f"unknown catch kind: {ckind!r}"

    # Observable hooks (SPEC 11.5).
    for hook_ref in pipeline.get("on_match", []):
        try:
            hook = resolve_fixture(hook_ref, ctx)
        except (KeyError, ValueError) as exc:
            return f"fixture resolution failed: {exc}"
        flow.on_match(hook)

    # Finalizer (SPEC 11.8): a named cleanup fixture.
    finally_ref = pipeline.get("finally")
    if finally_ref is not None:
        ref = finally_ref if isinstance(finally_ref, dict) else {"fixture": finally_ref}
        try:
            cleanup = resolve_fixture(ref, ctx)
        except (KeyError, ValueError) as exc:
            return f"fixture resolution failed: {exc}"
        flow.finally_(cleanup)
    if pipeline.get("finally_policy") is not None:
        flow.with_finally_policy(str(pipeline["finally_policy"]))
    if pipeline.get("finally_timeout_ms") is not None:
        flow.with_finally_timeout(int(pipeline["finally_timeout_ms"]))

    fallback = pipeline.get("fallback")
    if fallback is not None:
        fkind = fallback.get("kind")
        if fkind == "otherwise":
            try:
                action = resolve_fixture(fallback["action"], ctx)
            except (KeyError, ValueError) as exc:
                return f"fixture resolution failed: {exc}"
            flow.otherwise(action)
        elif fkind == "default_if_no_match":
            flow.default_if_no_match(fallback.get("value"))
        else:
            return f"unknown fallback kind: {fkind!r}"
    return flow


def _resolve_input(vector: dict[str, Any], ctx: FixtureContext) -> tuple[Any, str | None]:
    try:
        return resolve_fixture(vector["input"], ctx), None
    except (KeyError, ValueError) as exc:
        return None, f"fixture resolution failed: {exc}"


def _compare_expected(outcome: FlowOutcome, expected: dict[str, Any]) -> str | None:
    """Compare observed outcome against expected per runner-protocol.md."""
    if outcome.execution_status.name != expected["execution_status"]:
        return (
            f"execution_status: expected {expected['execution_status']}, "
            f"got {outcome.execution_status.name}"
        )

    exp_decision = expected.get("decision_status")
    got_decision = outcome.decision_status.name if outcome.decision_status is not None else None
    if exp_decision != got_decision:
        return f"decision_status: expected {exp_decision}, got {got_decision}"

    if "value" in expected and outcome.value != expected["value"]:
        return f"value: expected {expected['value']!r}, got {outcome.value!r}"

    if expected.get("has_recovery", False) != (outcome.recovery is not None):
        return "has_recovery mismatch"

    if expected.get("has_interruption", False) != (outcome.interruption is not None):
        return "has_interruption mismatch"

    exp_kind = expected.get("interruption_kind")
    got_kind = outcome.interruption.kind if outcome.interruption is not None else None
    if exp_kind != got_kind:
        return f"interruption_kind: expected {exp_kind}, got {got_kind}"

    if expected["has_finalization"] != (outcome.finalization is not None):
        return "has_finalization mismatch"

    exp_clean = expected.get("is_clean")
    got_clean = outcome.finalization.is_clean if outcome.finalization is not None else None
    if exp_clean != got_clean:
        return f"is_clean: expected {exp_clean}, got {got_clean}"

    exp_sec = expected.get("secondary_exceptions_count", 0)
    if exp_sec != len(outcome.secondary_exceptions):
        return (
            f"secondary_exceptions_count: expected {exp_sec}, "
            f"got {len(outcome.secondary_exceptions)}"
        )

    exp_primary = expected.get("primary_exception_kind")
    got_primary = (
        kind_of_exception(outcome.primary_exception)
        if outcome.primary_exception is not None
        else None
    )
    if exp_primary != got_primary:
        return f"primary_exception_kind: expected {exp_primary}, got {got_primary}"

    exp_effects = expected.get("effects")
    if exp_effects is not None:
        got_effects = [{"name": e.name, "payload": e.payload} for e in outcome.effects]
        normalized = [{"name": e.get("name"), "payload": e.get("payload")} for e in exp_effects]
        if got_effects != normalized:
            return f"effects: expected {normalized!r}, got {got_effects!r}"

    return None


def _compare_trace(vector: dict[str, Any], outcome: FlowOutcome) -> str | None:
    """Compare observed trace per runner-protocol.md trace rules."""
    expected_events = vector.get("trace")
    if expected_events is None:
        return None
    if outcome.trace is None:
        return "trace expected but trace was not collected"
    observed = [
        {"type": e.type, "rule_id": e.rule_id, "reason": e.reason} for e in outcome.trace.events
    ]
    expected = [
        {"type": e.get("type"), "rule_id": e.get("rule_id"), "reason": e.get("reason")}
        for e in expected_events
    ]

    def _matches(obs: dict[str, Any], exp: dict[str, Any]) -> bool:
        if obs["type"] != exp["type"]:
            return False
        if exp.get("rule_id") is not None and obs["rule_id"] != exp["rule_id"]:
            return False
        return exp.get("reason") is None or obs["reason"] == exp["reason"]

    if vector.get("trace_subset"):
        # Every expected event must appear in order; extras allowed.
        pos = 0
        for exp in expected:
            found = False
            while pos < len(observed):
                if _matches(observed[pos], exp):
                    found = True
                    pos += 1
                    break
                pos += 1
            if not found:
                return f"trace subset: missing event {exp!r}"
        return None

    if len(observed) != len(expected):
        return f"trace length: expected {len(expected)}, got {len(observed)}"
    for i, (obs, exp) in enumerate(zip(observed, expected, strict=True)):
        if not _matches(obs, exp):
            return f"trace[{i}]: expected {exp!r}, got {obs!r}"
    return None


def run_vector(path: Path) -> VectorResult:
    """Run a single vector file. Never raises; returns PASS/FAIL result."""
    vector_id = path.stem
    try:
        vector = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return VectorResult(vector_id, False, f"runner failure: cannot parse: {exc}")
    if not isinstance(vector, dict):
        return VectorResult(vector_id, False, "runner failure: vector is not an object")

    vector_id = str(vector.get("id", vector_id))

    version_error = _check_spec_version(vector)
    if version_error is not None:
        return VectorResult(vector_id, False, f"runner failure: {version_error}")

    shape_error = _validate_vector_shape(vector)
    if shape_error is not None:
        return VectorResult(vector_id, False, f"runner failure: {shape_error}")

    ctx = FixtureContext()
    expected_error = vector.get("expected_error")

    built = _build_flow(vector, ctx)
    if isinstance(built, str):
        if expected_error is not None:
            return VectorResult(vector_id, expected_error in built, built)
        return VectorResult(vector_id, False, built)

    input_value, input_error = _resolve_input(vector, ctx)
    if input_error is not None:
        if expected_error is not None:
            return VectorResult(vector_id, expected_error in input_error, input_error)
        return VectorResult(vector_id, False, input_error)

    try:
        contract = built.compile()
    except Exception as exc:  # StructureError and friends
        if expected_error is not None:
            return VectorResult(vector_id, expected_error in str(exc), f"compile failed: {exc}")
        return VectorResult(vector_id, False, f"compile failed: {exc}")

    clock = FakeClock()
    trace_enabled = "trace" in vector
    try:
        if vector["pipeline"].get("execution") == "async":
            outcome = asyncio.run(
                contract.try_execute_async(input_value, clock=clock, trace=trace_enabled)
            )
        else:
            outcome = contract.try_execute(input_value, clock=clock, trace=trace_enabled)
    except Exception as exc:
        if expected_error is not None:
            return VectorResult(vector_id, expected_error in str(exc), f"execution raised: {exc}")
        raise

    if expected_error is not None:
        return VectorResult(
            vector_id,
            False,
            f"expected rejection containing {expected_error!r} but execution completed",
        )

    mismatch = _compare_expected(outcome, vector["expected"])
    if mismatch is not None:
        return VectorResult(vector_id, False, mismatch)

    trace_error = _compare_trace(vector, outcome)
    if trace_error is not None:
        return VectorResult(vector_id, False, trace_error)

    return VectorResult(vector_id, True)


def discover_vectors(vectors_dir: Path) -> list[Path]:
    """Recursively discover *.json vector files (runner-protocol.md)."""
    return sorted(vectors_dir.rglob("*.json"))


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns 0 iff all discovered vectors pass."""
    parser = argparse.ArgumentParser(
        prog="flowsemantics-conformance",
        description="Run FlowSemantics conformance vectors.",
    )
    parser.add_argument(
        "--vectors",
        type=Path,
        required=True,
        help="Directory containing vector JSON files (searched recursively).",
    )
    args = parser.parse_args(argv)

    vectors_dir: Path = args.vectors
    if not vectors_dir.is_dir():
        print(f"ERROR: vectors directory not found: {vectors_dir}", file=sys.stderr)
        return 2

    paths = discover_vectors(vectors_dir)
    if not paths:
        print("RESULT: 0/0 passed (no vectors discovered)")
        return 0

    passed = 0
    for path in paths:
        result = run_vector(path)
        if result.passed:
            passed += 1
            print(f"PASS {result.vector_id}")
        else:
            print(f"FAIL {result.vector_id}: {result.reason}")

    total = len(paths)
    print(f"RESULT: {passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
