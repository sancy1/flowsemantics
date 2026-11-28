"""flowsemantics.configuration.flow - Flow builder and FlowContract.

Layer:      Composition
Module:     flowsemantics.configuration.flow
Since:      0.1.0
Implements: SPEC.md sections 4.1 (two-stage lifecycle), 10.1-10.6, 10.9
Depends on: flowsemantics.configuration.rule, flowsemantics.errors,
            flowsemantics.execution.{clock,context,outcome}
Used by:    consumers, conformance runner, samples
See also:   SPEC.md section 10

Notes:
  - Flow is the mutable construction-stage builder. It MUST NOT execute any
    condition, transformation, or effect during construction (SPEC 4.1.1).
  - FlowContract is the immutable execution-stage artifact produced by
    compile(). It is reusable and safe to share across concurrent
    invocations; user callbacks are NOT guaranteed thread-safe (SPEC 4.2).
  - Implemented here: when, when_not, then, otherwise,
    default/default_if_no_match, EvaluationMode (all three modes),
    compile(), execute(), try_execute(). Merge, DecisionTable, catch
    rules, finalizers, hooks, trace, and portability export arrive in
    their own sub-phases.
  - SPEC.md v0.1 does not define how a rule declares REJECTED polarity;
    a matched rule therefore yields APPROVED. REJECTED arrives with the
    API that defines it (tracked as a spec gap, not silently invented).
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import inspect
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, cast

from flowsemantics._spec import SPEC_VERSION
from flowsemantics.configuration.catch import (
    CatchRule,
    ExceptionHandler,
    ExceptionPredicate,
)
from flowsemantics.configuration.finalization import (
    FinallyCancellationToken,
    FinallyContext,
    FinallyFailurePolicy,
)
from flowsemantics.configuration.portable import (
    PExpr,
    PortableFlow,
    PortableRule,
    _parse_dt,
    eval_expr,
    expr_to_dict,
)
from flowsemantics.configuration.rule import (
    ActionFn,
    ConditionFn,
    GuardFn,
    Rule,
    RuleId,
    RuleKind,
)
from flowsemantics.errors import (
    AsyncOnlyContractError,
    PortabilityError,
    StructureError,
)
from flowsemantics.execution.clock import Clock, SystemClock
from flowsemantics.execution.context import FlowContext
from flowsemantics.execution.outcome import (
    DecisionStatus,
    Effect,
    ExecutionStatus,
    FinalizationInfo,
    FlowOutcome,
    InterruptionInfo,
    RecoveryInfo,
)
from flowsemantics.execution.trace import ExecutionTrace, TraceRecorder


class EvaluationMode(StrEnum):
    """Multiple-match behavior. Exactly three members (SPEC 10.6)."""

    FIRST_MATCH = "FirstMatch"
    ALL_MATCH = "AllMatch"
    PRIORITY = "Priority"


class FlowPortability(StrEnum):
    """Whole-contract portability classification (SPEC 4.4, feature 47)."""

    PORTABLE = "portable"
    NATIVE = "native"


@dataclass(frozen=True)
class Fallback:
    """No-match fallback configuration (SPEC 10.4)."""

    kind: str  # "otherwise" | "default_if_no_match"
    action: ActionFn | None = None
    value: Any = None


class Flow:
    """Mutable builder for a flow. Construction performs no execution."""

    def __init__(self) -> None:
        """Create an empty flow builder in FirstMatch mode."""
        self._rules: list[Rule] = []
        self._fallback: Fallback | None = None
        self._mode: EvaluationMode = EvaluationMode.FIRST_MATCH
        self._clock: Clock | None = None
        self._catches: list[CatchRule] = []
        self._hooks: list[Callable[[Any, str, Any], Any]] = []
        self._finalizers: list[Callable[[FinallyContext], None]] = []
        self._finally_policy: FinallyFailurePolicy = FinallyFailurePolicy.PRESERVE_PRIMARY
        self._finally_timeout_ms: int | None = None
        self._trace_enabled: bool = False
        self._trace_hook: Callable[[Any], dict[str, Any] | None] | None = None
        self._portable_rules: list[PortableRule] = []
        self._flow_id: str = ""
        self._cancel_check: Callable[[], bool] | None = None

    # -- rule registration -------------------------------------------------

    def when(
        self,
        condition: ConditionFn,
        *,
        then: ActionFn,
        id: str | RuleId,
        guard: GuardFn | None = None,
        priority: int = 0,
        effective_from: datetime.datetime | None = None,
        effective_until: datetime.datetime | None = None,
        effects: Iterable[Effect] = (),
    ) -> Flow:
        """Register a positive condition rule (SPEC 10.2, 12.9).

        effects are proposed (never applied) in evaluation order when the
        rule matches (SPEC 5, 6.4, 14.2).
        """
        self._rules.append(
            Rule(
                id=self._coerce_id(id),
                kind="when",
                condition=condition,
                guard=guard,
                action=then,
                priority=priority,
                effective_from=effective_from,
                effective_until=effective_until,
                effects=tuple(effects),
            )
        )
        return self

    def when_not(
        self,
        condition: ConditionFn,
        *,
        then: ActionFn,
        id: str | RuleId,
        guard: GuardFn | None = None,
        priority: int = 0,
        effective_from: datetime.datetime | None = None,
        effective_until: datetime.datetime | None = None,
        effects: Iterable[Effect] = (),
    ) -> Flow:
        """Register a negative condition rule (SPEC 10.2, 12.9)."""
        self._rules.append(
            Rule(
                id=self._coerce_id(id),
                kind="when_not",
                condition=condition,
                guard=guard,
                action=then,
                priority=priority,
                effective_from=effective_from,
                effective_until=effective_until,
                effects=tuple(effects),
            )
        )
        return self

    def when_expr(
        self,
        condition: PExpr,
        *,
        then: PExpr,
        id: str | RuleId,
        guard: PExpr | None = None,
        priority: int = 0,
        effective_from: datetime.datetime | None = None,
        effective_until: datetime.datetime | None = None,
        effects: Iterable[Effect] = (),
    ) -> Flow:
        """Register a portable rule (SPEC 14.2).

        Condition, guard, and transform are declarative expressions from
        the portable subset; no host lambdas are involved. Effects are
        proposed data carried in the IR (SPEC 14.2).
        """
        self._portable_rules.append(
            PortableRule(
                rule_id=str(self._coerce_id(id)),
                kind="when",
                condition=condition,
                guard=guard,
                transform=then,
                priority=priority,
                effective_from=(effective_from.isoformat() if effective_from else None),
                effective_until=(effective_until.isoformat() if effective_until else None),
                effects=tuple({"name": e.name, "payload": e.payload} for e in effects),
            )
        )
        return self

    def when_not_expr(
        self,
        condition: PExpr,
        *,
        then: PExpr,
        id: str | RuleId,
        guard: PExpr | None = None,
        priority: int = 0,
        effective_from: datetime.datetime | None = None,
        effective_until: datetime.datetime | None = None,
        effects: Iterable[Effect] = (),
    ) -> Flow:
        """Register a negated portable rule (SPEC 14.2)."""
        self._portable_rules.append(
            PortableRule(
                rule_id=str(self._coerce_id(id)),
                kind="when_not",
                condition=condition,
                guard=guard,
                transform=then,
                priority=priority,
                effective_from=(effective_from.isoformat() if effective_from else None),
                effective_until=(effective_until.isoformat() if effective_until else None),
                effects=tuple({"name": e.name, "payload": e.payload} for e in effects),
            )
        )
        return self

    def with_flow_id(self, flow_id: str) -> Flow:
        """Set the flow identifier carried in the Portable IR (SPEC 14.2)."""
        self._flow_id = flow_id
        return self

    @classmethod
    def from_ir(cls, data: dict[str, Any] | str) -> Flow:
        """Build a Flow from a Portable IR document (SPEC 14.2).

        Accepts a dict or JSON string produced by PortableFlow.to_dict/
        to_json. Only when/when_not rules with declarative expressions
        are supported; 'then' stages and dynamic fallbacks are rejected.
        """
        ir = PortableFlow.from_json(data) if isinstance(data, str) else PortableFlow.from_dict(data)
        if ir.portability != "PORTABLE":
            raise StructureError("IR portability must be PORTABLE")
        flow = cls().with_flow_id(ir.flow_id).with_mode(ir.mode)
        for r in ir.rules:
            if r.kind not in ("when", "when_not"):
                raise StructureError(f"portable IR kind {r.kind!r} not supported in from_ir")
            if r.condition is None or r.transform is None:
                raise StructureError("portable rule requires condition+transform")
            method = flow.when_expr if r.kind == "when" else flow.when_not_expr
            method(
                r.condition,
                then=r.transform,
                id=r.rule_id,
                guard=r.guard,
                priority=r.priority,
                effective_from=_parse_dt(r.effective_from),
                effective_until=_parse_dt(r.effective_until),
                effects=tuple(Effect(name=e["name"], payload=e.get("payload")) for e in r.effects),
            )
        if ir.fallback is not None:
            fb = ir.fallback
            if fb.get("kind") == "default_if_no_match":
                flow.default(fb.get("value"))
            elif fb.get("kind") == "otherwise" and "value" in fb:
                flow.default(fb["value"])
            else:
                raise StructureError(f"unsupported portable fallback kind: {fb.get('kind')!r}")
        return flow

    def then(
        self,
        stage: Callable[[Any, Any], Any],
        *,
        id: str | RuleId,
        effects: Iterable[Effect] = (),
    ) -> Flow:
        """Register a sequential stage (SPEC 10.5).

        The stage receives (input, previous_output) and runs only when the
        preceding rule matched. It cannot be the first element of a flow;
        compile() enforces that.
        """
        self._rules.append(
            Rule(
                id=self._coerce_id(id),
                kind="then",
                condition=None,
                guard=None,
                action=stage,
                effects=tuple(effects),
            )
        )
        return self

    # -- fallbacks ---------------------------------------------------------

    def otherwise(self, action: ActionFn) -> Flow:
        """Register a dynamic no-match fallback (SPEC 10.4)."""
        self._set_fallback(Fallback(kind="otherwise", action=action))
        return self

    def default_if_no_match(self, value: Any) -> Flow:
        """Register a constant no-match fallback (SPEC 10.4)."""
        self._set_fallback(Fallback(kind="default_if_no_match", value=value))
        return self

    def default(self, value: Any) -> Flow:
        """Alias of default_if_no_match (SPEC 10.4)."""
        return self.default_if_no_match(value)

    # -- exception handling (SPEC 11.1-11.4) ---------------------------------

    def catch(
        self,
        exc_type: type[Exception],
        handler: ExceptionHandler,
        *,
        id: str | None = None,
    ) -> Flow:
        """Register a typed exception handler (SPEC 11.1).

        The handler receives (input, exception) and returns the outcome
        value. Matching follows host-language inheritance: a handler for a
        base type catches subclasses.
        """
        self._catches.append(CatchRule(kind="typed", exc_type=exc_type, handler=handler, id=id))
        return self

    def catch_when(
        self,
        exc_type: type[Exception],
        predicate: ExceptionPredicate,
        handler: ExceptionHandler,
        *,
        id: str | None = None,
    ) -> Flow:
        """Register a typed handler with a predicate (SPEC 11.2).

        The predicate receives (input, exception) and is evaluated only
        after the type check passes.
        """
        self._catches.append(
            CatchRule(
                kind="when",
                exc_type=exc_type,
                predicate=predicate,
                handler=handler,
                id=id,
            )
        )
        return self

    def catch_any(self, handler: ExceptionHandler, *, id: str | None = None) -> Flow:
        """Register a broad handler for otherwise-uncaught exceptions (SPEC 11.3).

        MUST be registered after all typed catch/catch_when rules;
        compile() enforces the ordering.
        """
        self._catches.append(CatchRule(kind="any", handler=handler, id=id))
        return self

    def rethrow(self) -> Flow:
        """Register explicit propagation of the current exception (SPEC 11.4)."""
        self._catches.append(CatchRule(kind="rethrow"))
        return self

    def on_match(self, hook: Callable[[Any, str, Any], Any]) -> Flow:
        """Register an observable hook (SPEC 11.5).

        The hook receives (input, RuleId, value) after a when/when_not
        rule's action produces its value. Hook failures are isolated into
        secondary_exceptions and never trigger catch rules.
        """
        self._hooks.append(hook)
        return self

    def finally_(self, cleanup: Callable[[FinallyContext], None]) -> Flow:
        """Register a finalizer that runs after primary execution (SPEC 11.8).

        The finalizer receives a FinallyContext and runs for every outcome
        status, including CANCELLED and TIMED_OUT. Finalizers run in LIFO
        order and are isolated: a failure in one does not skip the rest.
        """
        self._finalizers.append(cleanup)
        return self

    def finally_async(self, cleanup: Callable[[FinallyContext], Any]) -> Flow:
        """Register an asynchronous finalizer (SPEC 11.8, 16.7).

        A flow with async finalizers is async-only: every finalizer must
        be async, and the contract can only run via execute_async()
        (SPEC 11.7, FR8).
        """
        self._finalizers.append(cleanup)
        return self

    def with_finally_policy(self, policy: FinallyFailurePolicy | str) -> Flow:
        """Set the finally failure policy (SPEC 11.8.3, 16.4)."""
        self._finally_policy = FinallyFailurePolicy(policy)
        return self

    def with_finally_timeout(self, ms: int) -> Flow:
        """Bound each finalizer's budget in milliseconds (SPEC 16.7)."""
        if ms < 1:
            raise StructureError("finally timeout must be >= 1ms (SPEC 16.7)")
        self._finally_timeout_ms = ms
        return self

    def with_trace(
        self,
        diagnostic_hook: Callable[[Any], dict[str, Any] | None] | None = None,
    ) -> Flow:
        """Enable tracing for executions of this flow (SPEC 12.3, 12.2).

        diagnostic_hook is the application-supplied redaction-aware hook:
        it receives each TraceEvent and may return extra diagnostic fields.
        """
        self._trace_enabled = True
        self._trace_hook = diagnostic_hook
        return self

    # -- configuration -----------------------------------------------------

    def with_cancel_check(self, check: Callable[[], bool]) -> Flow:
        """Register a cooperative cancellation predicate (SPEC 11.6).

        The predicate is polled before each rule evaluation; when it
        returns True the contract produces a CANCELLED outcome via an
        interruption, bypassing catch rules entirely.
        """
        self._cancel_check = check
        return self

    def with_mode(self, mode: EvaluationMode | str) -> Flow:
        """Set the evaluation mode (SPEC 10.6)."""
        self._mode = EvaluationMode(mode)
        return self

    def with_clock(self, clock: Clock) -> Flow:
        """Inject a deterministic clock (SPEC 6.2)."""
        self._clock = clock
        return self

    def merge(self, other: Flow | FlowContract) -> Flow:
        """Splice another flow's rules and fallback at the call site (SPEC 10.7).

        Rules:
          - Both flows MUST share the same EvaluationMode; mismatch raises
            StructureError.
          - RuleIds MUST be unique across the combined flow.
          - If both flows have a fallback, the outer (self) fallback wins
            and the inner fallback is discarded.
          - Catch scoping and LIFO finalizer ordering complete in Phase 2.5.
        """
        other_catches: list[CatchRule]
        other_finalizers: list[Callable[[FinallyContext], None]]
        if isinstance(other, FlowContract):
            other_rules = list(other.rules)
            other_fallback = other.fallback
            other_mode = other.mode
            other_catches = list(other.catches)
            other_finalizers = list(other.finalizers)
        else:
            other_rules = list(other._rules)
            other_fallback = other._fallback
            other_mode = other._mode
            other_catches = list(other._catches)
            other_finalizers = list(other._finalizers)

        if other_mode is not self._mode:
            raise StructureError(
                f"cannot merge flows with different EvaluationMode: "
                f"{self._mode} vs {other_mode} (SPEC 10.7)"
            )

        existing = {str(rule.id) for rule in self._rules}
        for rule in other_rules:
            if str(rule.id) in existing:
                raise StructureError(f"merge would produce duplicate RuleId: {rule.id} (SPEC 10.7)")
            existing.add(str(rule.id))

        self._rules.extend(other_rules)
        self._catches.extend(other_catches)
        self._finalizers.extend(other_finalizers)
        if self._fallback is None and other_fallback is not None:
            self._fallback = other_fallback
        return self

    # -- compilation -------------------------------------------------------

    def compile(self) -> FlowContract:
        """Validate and produce an immutable FlowContract (SPEC 10.9)."""
        if self._portable_rules and self._rules:
            raise StructureError(
                "cannot mix portable (when_expr) and native (when) rules "
                "in one flow; a contract is either PORTABLE or NATIVE"
            )
        portable_ir: PortableFlow | None = None
        portability = FlowPortability.NATIVE
        if self._portable_rules:
            rules = self._compile_portable_rules()
            # The IR carries rules, mode, fallback, and dates only
            # (SPEC 14.2). Catches, finalizers, and hooks are not
            # representable, so their presence makes the contract NATIVE
            # (SPEC 4.4, D3) rather than silently dropping them.
            if not (self._catches or self._finalizers or self._hooks):
                portability = FlowPortability.PORTABLE
                portable_ir = self._build_ir()
        else:
            rules = self._normalized_rules()
        self._validate(rules)
        self._validate_finalizer_forms()
        async_only = _compute_async_only(
            rules=rules,
            catches=self._catches,
            hooks=self._hooks,
            finalizers=self._finalizers,
        )
        return FlowContract(
            rules=tuple(rules),
            fallback=self._fallback,
            mode=self._mode,
            clock=self._clock if self._clock is not None else SystemClock(),
            spec_version=SPEC_VERSION,
            portability=portability,
            portable_ir=portable_ir,
            catches=tuple(self._catches),
            hooks=tuple(self._hooks),
            finalizers=tuple(self._finalizers),
            finally_policy=self._finally_policy,
            finally_timeout_ms=self._finally_timeout_ms,
            trace_enabled=self._trace_enabled,
            trace_diagnostic_hook=self._trace_hook,
            async_only=async_only,
            cancel_check=self._cancel_check,
            contract_version=_compute_contract_version(
                rules=rules,
                fallback=self._fallback,
                mode=self._mode,
                catches=self._catches,
                finalizers=self._finalizers,
                finally_policy=self._finally_policy,
                finally_timeout_ms=self._finally_timeout_ms,
                trace_enabled=self._trace_enabled,
                portable_rules=self._portable_rules,
            ),
        )

    def _compile_portable_rules(self) -> list[Rule]:
        """Convert portable rules to executable Rules (SPEC 14.2)."""
        rules: list[Rule] = []
        for pr in self._portable_rules:
            assert pr.condition is not None and pr.transform is not None
            for eff in pr.effects:
                try:
                    json.dumps(eff.get("payload"))
                except (TypeError, ValueError) as exc:
                    raise StructureError(
                        f"portable rule {pr.rule_id}: effect payload must be "
                        "JSON-serializable to be carried in the IR (SPEC 14.2)"
                    ) from exc
            cond = pr.condition
            guard = pr.guard
            transform = pr.transform

            # kind="when_not" is negated by the engine (_condition_holds);
            # the compiled condition stays positive.
            def _cond(i: Any, c: PExpr = cond) -> bool:
                return bool(eval_expr(c, i))

            def _guard_fn(i: Any, g: PExpr | None = guard) -> bool:
                assert g is not None
                return bool(eval_expr(g, i))

            def _action(i: Any, t: PExpr = transform) -> Any:
                return eval_expr(t, i)

            rules.append(
                Rule(
                    id=RuleId(pr.rule_id),
                    kind=cast(RuleKind, pr.kind),
                    condition=_cond,
                    guard=_guard_fn if guard is not None else None,
                    action=_action,
                    priority=pr.priority,
                    effective_from=_parse_dt(pr.effective_from),
                    effective_until=_parse_dt(pr.effective_until),
                    effects=tuple(
                        Effect(name=e["name"], payload=e.get("payload")) for e in pr.effects
                    ),
                )
            )
        return rules

    def _build_ir(self) -> PortableFlow:
        """Build the PortableFlow IR for this contract (SPEC 14.2)."""
        ir_rules = tuple(self._portable_rules)
        fallback_dict: dict[str, Any] | None = None
        if self._fallback is not None:
            fb = self._fallback
            fallback_dict = {"kind": fb.kind}
            if fb.kind == "default_if_no_match":
                fallback_dict["value"] = fb.value
        return PortableFlow(
            spec_version=SPEC_VERSION,
            flow_id=self._flow_id,
            portability="PORTABLE",
            mode=str(self._mode),
            rules=ir_rules,
            fallback=fallback_dict,
        )

    def _validate_finalizer_forms(self) -> None:
        """A flow MUST NOT mix sync and async finalizers (SPEC 11.8, FR8)."""
        if not self._finalizers:
            return
        forms = {_is_async_callable(f) for f in self._finalizers}
        if len(forms) > 1:
            raise StructureError(
                "cannot mix synchronous and asynchronous finalizers; "
                "a flow with finally_async must register only async "
                "finalizers (SPEC 11.8, FR8)"
            )

    def _normalized_rules(self) -> list[Rule]:
        """Return rules with then-stages inheriting the preceding priority."""
        rules = list(self._rules)
        previous_priority = 0
        for index, rule in enumerate(rules):
            if rule.kind == "then":
                rules[index] = replace(rule, priority=previous_priority)
            else:
                previous_priority = rule.priority
        return rules

    def _validate(self, rules: list[Rule]) -> None:
        seen: set[str] = set()
        for rule in rules:
            key = str(rule.id)
            if key in seen:
                raise StructureError(f"duplicate RuleId: {key!r}")
            seen.add(key)
        if not rules and self._fallback is None:
            raise StructureError(
                "flow has neither rules nor a fallback; at least one is required (SPEC 4.3)"
            )
        for index, rule in enumerate(rules):
            if rule.kind != "then":
                continue
            if index == 0:
                raise StructureError("then cannot be the first element of a flow (SPEC 10.5)")
            if rules[index - 1].kind not in ("when", "when_not", "then"):
                raise StructureError(f"then at index {index} does not follow a rule (SPEC 10.5)")
        for rule in rules:
            if (
                rule.effective_from is not None
                and rule.effective_until is not None
                and rule.effective_from >= rule.effective_until
            ):
                raise StructureError(
                    f"rule {rule.id}: effective_from must be before effective_until (SPEC 12.9)"
                )
        self._validate_catches()

    def _validate_catches(self) -> None:
        """Enforce catch ordering rules (SPEC 11.3, 4.3)."""
        seen_any = False
        for catch in self._catches:
            if catch.kind == "any":
                seen_any = True
            elif seen_any and catch.kind in ("typed", "when"):
                raise StructureError(
                    "catch_any MUST be registered after all typed catch "
                    "and catch_when rules (SPEC 11.3)"
                )

    @classmethod
    def from_table(cls, table: Any) -> Flow:
        """Build a Flow from a DecisionTable (SPEC 10.8).

        Accepts a DecisionTable; compiles each row to an equivalent when
        rule. Hit policy maps to EvaluationMode per SPEC 10.8.
        """
        from flowsemantics.configuration.table import table_to_flow

        return table_to_flow(table)

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _coerce_id(id: str | RuleId) -> RuleId:
        return id if isinstance(id, RuleId) else RuleId(id)

    def _set_fallback(self, fallback: Fallback) -> None:
        if self._fallback is not None:
            raise StructureError(
                "at most one of otherwise, default, default_if_no_match "
                "may be configured per flow (SPEC 10.4)"
            )
        self._fallback = fallback


