"""Unit tests for effective dates, replay, and shadow (SPEC 12.6-12.9)."""

from __future__ import annotations

import datetime
from typing import Any

import pytest

from flowsemantics import (
    FakeClock,
    Flow,
    ReplayError,
    ReplayMode,
    StructureError,
    record,
    replay,
    shadow,
    sign,
)


def _true(_input: Any) -> bool:
    return True


def _const(value: Any) -> Any:
    return lambda _input: value


UTC = datetime.UTC


# -- effective dates (12.9) ---------------------------------------------------------


def test_effective_from_future_skips_rule() -> None:
    clock = FakeClock()
    future = clock.wall() + datetime.timedelta(days=1)
    contract = (
        Flow()
        .with_clock(clock)
        .with_trace()
        .when(
            _true,
            then=_const("promo"),
            id="promo",
            effective_from=future,
        )
        .compile()
    )
    outcome = contract.try_execute(None)
    assert outcome.value is None
    assert outcome.trace is not None
    skipped = [e for e in outcome.trace.events if e.type == "rule_skipped"]
    assert skipped[0].reason == "not_effective"


def test_effective_until_past_skips_rule() -> None:
    clock = FakeClock()
    past = clock.wall() - datetime.timedelta(days=1)
    contract = (
        Flow()
        .with_clock(clock)
        .when(
            _true,
            then=_const("old"),
            id="old",
            effective_until=past,
        )
        .compile()
    )
    assert contract.try_execute(None).value is None


def test_effective_window_inclusive_from_exclusive_until() -> None:
    clock = FakeClock()
    start = clock.wall()
    end = clock.wall() + datetime.timedelta(hours=1)
    contract = (
        Flow()
        .with_clock(clock)
        .when(
            _true,
            then=_const("active"),
            id="r1",
            effective_from=start,
            effective_until=end,
        )
        .compile()
    )
    assert contract.try_execute(None).value == "active"


def test_effective_until_boundary_exclusive() -> None:
    clock = FakeClock()
    end = clock.wall()
    contract = (
        Flow()
        .with_clock(clock)
        .when(
            _true,
            then=_const("x"),
            id="r1",
            effective_until=end,
        )
        .compile()
    )
    assert contract.try_execute(None).value is None


def test_effective_ordering_validation() -> None:
    now = datetime.datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(StructureError):
        (
            Flow()
            .when(
                _true,
                then=_const(1),
                id="r1",
                effective_from=now,
                effective_until=now - datetime.timedelta(days=1),
            )
            .compile()
        )


def test_effective_dates_in_contract_version() -> None:
    now = datetime.datetime(2026, 1, 1, tzinfo=UTC)
    c1 = Flow().when(_true, then=_const(1), id="r1").compile()
    c2 = Flow().when(_true, then=_const(1), id="r1", effective_from=now).compile()
    assert c1.contract_version != c2.contract_version


# -- replay (12.6) ---------------------------------------------------------------------


def _sample_contract() -> Any:
    return (
        Flow()
        .when(lambda o: o["total"] > 100, then=lambda o: "big", id="big")
        .when_not(lambda o: o["total"] > 100, then=lambda o: "small", id="small")
        .compile()
    )


def test_record_captures_outcome_and_trace() -> None:
    contract = _sample_contract()
    rec = record(contract, {"total": 250})
    assert rec.spec_version == "0.1.0"
    assert rec.contract_version == contract.contract_version
    assert rec.outcome.value == "big"
    assert rec.trace is not None


def test_replay_simulation_equivalent() -> None:
    contract = _sample_contract()
    rec = record(contract, {"total": 50})
    result = replay(rec, contract, mode=ReplayMode.SIMULATION)
    assert result.equivalent is True
    assert result.outcome is not None
    assert result.outcome.value == "small"


def test_replay_decision_mode() -> None:
    contract = _sample_contract()
    rec = record(contract, {"total": 250})
    result = replay(rec, contract, mode=ReplayMode.DECISION)
    assert result.equivalent is True


def test_replay_historical_returns_recorded() -> None:
    contract = _sample_contract()
    rec = record(contract, {"total": 250})
    result = replay(rec, contract, mode=ReplayMode.HISTORICAL)
    assert result.outcome is rec.outcome
    assert result.equivalent is None


