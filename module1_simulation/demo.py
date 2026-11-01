"""Development-only call inputs and movement checks; replace when Module 4 connects."""

import tomllib
from pathlib import Path
from random import Random

from .city import fields, number, tick_at
from .simulation import Simulation


def load_call_settings(path: str | Path) -> dict:
    with Path(path).open("rb") as source:
        settings = tomllib.load(source)
    fields(settings, {"interval_seconds", "seed"}, "development call settings")
    number(settings["interval_seconds"], "interval_seconds", positive=True)
    if type(settings["seed"]) is not int:
        raise ValueError("seed: expected an integer")
    return settings


class DemoRunner:
    def __init__(self, simulation: Simulation, *, call_interval_seconds=None,
                 seed=42, auto_assign=False) -> None:
        self.simulation = simulation
        self._auto_assign = auto_assign
        if type(seed) is not int:
            raise ValueError("seed: expected an integer")
        self._seed = seed
        self._rng = Random(seed)
        self._interval_ticks = None
        if call_interval_seconds is not None:
            number(call_interval_seconds, "call_interval_seconds", positive=True)
            self._interval_ticks = tick_at(call_interval_seconds, simulation.config.tick_seconds,
                                           "call_interval_seconds")
            if self._interval_ticks < 1:
                raise ValueError("call interval must be at least one tick")
            if simulation.has_initial_calls:
                raise ValueError("continuous calls cannot be combined with a recorded scenario")
        if simulation.tick != 0:
            raise ValueError("DemoRunner must start at tick 0")
        self._created = 0
        if self._interval_ticks is not None:
            self._emit_call()
        self._assign_waiting()

    @property
    def auto_assign(self) -> bool:
        return self._auto_assign

    def _assign_waiting(self) -> None:
        if not self._auto_assign:
            return
        # Only current, released observations participate in this temporary demo rule.
        waiting = sorted((p for p in self.simulation.passenger_snapshots() if p.state == "waiting"),
                         key=lambda p: (p.requested_at_seconds, p.call_id))
        size = self.simulation.config.block_size_m
        for passenger in waiting:
            available = [t for t in self.simulation.snapshot() if t.state == "idle"]
            if not available:
                break
            x, y = (n * size for n in passenger.origin)
            closest = min(available, key=lambda t: (abs(t.x_m - x) + abs(t.y_m - y), t.taxi_id))
            self.simulation.dispatch(closest.taxi_id, passenger.call_id)

    def _emit_call(self) -> None:
        intersections = [(x, y) for x in range(4) for y in range(4)]
        origin, destination = self._rng.sample(intersections, 2)
        next_id = self._created + 1
        self.simulation.add_calls([dict(
            call_id=f"call-{next_id}", requested_at_seconds=self.simulation.time_seconds,
            origin=list(origin), destination=list(destination))])
        self._created = next_id

    def advance(self, ticks: int = 1) -> None:
        if type(ticks) is not int or ticks < 0:
            raise ValueError("ticks: expected a non-negative integer")
        for _ in range(ticks):
            self.simulation.advance()
            if self._interval_ticks is not None and self.simulation.tick % self._interval_ticks == 0:
                self._emit_call()
            self._assign_waiting()

    def reset(self) -> None:
        self.simulation.reset()
        self._rng.seed(self._seed)
        self._created = 0
        if self._interval_ticks is not None:
            self._emit_call()
        self._assign_waiting()
