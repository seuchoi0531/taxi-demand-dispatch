"""Finite synthetic inputs conforming to the existing Module 1 call contract."""

import math
import random


def _tick(value: object, tick_seconds: float, name: str, *, positive: bool = False) -> int:
    if (type(value) not in (int, float) or not math.isfinite(value)
            or (value <= 0 if positive else value < 0)):
        raise ValueError(f"{name}: expected a finite {'positive' if positive else 'non-negative'} number")
    ratio = value / tick_seconds
    if not math.isfinite(ratio):
        raise ValueError(f"{name}: tick count is not finite")
    result = round(ratio)
    if not math.isclose(result * tick_seconds, value, rel_tol=0, abs_tol=1e-9):
        raise ValueError(f"{name}: must be aligned with tick_seconds")
    if positive and result == 0:
        raise ValueError(f"{name}: must span at least one tick")
    return result


def generate_scenario(*, seed: int, call_count: int, start_seconds: float,
                      interval_seconds: float, tick_seconds: float) -> dict:
    """Generate deterministic calls; never use the global random stream."""
    if type(seed) is not int:
        raise ValueError("seed: expected an integer")
    if type(call_count) is not int or call_count < 0:
        raise ValueError("call_count: expected a non-negative integer")
    if (type(tick_seconds) not in (int, float) or not math.isfinite(tick_seconds)
            or tick_seconds <= 0):
        raise ValueError("tick_seconds: expected a finite positive number")
    start = _tick(start_seconds, tick_seconds, "start_seconds")
    interval = _tick(interval_seconds, tick_seconds, "interval_seconds", positive=True)
    rng = random.Random(seed)
    nodes = [[x, y] for x in range(4) for y in range(4)]
    calls = []
    for index in range(call_count):
        at_seconds = (start + index * interval) * tick_seconds
        if not math.isfinite(at_seconds):
            raise ValueError(f"call-{index + 1}: generated time is not finite")
        origin, destination = rng.sample(nodes, 2)
        calls.append({
            "call_id": f"call-{index + 1}",
            "requested_at_seconds": at_seconds,
            "origin": origin.copy(),
            "destination": destination.copy(),
        })
    return {"schema_version": "0.1", "calls": calls}
