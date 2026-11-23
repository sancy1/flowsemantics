"""Unit tests for injected clocks (SPEC.md section 6.2-6.3)."""

from __future__ import annotations

import datetime

from flowsemantics import FakeClock, SystemClock


def test_fake_clock_defaults_to_epoch() -> None:
    clock = FakeClock()
    assert clock.wall() == datetime.datetime(1970, 1, 1, tzinfo=datetime.UTC)
    assert clock.monotonic() == 0.0


def test_fake_clock_advance_moves_both() -> None:
    clock = FakeClock()
    clock.advance(5.0)
    assert clock.monotonic() == 5.0
    assert clock.wall() == datetime.datetime(1970, 1, 1, 0, 0, 5, tzinfo=datetime.UTC)


def test_fake_clock_advance_wall_only() -> None:
    clock = FakeClock()
    clock.advance_wall(10.0)
    assert clock.monotonic() == 0.0
    assert clock.wall().second == 10


def test_fake_clock_set_wall() -> None:
    clock = FakeClock()
    target = datetime.datetime(2026, 6, 1, 12, 0, 0, tzinfo=datetime.UTC)
    clock.set_wall(target)
    assert clock.wall() == target


def test_fake_clock_deterministic() -> None:
    a = FakeClock()
    b = FakeClock()
    a.advance(3.0)
    b.advance(3.0)
    assert a.wall() == b.wall()
    assert a.monotonic() == b.monotonic()


def test_system_clock_returns_aware_wall_and_float_monotonic() -> None:
    clock = SystemClock()
    wall = clock.wall()
    assert wall.tzinfo is not None
    assert isinstance(clock.monotonic(), float)