@dataclass(frozen=True)
class FlowContract:
    """Immutable, reusable execution definition produced by compile()."""

    rules: tuple[Rule, ...]
    fallback: Fallback | None
    mode: EvaluationMode
    clock: Clock
    spec_version: str
    portability: FlowPortability
    catches: tuple[CatchRule, ...] = ()
    hooks: tuple[Callable[[Any, str, Any], Any], ...] = ()
    finalizers: tuple[Callable[[FinallyContext], Any], ...] = ()
    finally_policy: FinallyFailurePolicy = FinallyFailurePolicy.PRESERVE_PRIMARY
    finally_timeout_ms: int | None = None
    trace_enabled: bool = False
    trace_diagnostic_hook: Callable[[Any], dict[str, Any] | None] | None = None
    portable_ir: PortableFlow | None = None
    async_only: bool = False
    cancel_check: Callable[[], bool] | None = None
    contract_version: str = field(default="1")

    # -- portable IR (SPEC 14.2) -------------------------------------------

    def to_ir(self) -> PortableFlow:
        """Export the contract as a PortableFlow IR document.

        Only PORTABLE contracts carry an IR; NATIVE contracts raise
        PortabilityError (SPEC 4.4, 14.2).
        """
        if self.portable_ir is None:
            raise PortabilityError(
                "contract is NATIVE; only PORTABLE contracts can be "
                "exported to the Portable IR (SPEC 14.2)"
            )
        return replace(self.portable_ir, contract_version=self.contract_version)

    def to_ir_json(self) -> str:
        """Export the contract as canonical Portable IR JSON."""
        return self.to_ir().to_json()

    # -- trust layer (SPEC section 12) -------------------------------------

    def simulate(self, input: Any, *, clock: Clock | None = None) -> FlowOutcome:
        """Evaluate without effects, hooks, or finalizers (SPEC 12.5).

        Produces the same decision semantics as a real execution for the
        same input and clock, except finalization is not performed and
        on_match hooks are suppressed.
        """
        sim_contract = replace(self, hooks=())
        ctx = FlowContext(input=input, clock=clock if clock is not None else self.clock)
        return sim_contract._primary(ctx, None)

    def simulate_batch(
        self, inputs: Iterable[Any], *, clock: Clock | None = None
    ) -> dict[str, Any]:
        """Batch simulation with firing distribution (SPEC 12.5).

        Runs simulate() over each input and aggregates outcomes by
        execution status, decision status, and produced value.
        """
        by_status: dict[str, int] = {}
        by_decision: dict[str, int] = {}
        by_value: dict[str, int] = {}
        outcomes: list[FlowOutcome] = []
        for inp in inputs:
            outcome = self.simulate(inp, clock=clock)
            outcomes.append(outcome)
            by_status[outcome.execution_status.value] = (
                by_status.get(outcome.execution_status.value, 0) + 1
            )
            dkey = outcome.decision_status.value if outcome.decision_status else "null"
            by_decision[dkey] = by_decision.get(dkey, 0) + 1
            vkey = json.dumps(outcome.value, default=str, sort_keys=True)
            by_value[vkey] = by_value.get(vkey, 0) + 1
        return {
            "total": len(outcomes),
            "by_status": by_status,
            "by_decision": by_decision,
            "by_value": by_value,
            "outcomes": outcomes,
        }

    def portability_report(self) -> dict[str, Any]:
        """Portability classification + offending components (SPEC 4.4)."""
        if self.portable_ir is None:
            return {"classification": "NATIVE", "offenders": ["native rules"]}
        offenders: list[str] = []
        if self.catches:
            offenders.append("catches")
        if self.finalizers:
            offenders.append("finalizers")
        if self.hooks:
            offenders.append("hooks")
        return {
            "classification": "PORTABLE" if not offenders else "NATIVE",
            "offenders": offenders,
        }

    def explain(self, trace: ExecutionTrace) -> str:
        """Render a trace as human-readable lines (SPEC 12.4).

        The rationale is derived only from trace events and registered
        rule ids; no reasons are invented.
        """
        lines = [f"FlowContract {trace.contract_version}: {len(trace.events)} event(s)"]
        for event in trace.events:
            lines.append(_explain_event(event))
        return "\n".join(lines)

    def validate(self) -> tuple[ValidationIssue, ...]:
        """Static analysis without execution (SPEC 12.8).

        Returns issues distinguishing errors (block compilation) from
        warnings (should investigate). A compiled contract is expected to
        have no errors; warnings may remain.
        """
        issues: list[ValidationIssue] = []
        if not self.rules and self.fallback is None:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="empty_flow",
                    message="flow has neither rules nor a fallback",
                )
            )
        seen: set[str] = set()
        for rule in self.rules:
            rid = str(rule.id)
            if rid in seen:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="duplicate_rule_id",
                        message=f"duplicate RuleId: {rid}",
                        rule_id=rid,
                    )
                )
            seen.add(rid)
        seen_any = False
        for catch in self.catches:
            if catch.kind == "any":
                seen_any = True
            elif seen_any and catch.kind in ("typed", "when"):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="catch_any_ordering",
                        message="typed catch registered after catch_any",
                    )
                )
        for rule in self.rules:
            if (
                rule.effective_from is not None
                and rule.effective_until is not None
                and rule.effective_from >= rule.effective_until
            ):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="invalid_effective_window",
                        message="effective_from must be before effective_until",
                        rule_id=str(rule.id),
                    )
                )
        # Unreachable / overlap analysis is only provable for portable
        # const-true and structurally identical conditions (SPEC 12.8).
        if self.portable_ir is not None:
            prs = [r for r in self.portable_ir.rules if r.kind != "then"]
            if self.mode is not EvaluationMode.ALL_MATCH:
                unconditional = False
                for pr in prs:
                    rid = str(pr.rule_id)
                    if unconditional:
                        issues.append(
                            ValidationIssue(
                                severity="warning",
                                code="unreachable_rule",
                                message=(
                                    "rule cannot match: an earlier unconditional "
                                    "rule always matches first"
                                ),
                                rule_id=rid,
                            )
                        )
                        continue
                    cond = pr.condition
                    if cond is not None and cond.op == "const" and cond.value is True:
                        unconditional = True
            # O(n) overlap detection: group by (kind, canonical condition)
            # then compare only within each group (SPEC 12.8).
            groups: dict[tuple[str, str], list] = {}
            for pr in prs:
                key = (
                    pr.kind,
                    json.dumps(expr_to_dict(pr.condition), sort_keys=True)
                    if pr.condition is not None
                    else "null",
                )
                groups.setdefault(key, []).append(pr)
            for members in groups.values():
                for i, a in enumerate(members):
                    for b in members[i + 1 :]:
                        issues.append(
                            ValidationIssue(
                                severity="warning",
                                code="overlapping_rules",
                                message=("rules have structurally identical conditions"),
                                rule_id=str(b.rule_id),
                            )
                        )
        if self.fallback is None and self.rules:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="possible_gap",
                    message="no fallback configured; some inputs may produce NO_MATCH",
                )
            )
        return tuple(issues)

    # -- execution ---------------------------------------------------------

    def execute(self, input: Any, *, clock: Clock | None = None) -> FlowOutcome:
        """Execute and propagate an unrecovered exception (SPEC 11.4, D13)."""
        if self.async_only:
            raise AsyncOnlyContractError(
                "contract is async-only; use execute_async() (SPEC 11.7, FR8)"
            )
        outcome = self.try_execute(input, clock=clock)
        if (
            outcome.execution_status is ExecutionStatus.FAILED
            and outcome.primary_exception is not None
        ):
            raise outcome.primary_exception
        return outcome

    def try_execute(
        self,
        input: Any,
        *,
        clock: Clock | None = None,
        trace: bool | None = None,
        diagnostic_hook: Callable[[Any], dict[str, Any] | None] | None = None,
    ) -> FlowOutcome:
        """Execute and always return a FlowOutcome (SPEC 11.4, D13).

        trace=True enables trace collection for this execution even when
        the contract was not built with_trace() (SPEC 12.3).
        diagnostic_hook overrides the contract-level hook for this call.
        """
        ctx = FlowContext(input=input, clock=clock if clock is not None else self.clock)
        if self.async_only:
            raise AsyncOnlyContractError(
                "contract is async-only; use try_execute_async() (SPEC 11.7)"
            )
        enabled = self.trace_enabled if trace is None else trace
        hook = diagnostic_hook if diagnostic_hook is not None else self.trace_diagnostic_hook
        rec = TraceRecorder(self.contract_version, hook) if enabled else None
        primary = self._primary(ctx, rec)
        outcome = _finalize(self, ctx, primary, rec)
        if rec is not None:
            outcome = replace(outcome, trace=rec.build())
        return outcome

    async def execute_async(self, input: Any, *, clock: Clock | None = None) -> FlowOutcome:
        """Async execution; propagates an unrecovered exception (SPEC 11.7)."""
        outcome = await self.try_execute_async(input, clock=clock)
        if (
            outcome.execution_status is ExecutionStatus.FAILED
            and outcome.primary_exception is not None
        ):
            raise outcome.primary_exception
        return outcome

    async def try_execute_async(
        self,
        input: Any,
        *,
        clock: Clock | None = None,
        trace: bool | None = None,
        diagnostic_hook: Callable[[Any], dict[str, Any] | None] | None = None,
    ) -> FlowOutcome:
        """Async execution returning a FlowOutcome (SPEC 11.7).

        Awaits every user-supplied callback that returns an awaitable;
        sync and async paths produce identical outcomes for the same
        contract and input.
        """
        ctx = FlowContext(input=input, clock=clock if clock is not None else self.clock)
        enabled = self.trace_enabled if trace is None else trace
        hook = diagnostic_hook if diagnostic_hook is not None else self.trace_diagnostic_hook
        rec = TraceRecorder(self.contract_version, hook) if enabled else None
        primary = await self._primary_async(ctx, rec)
        outcome = await _finalize_async(self, ctx, primary, rec)
        if rec is not None:
            outcome = replace(outcome, trace=rec.build())
        return outcome

    async def _primary_async(self, ctx: FlowContext, rec: TraceRecorder | None) -> FlowOutcome:
        """Async primary outcome before finalization (SPEC 7.3.1, 11.7)."""
        try:
            return await _evaluate_async(self, ctx, rec)
        except asyncio.CancelledError as exc:
            if rec is not None:
                rec.emit("cancelled_observed", timestamp=ctx.clock.wall())
            return FlowOutcome(
                execution_status=ExecutionStatus.CANCELLED,
                interruption=InterruptionInfo(
                    kind="cancelled",
                    source="host",
                    timestamp=ctx.clock.wall(),
                ),
                primary_exception=exc,
            )
        except TimeoutError as exc:
            if rec is not None:
                rec.emit("timed_out_observed", timestamp=ctx.clock.wall())
            return FlowOutcome(
                execution_status=ExecutionStatus.TIMED_OUT,
                interruption=InterruptionInfo(
                    kind="timed_out",
                    source="external",
                    timestamp=ctx.clock.wall(),
                ),
                primary_exception=exc,
            )
        except Exception as exc:
            try:
                return await _route_exception_async(self, ctx, exc, rec)
            except Exception as route_exc:
                return FlowOutcome(
                    execution_status=ExecutionStatus.FAILED,
                    primary_exception=route_exc,
                )
        except BaseException as exc:
            return FlowOutcome(
                execution_status=ExecutionStatus.FAILED,
                primary_exception=exc,
            )

    def _primary(self, ctx: FlowContext, rec: TraceRecorder | None) -> FlowOutcome:
        """Compute the primary outcome before finalization (SPEC 7.3.1)."""
        try:
            return _evaluate(self, ctx, rec)
        except asyncio.CancelledError as exc:
            if rec is not None:
                rec.emit(
                    "cancelled_observed",
                    timestamp=ctx.clock.wall(),
                )
            # Cooperative cancellation: an interruption, not an exception.
            # It bypasses catch rules entirely (SPEC 11.6.1, 11.6.3).
            return FlowOutcome(
                execution_status=ExecutionStatus.CANCELLED,
                interruption=InterruptionInfo(
                    kind="cancelled",
                    source="host",
                    timestamp=ctx.clock.wall(),
                ),
                primary_exception=exc,
            )
        except TimeoutError as exc:
            # Externally-imposed timeout: an interruption, not an exception.
            # The library does not enforce timeouts; it recognizes them
            # (SPEC 11.6.2). Catch rules MUST NOT catch it (11.6.3).
            if rec is not None:
                rec.emit(
                    "timed_out_observed",
                    timestamp=ctx.clock.wall(),
                )
            return FlowOutcome(
                execution_status=ExecutionStatus.TIMED_OUT,
                interruption=InterruptionInfo(
                    kind="timed_out",
                    source="external",
                    timestamp=ctx.clock.wall(),
                ),
                primary_exception=exc,
            )
        except Exception as exc:
            try:
                return _route_exception(self, ctx, exc, rec)
            except Exception as route_exc:
                return FlowOutcome(
                    execution_status=ExecutionStatus.FAILED,
                    primary_exception=route_exc,
                )
        except BaseException as exc:
            # Non-Exception BaseExceptions (e.g. SystemExit, KeyboardInterrupt)
            # are ordinary failures, not interruptions (SPEC 11.6.3).
            return FlowOutcome(
                execution_status=ExecutionStatus.FAILED,
                primary_exception=exc,
            )


