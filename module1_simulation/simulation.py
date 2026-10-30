"""Deterministic movement prototype; no rendering or cross-module contracts."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import tomllib


def _positive(value: object, name: str) -> None:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value <= 0):
        raise ValueError(f"{name}: expected a finite positive number, got {value!r}")


@dataclass(frozen=True)
class TaxiPlan:
    taxi_id: str
    speed_mps: float
    route: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class DemoConfig:
    blocks: int
    block_size_m: float
    tick_seconds: float
    taxis: tuple[TaxiPlan, ...]

    def __post_init__(self) -> None:
        if type(self.blocks) is not int or self.blocks != 3:
            raise ValueError("blocks: this prototype requires 3 × 3 blocks")
        _positive(self.block_size_m, "block_size_m")
        _positive(self.tick_seconds, "tick_seconds")
        if len(self.taxis) != 3:
            raise ValueError("taxis: this prototype requires exactly 3 taxis")
        ids = set()
        for taxi in self.taxis:
            if not isinstance(taxi.taxi_id, str) or not taxi.taxi_id.strip():
                raise ValueError("taxi_id: expected a non-empty string")
            if taxi.taxi_id in ids:
                raise ValueError(f"duplicate taxi_id: {taxi.taxi_id}")
            ids.add(taxi.taxi_id)
            _positive(taxi.speed_mps, f"{taxi.taxi_id}.speed_mps")
            if len(taxi.route) < 2:
                raise ValueError(f"{taxi.taxi_id}: route requires at least 2 nodes")
            for node in taxi.route:
                if (len(node) != 2 or any(type(n) is not int or not 0 <= n <= self.blocks
                                          for n in node)):
                    raise ValueError(f"{taxi.taxi_id}: invalid intersection {node!r}")
            for start, end in zip(taxi.route, taxi.route[1:] + taxi.route[:1]):
                if abs(start[0] - end[0]) + abs(start[1] - end[1]) != 1:
                    raise ValueError(f"{taxi.taxi_id}: disconnected road {start} -> {end}")


def load_config(path: str | Path) -> DemoConfig:
    """Read required fields without substituting hidden defaults."""
    with Path(path).open("rb") as source:
        data = tomllib.load(source)
    try:
        return DemoConfig(
            blocks=data["blocks"],
            block_size_m=data["block_size_m"],
            tick_seconds=data["tick_seconds"],
            taxis=tuple(TaxiPlan(taxi_id=t["taxi_id"], speed_mps=t["speed_mps"],
                                 route=tuple(tuple(node) for node in t["route"]))
                        for t in data["taxis"]),
        )
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Invalid demo configuration {path}: {exc}") from exc


@dataclass(frozen=True)
class TaxiSnapshot:
    taxi_id: str
    x_m: float
    y_m: float
    heading_degrees: float
    distance_m: float
    state: str = "demo_cruising"


@dataclass(frozen=True)
class Passenger:
    """Prototype data only; runtime request lifecycle is not implemented yet."""

    passenger_id: str
    origin: tuple[int, int]
    destination: tuple[int, int]
    requested_at_seconds: float

    def __post_init__(self) -> None:
        if not isinstance(self.passenger_id, str) or not self.passenger_id.strip():
            raise ValueError("passenger_id: expected a non-empty string")
        for name, node in (("origin", self.origin), ("destination", self.destination)):
            if (not isinstance(node, tuple) or len(node) != 2
                    or any(type(n) is not int or not 0 <= n <= 3 for n in node)):
                raise ValueError(f"{self.passenger_id}.{name}: invalid intersection {node!r}")
        value = self.requested_at_seconds
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value < 0):
            raise ValueError(f"{self.passenger_id}: invalid request time {value!r}")

    @property
    def state(self) -> str:
        return "waiting"


class SimulationClock:
    def __init__(self, tick_seconds: float) -> None:
        _positive(tick_seconds, "tick_seconds")
        self._tick_seconds = tick_seconds
        self._tick = 0

    @property
    def tick(self) -> int:
        return self._tick

    @property
    def time_seconds(self) -> float:
        return self._tick * self._tick_seconds

    def advance(self, ticks: int = 1) -> None:
        if type(ticks) is not int or ticks < 0:
            raise ValueError("ticks: expected a non-negative integer")
        self._tick += ticks

    def reset(self) -> None:
        self._tick = 0


class Simulation:
    """Advance in integer ticks, independent of real time and render frequency."""

    def __init__(self, config: DemoConfig) -> None:
        self.config = config
        self.clock = SimulationClock(config.tick_seconds)

    @property
    def tick(self) -> int:
        return self.clock.tick

    @property
    def time_seconds(self) -> float:
        return self.clock.time_seconds

    def advance(self, ticks: int = 1) -> None:
        self.clock.advance(ticks)

    def reset(self) -> None:
        self.clock.reset()

    def snapshot(self) -> tuple[TaxiSnapshot, ...]:
        result = []
        size = self.config.block_size_m
        for taxi in self.config.taxis:
            distance = self.time_seconds * taxi.speed_mps
            progress = (distance / size) % len(taxi.route)
            index = int(progress)
            fraction = progress - index
            start = taxi.route[index]
            end = taxi.route[(index + 1) % len(taxi.route)]
            dx, dy = end[0] - start[0], end[1] - start[1]
            result.append(TaxiSnapshot(
                taxi_id=taxi.taxi_id,
                x_m=(start[0] + dx * fraction) * size,
                y_m=(start[1] + dy * fraction) * size,
                heading_degrees=math.degrees(math.atan2(-dx, dy)),
                distance_m=distance,
            ))
        return tuple(result)
