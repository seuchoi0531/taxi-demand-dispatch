"""Load simulation settings and existing call data, without generating calls."""

from dataclasses import dataclass
import json
from pathlib import Path
import tomllib

from .city import fields, identifier, node, number


@dataclass(frozen=True)
class TaxiConfig:
    taxi_id: str
    speed_mps: float
    initial_node: tuple[int, int]

    def __post_init__(self) -> None:
        identifier(self.taxi_id, "taxi_id")
        number(self.speed_mps, f"{self.taxi_id}.speed_mps", positive=True)
        object.__setattr__(self, "initial_node", node(self.initial_node, self.taxi_id))


@dataclass(frozen=True)
class SimulationConfig:
    blocks: int
    block_size_m: float
    tick_seconds: float
    taxis: tuple[TaxiConfig, ...]

    def __post_init__(self) -> None:
        if type(self.blocks) is not int or self.blocks != 3:
            raise ValueError("blocks: this MVP requires 3 × 3 blocks")
        number(self.block_size_m, "block_size_m", positive=True)
        number(self.tick_seconds, "tick_seconds", positive=True)
        if len(self.taxis) != 3 or any(not isinstance(t, TaxiConfig) for t in self.taxis):
            raise ValueError("taxis: expected exactly 3 TaxiConfig objects")
        object.__setattr__(self, "taxis", tuple(self.taxis))
        if len({t.taxi_id for t in self.taxis}) != 3:
            raise ValueError("duplicate taxi_id")


def load_config(path: str | Path) -> SimulationConfig:
    with Path(path).open("rb") as source:
        data = tomllib.load(source)
    fields(data, {"blocks", "block_size_m", "tick_seconds", "taxis"}, "configuration")
    if not isinstance(data["taxis"], list):
        raise ValueError("taxis: expected a list")
    taxis = []
    for taxi in data["taxis"]:
        fields(taxi, {"taxi_id", "speed_mps", "initial_node"}, "taxi configuration")
        taxis.append(TaxiConfig(**taxi))
    return SimulationConfig(data["blocks"], data["block_size_m"], data["tick_seconds"], tuple(taxis))


def load_calls(path: str | Path) -> list[dict]:
    with Path(path).open(encoding="utf-8") as source:
        data = json.load(source)
    fields(data, {"schema_version", "calls"}, "call scenario")
    if data["schema_version"] != "0.1" or not isinstance(data["calls"], list):
        raise ValueError("call scenario: expected schema_version '0.1' and a calls list")
    return data["calls"]