def _finalize(
    contract: FlowContract,
    ctx: FlowContext,
    outcome: FlowOutcome,
    rec: TraceRecorder | None,
) -> FlowOutcome:
    """Run finalizers and apply the finally failure policy (SPEC 11.8, 16.4).

    Finalizers run in LIFO order (innermost first), each isolated with a
    fresh cancellation token. Cleanup exceptions never trigger catch rules
    and never re-enter evaluation (FR3). is_clean is false iff any
    finalizer raised, was cancelled, or exceeded its budget.
    """
    if not contract.finalizers:
        return outcome

    cleanup_excs: list[BaseException] = []
    budget_exceeded = False
    for fin in reversed(contract.finalizers):
        fctx = FinallyContext(
            result=outcome,
            status=outcome.execution_status,
            value=outcome.value,
            exception=outcome.primary_exception,
            context=ctx.input,
            cancellation_token=FinallyCancellationToken(),
        )
        start = ctx.clock.monotonic()
        if rec is not None:
            rec.emit("finally_started", timestamp=ctx.clock.wall())
        try:
            fin_result = fin(fctx)
            _reject_awaitable(fin_result)
        except Exception as exc:
            cleanup_excs.append(exc)
            if rec is not None:
                rec.emit("finally_raised", timestamp=ctx.clock.wall())
        else:
            if rec is not None:
                rec.emit("finally_completed", timestamp=ctx.clock.wall())
        if contract.finally_timeout_ms is not None:
            elapsed_ms = (ctx.clock.monotonic() - start) * 1000.0
            if elapsed_ms > contract.finally_timeout_ms:
                budget_exceeded = True

    is_clean = not cleanup_excs and not budget_exceeded
    finfo = FinalizationInfo(
        is_clean=is_clean,
        cleanup_exceptions=tuple(cleanup_excs),
        cleanup_budget_exceeded=budget_exceeded,
    )
    result = replace(outcome, finalization=finfo)

    if not cleanup_excs:
        return result

    secondary = list(outcome.secondary_exceptions) + cleanup_excs
    if (
        contract.finally_policy is FinallyFailurePolicy.REPLACE_PRIMARY
        and outcome.execution_status is ExecutionStatus.FAILED
        and outcome.primary_exception is not None
    ):
        # ReplacePrimary on FAILED: cleanup exception becomes primary,
        # original primary moves to secondary (SPEC 16.4 matrix).
        secondary.append(outcome.primary_exception)
        return replace(
            result,
            primary_exception=cleanup_excs[0],
            secondary_exceptions=tuple(secondary),
        )
    # PreservePrimary and Attach: outcome unchanged; cleanup exceptions
    # recorded in secondary_exceptions (FR2). ReplacePrimary on
    # COMPLETED/CANCELLED/TIMED_OUT also lands here (B3-a).
    return replace(result, secondary_exceptions=tuple(secondary))


