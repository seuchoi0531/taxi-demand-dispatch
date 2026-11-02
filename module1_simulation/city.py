"""The small road graph owned by Module 1."""

from dataclasses import dataclass
import math


def number(value: object, name: str, *, positive: bool = False) -> None:
    if (type(value) not in (int, float) or not math.isfinite(value)
            or (value <= 0 if positive else value < 0)):
        bound = "positive" if positive else "non-negative"
        raise ValueError(f"{name}: expected a finite {bound} number, got {value!r}")


def node(value: object, name: str) -> tuple[int, int]:
    if (not isinstance(value, (tuple, list)) or len(value) != 2
            or any(type(n) is not int or not 0 <= n <= 3 for n in value)):
        raise ValueError(f"{name}: expected an intersection [x,y] with integers 0..3")
    return tuple(value)


def identifier(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name}: expected a non-empty string")


def fields(value: object, required: set[str], name: str) -> None:
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError(f"{name}: expected exactly these fields: {sorted(required)}")


def tick_at(seconds: float, tick_seconds: float, name: str) -> int:
    number(seconds, name)
    tick = round(seconds / tick_seconds)
    if not math.isclose(tick * tick_seconds, seconds, rel_tol=0, abs_tol=1e-9):
        raise ValueError(f"{name}: {seconds} is not aligned with tick_seconds={tick_seconds}")
    return tick


@dataclass(frozen=True)
class City:
    block_size_m: float

    def __post_init__(self) -> None:
        number(self.block_size_m, "block_size_m", positive=True)

    def shortest_path(self, origin, destination) -> tuple[tuple[int, int], ...]:
        start, end = node(origin, "origin"), node(destination, "destination")
        x, y = start
        route = []
        while x != end[0]:
            x += 1 if x < end[0] else -1
            route.append((x, y))
        while y != end[1]:
            y += 1 if y < end[1] else -1
            route.append((x, y))
        return tuple(route)

    def zone_at(self, x_m: float, y_m: float) -> str:
        extent = 3 * self.block_size_m
        if not (math.isfinite(x_m) and math.isfinite(y_m)
                and 0 <= x_m <= extent and 0 <= y_m <= extent):
            raise ValueError(f"position outside city: {(x_m, y_m)}")
        x, y = min(int(x_m / self.block_size_m), 2), min(int(y_m / self.block_size_m), 2)
        return f"zone-{x}-{y}"