def test_replay_fails_closed_on_spec_mismatch() -> None:
    contract = _sample_contract()
    rec = record(contract, {"total": 1})
    bad = type(rec)(
        spec_version="9.9.9",
        contract_version=rec.contract_version,
        input=rec.input,
        clock_wall=rec.clock_wall,
        clock_monotonic=rec.clock_monotonic,
        outcome=rec.outcome,
    )
    with pytest.raises(ReplayError):
        replay(bad, contract)


def test_replay_fails_closed_on_contract_mismatch() -> None:
    contract = _sample_contract()
    rec = record(contract, {"total": 1})
    other = Flow().when(_true, then=_const("x"), id="other").compile()
    with pytest.raises(ReplayError):
        replay(rec, other)


def test_replay_integrity_hmac() -> None:
    contract = _sample_contract()
    rec = record(contract, {"total": 1})
    key = b"test-key-123"
    signed_rec = sign(rec, key)
    result = replay(signed_rec, contract, integrity_key=key)
    assert result.equivalent is True


def test_replay_integrity_requires_key() -> None:
    contract = _sample_contract()
    rec = record(contract, {"total": 1})
    signed_rec = sign(rec, b"key")
    with pytest.raises(ReplayError):
        replay(signed_rec, contract)


def test_replay_integrity_detects_tampering() -> None:
    contract = _sample_contract()
    rec = record(contract, {"total": 1})
    signed_rec = sign(rec, b"key")
    tampered = type(signed_rec)(
        spec_version=signed_rec.spec_version,
        contract_version=signed_rec.contract_version,
        input={"total": 999},  # tampered input
        clock_wall=signed_rec.clock_wall,
        clock_monotonic=signed_rec.clock_monotonic,
        outcome=signed_rec.outcome,
        integrity=signed_rec.integrity,
    )
    with pytest.raises(ReplayError):
        replay(tampered, contract, integrity_key=b"key")


def test_replay_effects_requires_authorization() -> None:
    contract = _sample_contract()
    rec = record(contract, {"total": 1})
    with pytest.raises(ReplayError):
        replay(rec, contract, mode=ReplayMode.EFFECTS)


def test_replay_effects_applies_with_authorization() -> None:
    contract = _sample_contract()
    rec = record(contract, {"total": 1})
    applied: list[Any] = []
    result = replay(
        rec,
        contract,
        mode=ReplayMode.EFFECTS,
        effect_executor=applied.append,
        authorize_effects=True,
    )
    assert result.effects_applied == len(rec.effects)


def test_replay_uses_recorded_clock() -> None:
    clock = FakeClock()
    contract = Flow().with_clock(clock).when(_true, then=_const("v"), id="r1").compile()
    rec = record(contract, None)
    clock.advance(100.0)  # move clock far forward after recording
    result = replay(rec, contract, mode=ReplayMode.SIMULATION)
    assert result.equivalent is True


# -- shadow (12.7) -----------------------------------------------------------------------


def test_shadow_identical_flows_no_differences() -> None:
    def build() -> Any:
        return Flow().when(lambda o: o > 0, then=lambda o: "pos", id="p").compile()

    report = shadow(build(), build(), [1, -1, 0])
    assert report.total == 3
    assert report.differences == 0


def test_shadow_detects_difference() -> None:
    current = Flow().when(lambda o: o > 0, then=lambda o: "pos", id="p").compile()
    candidate = Flow().when(lambda o: o > 10, then=lambda o: "big", id="b").compile()
    report = shadow(current, candidate, [5, 50])
    assert report.differences == 2
    assert report.entries[0].differing_fields


def test_shadow_deterministic() -> None:
    current = Flow().when(_true, then=_const("a"), id="a").compile()
    candidate = Flow().when(_true, then=_const("b"), id="b").compile()
    r1 = shadow(current, candidate, [1, 2, 3])
    r2 = shadow(current, candidate, [1, 2, 3])
    assert r1 == r2


def test_shadow_never_applies_effects() -> None:
    # simulate() suppresses hooks/finalizers; shadow uses simulate.
    ran: list[str] = []
    current = (
        Flow()
        .when(_true, then=_const("x"), id="r1")
        .finally_(lambda _c: ran.append("fin"))
        .compile()
    )
    candidate = Flow().when(_true, then=_const("x"), id="r1").compile()
    shadow(current, candidate, [None])
    assert ran == []