def _ordered_rules(contract: FlowContract) -> list[Rule]:
    if contract.mode is EvaluationMode.PRIORITY:
        # Stable sort: higher priority first, ties keep registration order.
        return sorted(contract.rules, key=lambda r: -r.priority)
    return list(contract.rules)


def _evaluate(contract: FlowContract, ctx: FlowContext, rec: TraceRecorder | None) -> FlowOutcome:
    """Evaluate the contract against the context (SPEC sections 7, 10)."""
    secondary: list[BaseException] = []
    effects: list[Effect] = []
    outcome = _run_rules(contract, ctx, secondary, effects, rec)
    if secondary:
        outcome = replace(outcome, secondary_exceptions=tuple(secondary))
    if effects:
        outcome = replace(outcome, effects=tuple(effects))
    return outcome


def _run_rules(
    contract: FlowContract,
    ctx: FlowContext,
    secondary: list[BaseException],
    effects: list[Effect],
    rec: TraceRecorder | None,
) -> FlowOutcome:
    """Core rule evaluation; hook failures append to secondary (SPEC 11.5)."""
    rules = _ordered_rules(contract)
    matched = False
    value: Any = None
    index = 0
    total = len(rules)

    while index < total:
        rule = rules[index]
        if contract.cancel_check is not None and contract.cancel_check():
            raise asyncio.CancelledError()
        if rule.kind == "then":
            # then-stage with no active match: skipped (SPEC 10.5).
            index += 1
            continue

        if not _is_effective(rule, ctx):
            if rec is not None:
                rec.emit(
                    "rule_skipped",
                    rule_id=str(rule.id),
                    timestamp=ctx.clock.wall(),
                    reason="not_effective",
                )
            index += 1
            continue

        holds, skip_reason = _condition_holds(rule, ctx, rec)
        if not holds:
            if rec is not None and skip_reason is not None:
                rec.emit(
                    "rule_skipped",
                    rule_id=str(rule.id),
                    timestamp=ctx.clock.wall(),
                    reason=skip_reason,
                )
            index += 1
            continue

        matched = True
        try:
            value = rule.action(ctx.input)
            _reject_awaitable(value)
        except Exception:
            if rec is not None:
                rec.emit(
                    "action_raised",
                    rule_id=str(rule.id),
                    timestamp=ctx.clock.wall(),
                )
            raise
        if rec is not None:
            rec.emit(
                "action_executed",
                rule_id=str(rule.id),
                timestamp=ctx.clock.wall(),
            )
        _propose_effects(rule, effects, rec, ctx)
        _fire_hooks(contract, ctx, str(rule.id), value, secondary, rec)

        # Run the then-chain immediately following this rule (SPEC 10.5).
        chain_index = index + 1
        while chain_index < total and rules[chain_index].kind == "then":
            stage = rules[chain_index]
            value = stage.action(ctx.input, value)
            _reject_awaitable(value)
            _propose_effects(stage, effects, rec, ctx)
            chain_index += 1

        if contract.mode is not EvaluationMode.ALL_MATCH:
            # FirstMatch/Priority: remaining rules skipped by short-circuit.
            if rec is not None:
                for skipped in rules[chain_index:]:
                    if skipped.kind == "then":
                        continue
                    rec.emit(
                        "skipped_by_short_circuit",
                        rule_id=str(skipped.id),
                        timestamp=ctx.clock.wall(),
                        reason="earlier_match",
                    )
            break
        index = chain_index

    if matched:
        return FlowOutcome(
            execution_status=ExecutionStatus.COMPLETED,
            decision_status=DecisionStatus.APPROVED,
            value=value,
        )

    # No rule matched: apply fallback if configured (SPEC 10.4, 3.2).
    if contract.fallback is not None:
        if contract.fallback.kind == "otherwise":
            assert contract.fallback.action is not None
            fb_value = contract.fallback.action(ctx.input)
            _reject_awaitable(fb_value)
            return FlowOutcome(
                execution_status=ExecutionStatus.COMPLETED,
                decision_status=DecisionStatus.NO_MATCH,
                value=fb_value,
            )
        return FlowOutcome(
            execution_status=ExecutionStatus.COMPLETED,
            decision_status=DecisionStatus.NO_MATCH,
            value=contract.fallback.value,
        )

    return FlowOutcome(
        execution_status=ExecutionStatus.COMPLETED,
        decision_status=DecisionStatus.NO_MATCH,
        value=None,
    )


