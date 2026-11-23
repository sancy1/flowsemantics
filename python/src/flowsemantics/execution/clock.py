"""flowsemantics.execution.clock - Injected wall and monotonic clocks.

Layer:      Domain
Module:     flowsemantics.execution.clock
Since:      0.1.0
Implements: SPEC.md section 6.2 (injected clocks), section 6.3 (default clock)
Depends on: stdlib only (datetime, time)
Used by:    FlowContext, FlowOutcome timestamps, finalization budgets
See also:   SPEC.md section 6

Notes:
  - Every time read in Core routes through a Clock. Ambient clock APIs are
    banned in Core by audit.py; SystemClock is the single sanctioned reader,
    permitted by SPEC.md section 6.3 and clearly replaceable via with_clock.
  - SystemClock reads the host clocks through the datetime and time modules.
    It is the documented default; deterministic replay requires FakeClock.
"""

from __future__ import annotations

import datetime
import time
from typing import Protocol

_EPOCH = datetime.datetime(1970, 1, 1, tzinfo=datetime.UTC)


class Clock(Protocol):
    """Two-concept clock: wall time for timestamps, monotonic for durations.

    SPEC.md section 6.2 makes the wall/monotonic distinction normative.
    """

    def wall(self) -> datetime.datetime:
        """Return the current wall-clock time as a timezone-aware datetime."""
        ...

    def monotonic(self) -> float:
        """Return the current monotonic time in seconds."""
        ...


class SystemClock:
    """Default clock reading the host's real clocks (SPEC.md section 6.3).

    This is the only Core component permitted to read ambient time. It is
    replaceable: pass any Clock implementation via Flow.with_clock() or the
    execute() clock parameter. Deterministic replay and tests MUST use
    FakeClock instead.
    """

    def wall(self) -> datetime.datetime:
        """Return the host wall-clock time in UTC."""
        return datetime.datetime.now(datetime.UTC)

    def monotonic(self) -> float:
        """Return the host monotonic clock in seconds."""
        return time.monotonic()


class FakeClock:
    """Deterministic clock for tests, replay, and conformance vectors.

    Wall and monotonic values advance only when advance() or advance_wall()
    is called. Two FakeClocks constructed with the same values behave
    identically, which is what SPEC.md section 6.1 determinism requires.
    """

    def __init__(
        self,
        wall: datetime.datetime | None = None,
        monotonic: float = 0.0,
    ) -> None:
        """Create a FakeClock at the given wall time and monotonic offset."""
        self._wall = wall if wall is not None else _EPOCH
        self._monotonic = monotonic

    def wall(self) -> datetime.datetime:
        """Return the current fake wall-clock time."""
        return self._wall

    def monotonic(self) -> float:
        """Return the current fake monotonic time in seconds."""
        return self._monotonic

    def advance(self, seconds: float) -> None:
        """Advance both wall and monotonic time by the same duration."""
        self._wall += datetime.timedelta(seconds=seconds)
        self._monotonic += seconds

    def advance_wall(self, seconds: float) -> None:
        """Advance only the wall clock (monotonic time is unaffected)."""
        self._wall += datetime.timedelta(seconds=seconds)

    def set_wall(self, value: datetime.datetime) -> None:
        """Set the wall clock to an absolute value."""
        self._wall = value


__all__: list[str] = [
    "Clock",
    "FakeClock",
    "SystemClock",
]
