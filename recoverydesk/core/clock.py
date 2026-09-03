"""ClockPort — WallClock for SBX/PRD, SimClock for the SIM zone (D-024).

PHASE_4 §15: environment = config, not a branch. The SimClock fast-forwards
(sim_time_scale: 1 real second = `scale` sim seconds) so a 14-day case horizon
plays out in minutes for demos/batch runs. All orchestrator/gateway/scheduler
code takes a Clock; nothing reads wall time directly.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...
    def real_until(self, dt: datetime) -> float: ...


class WallClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def real_until(self, dt: datetime) -> float:
        return max(0.0, dt.timestamp() - self.now().timestamp())


class SimClock:
    """Virtual clock: sim_now = start + (real_elapsed × scale)."""

    def __init__(self, start: datetime, scale: float = 60.0):
        self._start = start
        self._scale = scale
        self._t0 = time.monotonic()

    @property
    def scale(self) -> float:
        return self._scale

    def now(self) -> datetime:
        elapsed_sim = (time.monotonic() - self._t0) * self._scale
        ts = self._start.timestamp() + elapsed_sim
        return datetime.fromtimestamp(ts, tz=timezone.utc)

    def real_until(self, sim_dt: datetime) -> float:
        """Real seconds until sim time `sim_dt` (for due_at scheduling)."""
        sim_delta = sim_dt.timestamp() - self.now().timestamp()
        return max(0.0, sim_delta / self._scale)


class SteppyClock:
    """Manually-advanced clock for tests and replay (deterministic windows)."""

    def __init__(self, start):
        self._t = start

    def now(self):
        return self._t

    def real_until(self, dt) -> float:
        return max(0.0, dt.timestamp() - self._t.timestamp())

    def advance(self, hours: float) -> None:
        from datetime import timedelta

        self._t = self._t + timedelta(hours=hours)