def _propose_effects(
    rule: Rule,
    effects: list[Effect],
    rec: TraceRecorder | None,
    ctx: FlowContext,
) -> None:
    """Append a rule's proposed effects in deterministic order (SPEC 5, 6.4)."""
    for effect in rule.effects:
        effects.append(effect)
        if rec is not None:
            rec.emit(
                "effect_proposed",
                rule_id=str(rule.id),
                timestamp=ctx.clock.wall(),
            )


def _is_effective(rule: Rule, ctx: FlowContext) -> bool:
    """Check effective window against injected wall clock (SPEC 12.9).

    Inclusive of effective_from, exclusive of effective_until.
    """
    now = ctx.clock.wall()
    if rule.effective_from is not None and now < rule.effective_from:
        return False
    return not (rule.effective_until is not None and now >= rule.effective_until)


def _condition_holds(
    rule: Rule, ctx: FlowContext, rec: TraceRecorder | None
) -> tuple[bool, str | None]:
    """Evaluate condition + guard; emit trace events (SPEC 10.1-10.2, 12.1).

    Returns (holds, skip_reason) where skip_reason is a closed-enum reason
    for rule_skipped events, or None when the rule holds.
    """
    assert rule.condition is not None
    rid = str(rule.id)
    try:
        cond_raw = rule.condition(ctx.input)
        _reject_awaitable(cond_raw)
        result = bool(cond_raw)
    except Exception:
        if rec is not None:
            rec.emit(
                "condition_raised",
                rule_id=rid,
                timestamp=ctx.clock.wall(),
            )
        raise
    if rec is not None:
        rec.emit(
            "condition_evaluated",
            rule_id=rid,
            timestamp=ctx.clock.wall(),
        )
    if rule.kind == "when_not":
        result = not result
    if not result:
        return False, "condition_false"
    if rule.guard is not None:
        try:
            guard_raw = rule.guard(ctx.input)
            _reject_awaitable(guard_raw)
            guard_ok = bool(guard_raw)
        except Exception:
            raise
        if rec is not None:
            rec.emit(
                "guard_evaluated",
                rule_id=rid,
                timestamp=ctx.clock.wall(),
            )
        if not guard_ok:
            return False, "guard_blocked"
    return True, None


def _fire_hooks(
    contract: FlowContract,
    ctx: FlowContext,
    rule_id: str,
    value: Any,
    secondary: list[BaseException],
    rec: TraceRecorder | None,
) -> None:
    """Invoke on_match hooks; failures are isolated (SPEC 11.5)."""
    for hook in contract.hooks:
        if rec is not None:
            rec.emit("hook_invoked", rule_id=rule_id, timestamp=ctx.clock.wall())
        try:
            hook_result = hook(ctx.input, rule_id, value)
            _reject_awaitable(hook_result)
        except Exception as exc:
            secondary.append(exc)
            if rec is not None:
                rec.emit("hook_raised", rule_id=rule_id, timestamp=ctx.clock.wall())


def _route_exception(
    contract: FlowContract,
    ctx: FlowContext,
    exc: Exception,
    rec: TraceRecorder | None,
) -> FlowOutcome:
    """Route an exception through the catch chain (SPEC 11.1-11.4, 7.3.1).

    The first matching catch handles the exception. A handler that raises
    propagates the NEW exception through the remaining catches. rethrow
    stops evaluation and fails with the current exception. If no catch
    matches, the outcome is FAILED with the current exception as primary.
    """
    current: Exception = exc
    for index, catch in enumerate(contract.catches):
        if catch.kind == "rethrow":
            if rec is not None:
                rec.emit("rethrow_reached", timestamp=ctx.clock.wall())
            return FlowOutcome(
                execution_status=ExecutionStatus.FAILED,
                primary_exception=current,
            )
        if catch.kind == "any":
            type_matched = True
        else:
            assert catch.exc_type is not None
            type_matched = isinstance(current, catch.exc_type)
        if not type_matched:
            continue
        if rec is not None and catch.kind != "any":
            rec.emit("catch_matched", timestamp=ctx.clock.wall())
        if catch.kind == "when" and catch.predicate is not None:
            if rec is not None:
                rec.emit("catch_predicate_evaluated", timestamp=ctx.clock.wall())
            try:
                pred_raw = catch.predicate(ctx.input, current)
                _reject_awaitable(pred_raw)
                pred_ok = bool(pred_raw)
            except Exception as pred_exc:
                if rec is not None:
                    rec.emit("catch_predicate_raised", timestamp=ctx.clock.wall())
                # A failing predicate is an explicit failure: the predicate
                # exception becomes the new primary candidate (SPEC 11.2).
                current = pred_exc
                continue
            if not pred_ok:
                if rec is not None:
                    rec.emit("catch_declined", timestamp=ctx.clock.wall())
                continue
        assert catch.handler is not None
        try:
            value = catch.handler(ctx.input, current)
            _reject_awaitable(value)
        except Exception as new_exc:
            # Handler failure propagates the new exception through the
            # remaining catches (SPEC 11.1, 11.2, 11.3).
            current = new_exc
            continue
        if rec is not None:
            rec.emit("catch_handled", timestamp=ctx.clock.wall())
        handler_id = catch.id if catch.id is not None else f"catch[{index}]"
        return FlowOutcome(
            execution_status=ExecutionStatus.COMPLETED,
            value=value,
            recovery=RecoveryInfo(
                original_exception=current,
                handler_rule_id=handler_id,
                recovered_at=ctx.clock.wall(),
            ),
        )
    return FlowOutcome(
        execution_status=ExecutionStatus.FAILED,
        primary_exception=current,
    )


# -- async execution parity (SPEC 11.7) ---------------------------------------


def _is_async_callable(fn: Callable[..., Any]) -> bool:
    """Detect async callables including partials and async __call__."""
    if inspect.iscoroutinefunction(fn):
        return True
    try:
        return inspect.iscoroutinefunction(type(fn).__call__)
    except AttributeError:
        return False


def _compute_async_only(
    *,
    rules: list[Rule],
    catches: list[CatchRule],
    hooks: list[Callable[[Any, str, Any], None]],
    finalizers: list[Callable[[FinallyContext], Any]],
) -> bool:
    """Classify the contract as async-only (SPEC 11.7, FR8)."""
    for rule in rules:
        for fn in (rule.condition, rule.guard, rule.action):
            if fn is not None and _is_async_callable(fn):
                return True
    for catch in catches:
        for fn in (catch.handler, catch.predicate):
            if fn is not None and _is_async_callable(fn):
                return True
    for hook in hooks:
        if _is_async_callable(hook):
            return True
    return any(_is_async_callable(fin) for fin in finalizers)


def _reject_awaitable(result: Any) -> None:
    """Sync path must never silently skip awaiting (SPEC 11.7)."""
    if inspect.isawaitable(result):
        raise AsyncOnlyContractError(
            "a user callback returned an awaitable on the sync path; "
            "use execute_async() (SPEC 11.7)"
        )


async def _resolve(value: Any) -> Any:
    """Await the value if it is awaitable, else return it (SPEC 11.7)."""
    if inspect.isawaitable(value):
        return await value
    return value


async def _evaluate_async(
    contract: FlowContract, ctx: FlowContext, rec: TraceRecorder | None
) -> FlowOutcome:
    """Async rule evaluation; hook failures append to secondary."""
    secondary: list[BaseException] = []
    effects: list[Effect] = []
    outcome = await _run_rules_async(contract, ctx, secondary, effects, rec)
    if secondary:
        outcome = replace(outcome, secondary_exceptions=tuple(secondary))
    if effects:
        outcome = replace(outcome, effects=tuple(effects))
    return outcome


async def _run_rules_async(
    contract: FlowContract,
    ctx: FlowContext,
    secondary: list[BaseException],
    effects: list[Effect],
    rec: TraceRecorder | None,
) -> FlowOutcome:
    """Async core rule evaluation (SPEC 10, 11.7)."""
    rules = _ordered_rules(contract)
    matched = False
    value: Any = None
    index = 0
    total = len(rules)

    while index < total:
        rule = rules[index]
        if contract.cancel_check is not None and contract.cancel_check():
            raise asyncio.CancelledError()
        if rule.kind == "then":
            index += 1
            continue

        if not _is_effective(rule, ctx):
            if rec is not None:
                rec.emit(
                    "rule_skipped",
                    rule_id=str(rule.id),
                    timestamp=ctx.clock.wall(),
                    reason="not_effective",
                )
            index += 1
            continue

        holds, skip_reason = await _condition_holds_async(rule, ctx, rec)
        if not holds:
            if rec is not None and skip_reason is not None:
                rec.emit(
                    "rule_skipped",
                    rule_id=str(rule.id),
                    timestamp=ctx.clock.wall(),
                    reason=skip_reason,
                )
            index += 1
            continue

        matched = True
        try:
            value = await _resolve(rule.action(ctx.input))
        except Exception:
            if rec is not None:
                rec.emit(
                    "action_raised",
                    rule_id=str(rule.id),
                    timestamp=ctx.clock.wall(),
                )
            raise
        if rec is not None:
            rec.emit(
                "action_executed",
                rule_id=str(rule.id),
                timestamp=ctx.clock.wall(),
            )
        _propose_effects(rule, effects, rec, ctx)
        await _fire_hooks_async(contract, ctx, str(rule.id), value, secondary, rec)

        chain_index = index + 1
        while chain_index < total and rules[chain_index].kind == "then":
            stage = rules[chain_index]
            value = await _resolve(stage.action(ctx.input, value))
            _propose_effects(stage, effects, rec, ctx)
            chain_index += 1

        if contract.mode is not EvaluationMode.ALL_MATCH:
            if rec is not None:
                for skipped in rules[chain_index:]:
                    if skipped.kind == "then":
                        continue
                    rec.emit(
                        "skipped_by_short_circuit",
                        rule_id=str(skipped.id),
                        timestamp=ctx.clock.wall(),
                        reason="earlier_match",
                    )
            break
        index = chain_index

    if matched:
        return FlowOutcome(
            execution_status=ExecutionStatus.COMPLETED,
            decision_status=DecisionStatus.APPROVED,
            value=value,
        )

    if contract.fallback is not None:
        if contract.fallback.kind == "otherwise":
            assert contract.fallback.action is not None
            return FlowOutcome(
                execution_status=ExecutionStatus.COMPLETED,
                decision_status=DecisionStatus.NO_MATCH,
                value=await _resolve(contract.fallback.action(ctx.input)),
            )
        return FlowOutcome(
            execution_status=ExecutionStatus.COMPLETED,
            decision_status=DecisionStatus.NO_MATCH,
            value=contract.fallback.value,
        )

    return FlowOutcome(
        execution_status=ExecutionStatus.COMPLETED,
        decision_status=DecisionStatus.NO_MATCH,
        value=None,
    )


async def _condition_holds_async(
    rule: Rule, ctx: FlowContext, rec: TraceRecorder | None
) -> tuple[bool, str | None]:
    """Async condition + guard evaluation (SPEC 10.1-10.2, 11.7)."""
    assert rule.condition is not None
    rid = str(rule.id)
    try:
        result = bool(await _resolve(rule.condition(ctx.input)))
    except Exception:
        if rec is not None:
            rec.emit(
                "condition_raised",
                rule_id=rid,
                timestamp=ctx.clock.wall(),
            )
        raise
    if rec is not None:
        rec.emit(
            "condition_evaluated",
            rule_id=rid,
            timestamp=ctx.clock.wall(),
        )
    if rule.kind == "when_not":
        result = not result
    if not result:
        return False, "condition_false"
    if rule.guard is not None:
        try:
            guard_ok = bool(await _resolve(rule.guard(ctx.input)))
        except Exception:
            raise
        if rec is not None:
            rec.emit(
                "guard_evaluated",
                rule_id=rid,
                timestamp=ctx.clock.wall(),
            )
        if not guard_ok:
            return False, "guard_blocked"
    return True, None


async def _fire_hooks_async(
    contract: FlowContract,
    ctx: FlowContext,
    rule_id: str,
    value: Any,
    secondary: list[BaseException],
    rec: TraceRecorder | None,
) -> None:
    """Async on_match hooks; failures isolated (SPEC 11.5, 11.7)."""
    for hook in contract.hooks:
        if rec is not None:
            rec.emit("hook_invoked", rule_id=rule_id, timestamp=ctx.clock.wall())
        try:
            await _resolve(hook(ctx.input, rule_id, value))
        except Exception as exc:
            secondary.append(exc)
            if rec is not None:
                rec.emit("hook_raised", rule_id=rule_id, timestamp=ctx.clock.wall())


async def _route_exception_async(
    contract: FlowContract,
    ctx: FlowContext,
    exc: Exception,
    rec: TraceRecorder | None,
) -> FlowOutcome:
    """Async catch-chain routing (SPEC 11.1-11.4, 11.7)."""
    current: Exception = exc
    for index, catch in enumerate(contract.catches):
        if catch.kind == "rethrow":
            if rec is not None:
                rec.emit("rethrow_reached", timestamp=ctx.clock.wall())
            return FlowOutcome(
                execution_status=ExecutionStatus.FAILED,
                primary_exception=current,
            )
        if catch.kind == "any":
            type_matched = True
        else:
            assert catch.exc_type is not None
            type_matched = isinstance(current, catch.exc_type)
        if not type_matched:
            continue
        if rec is not None and catch.kind != "any":
            rec.emit("catch_matched", timestamp=ctx.clock.wall())
        if catch.kind == "when" and catch.predicate is not None:
            if rec is not None:
                rec.emit("catch_predicate_evaluated", timestamp=ctx.clock.wall())
            try:
                pred_ok = bool(await _resolve(catch.predicate(ctx.input, current)))
            except Exception as pred_exc:
                if rec is not None:
                    rec.emit("catch_predicate_raised", timestamp=ctx.clock.wall())
                current = pred_exc
                continue
            if not pred_ok:
                if rec is not None:
                    rec.emit("catch_declined", timestamp=ctx.clock.wall())
                continue
        assert catch.handler is not None
        try:
            value = await _resolve(catch.handler(ctx.input, current))
        except Exception as new_exc:
            current = new_exc
            continue
        if rec is not None:
            rec.emit("catch_handled", timestamp=ctx.clock.wall())
        handler_id = catch.id if catch.id is not None else f"catch[{index}]"
        return FlowOutcome(
            execution_status=ExecutionStatus.COMPLETED,
            value=value,
            recovery=RecoveryInfo(
                original_exception=current,
                handler_rule_id=handler_id,
                recovered_at=ctx.clock.wall(),
            ),
        )
    return FlowOutcome(
        execution_status=ExecutionStatus.FAILED,
        primary_exception=current,
    )


async def _finalize_async(
    contract: FlowContract,
    ctx: FlowContext,
    outcome: FlowOutcome,
    rec: TraceRecorder | None,
) -> FlowOutcome:
    """Async finalization with the same failure policy (SPEC 11.8, 16.4)."""
    if not contract.finalizers:
        return outcome

    cleanup_excs: list[BaseException] = []
    budget_exceeded = False
    for fin in reversed(contract.finalizers):
        fctx = FinallyContext(
            result=outcome,
            status=outcome.execution_status,
            value=outcome.value,
            exception=outcome.primary_exception,
            context=ctx.input,
            cancellation_token=FinallyCancellationToken(),
        )
        start = ctx.clock.monotonic()
        if rec is not None:
            rec.emit("finally_started", timestamp=ctx.clock.wall())
        try:
            call = fin(fctx)
            if contract.finally_timeout_ms is not None and inspect.isawaitable(call):
                await asyncio.wait_for(_resolve(call), timeout=contract.finally_timeout_ms / 1000.0)
            else:
                await _resolve(call)
        except Exception as exc:
            cleanup_excs.append(exc)
            if rec is not None:
                rec.emit("finally_raised", timestamp=ctx.clock.wall())
        else:
            if rec is not None:
                rec.emit("finally_completed", timestamp=ctx.clock.wall())
        if contract.finally_timeout_ms is not None:
            elapsed_ms = (ctx.clock.monotonic() - start) * 1000.0
            if elapsed_ms > contract.finally_timeout_ms:
                budget_exceeded = True

    is_clean = not cleanup_excs and not budget_exceeded
    finfo = FinalizationInfo(
        is_clean=is_clean,
        cleanup_exceptions=tuple(cleanup_excs),
        cleanup_budget_exceeded=budget_exceeded,
    )
    result = replace(outcome, finalization=finfo)

    if not cleanup_excs:
        return result

    secondary = list(outcome.secondary_exceptions) + cleanup_excs
    if (
        contract.finally_policy is FinallyFailurePolicy.REPLACE_PRIMARY
        and outcome.execution_status is ExecutionStatus.FAILED
        and outcome.primary_exception is not None
    ):
        secondary.append(outcome.primary_exception)
        return replace(
            result,
            primary_exception=cleanup_excs[0],
            secondary_exceptions=tuple(secondary),
        )
    return replace(result, secondary_exceptions=tuple(secondary))


@dataclass(frozen=True)
class ValidationIssue:
    """A static-analysis finding (SPEC 12.8).

    severity "error" blocks compilation; "warning" should be investigated
    but does not block.
    """

    severity: str  # "error" | "warning"
    code: str
    message: str
    rule_id: str | None = None


def _epoch_ms(dt: datetime.datetime | None) -> int | None:
    """Canonical epoch-milliseconds representation of a datetime.

    Naive datetimes are interpreted as UTC so the value is identical
    across hosts with different local timezones (SPEC 12.9, v2).
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return int(dt.timestamp() * 1000)


def _compute_contract_version(
    *,
    rules: list[Rule],
    fallback: Fallback | None,
    mode: EvaluationMode,
    catches: list[CatchRule],
    finalizers: list[Callable[[FinallyContext], Any]],
    finally_policy: FinallyFailurePolicy,
    finally_timeout_ms: int | None,
    trace_enabled: bool,
    portable_rules: list[PortableRule] | None = None,
) -> str:
    """Structural contract version: SHA-256 of canonical content (SPEC 12.9).

    Algorithm v2: JSON-canonical serialization of rule ids/kinds/
    priorities, effective dates as epoch milliseconds, portable rule
    bodies (condition/guard/transform expressions and effects),
    fallback kind, mode, catch kinds, finalizer count, policy, timeout,
    and trace flag; SHA-256 hex digest truncated to 32 chars. Native
    (callable) rule bodies are not serializable and are marked
    ``native: true``; their metadata still participates in the hash.
    """
    prs = portable_rules or []
    rule_entries = []
    for i, r in enumerate(rules):
        pr = prs[i] if i < len(prs) else None
        entry: dict[str, Any] = {
            "id": str(r.id),
            "kind": r.kind,
            "priority": r.priority,
            "effective_from": _epoch_ms(r.effective_from),
            "effective_until": _epoch_ms(r.effective_until),
            "native": pr is None,
            "condition": (
                expr_to_dict(pr.condition)
                if pr is not None and pr.condition is not None
                else None
            ),
            "guard": (
                expr_to_dict(pr.guard)
                if pr is not None and pr.guard is not None
                else None
            ),
            "transform": (
                expr_to_dict(pr.transform)
                if pr is not None and pr.transform is not None
                else None
            ),
            "effects": [
                {"name": e.name, "payload": e.payload} for e in r.effects
            ],
        }
        rule_entries.append(entry)
    payload = {
        "algorithm": "flowsemantics-contract-v2",
        "rules": rule_entries,
        "fallback": None if fallback is None else fallback.kind,
        "mode": str(mode),
        "catches": [c.kind for c in catches],
        "finalizer_count": len(finalizers),
        "finally_policy": str(finally_policy),
        "finally_timeout_ms": finally_timeout_ms,
        "trace_enabled": trace_enabled,
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def _explain_event(event: Any) -> str:
    """Render one trace event as a line (SPEC 12.4)."""
    rid = event.rule_id if event.rule_id is not None else "-"
    reason = f" ({event.reason})" if event.reason else ""
    return f"  [{event.type}] rule={rid}{reason}"


__all__: list[str] = [
    "EvaluationMode",
    "Fallback",
    "Flow",
    "FlowContract",
    "FlowPortability",
    "ValidationIssue",
]
