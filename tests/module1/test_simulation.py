"""Behavioral tests for the first movement prototype, without a GPU."""

from dataclasses import replace
from pathlib import Path

import pytest

from module1_simulation.simulation import (
    Passenger, Simulation, SimulationClock, load_config,
)


@pytest.fixture
def config():
    return load_config(Path(__file__).resolve().parents[2] / "configs/module1_demo.toml")


def test_three_taxis_move_on_roads_and_stay_in_city(config):
    simulation = Simulation(config)
    initial = simulation.snapshot()
    size = config.block_size_m
    for _ in range(2000):
        simulation.advance()
        for taxi in simulation.snapshot():
            assert 0 <= taxi.x_m <= 3 * size
            assert 0 <= taxi.y_m <= 3 * size
            assert (taxi.x_m / size == pytest.approx(round(taxi.x_m / size))
                    or taxi.y_m / size == pytest.approx(round(taxi.y_m / size)))
    assert len(simulation.snapshot()) == 3
    assert simulation.snapshot() != initial


def test_speed_turn_and_full_route(config):
    simulation = Simulation(config)
    simulation.advance(40)
    taxi = simulation.snapshot()[0]
    assert (taxi.x_m, taxi.y_m, taxi.distance_m) == pytest.approx((10, 0, 10))
    simulation.advance(200)
    taxi = simulation.snapshot()[0]
    assert (taxi.x_m, taxi.y_m, taxi.heading_degrees) == pytest.approx((60, 0, 0))
    simulation.advance(720)
    taxi = simulation.snapshot()[0]
    assert (taxi.x_m, taxi.y_m, taxi.distance_m) == pytest.approx((0, 0, 240))


def test_tick_batching_and_reset_are_reproducible(config):
    first, second = Simulation(config), Simulation(config)
    for _ in range(913):
        first.advance()
    second.advance(913)
    assert first.snapshot() == second.snapshot()
    assert first.time_seconds == second.time_seconds
    first.reset()
    assert first.tick == 0
    assert first.snapshot() == Simulation(config).snapshot()


@pytest.mark.parametrize("ticks", [-1, 0.5, True])
def test_clock_rejects_invalid_progress_without_mutation(ticks):
    clock = SimulationClock(0.05)
    clock.advance(20)
    with pytest.raises(ValueError):
        clock.advance(ticks)
    assert clock.time_seconds == 1


@pytest.mark.parametrize("field,value", [
    ("blocks", 4), ("block_size_m", 0), ("tick_seconds", float("nan")),
    ("tick_seconds", True),
])
def test_invalid_dimensions_or_time_are_rejected(config, field, value):
    with pytest.raises(ValueError):
        replace(config, **{field: value})


def test_invalid_taxis_are_rejected(config):
    with pytest.raises(ValueError, match="exactly 3"):
        replace(config, taxis=config.taxis[:2])
    with pytest.raises(ValueError, match="duplicate taxi_id"):
        replace(config, taxis=(config.taxis[0], config.taxis[0], config.taxis[2]))
    with pytest.raises(ValueError, match="speed_mps"):
        replace(config, taxis=(replace(config.taxis[0], speed_mps=-1), *config.taxis[1:]))


@pytest.mark.parametrize("route", [((0, 0), (1, 1)), ((0, 0), (4, 0)),
                                  ((0, 0), (1, 0), (2, 0))])
def test_invalid_roads_including_loop_closure_are_rejected(config, route):
    with pytest.raises(ValueError):
        replace(config, taxis=(replace(config.taxis[0], route=route), *config.taxis[1:]))


def test_missing_config_fields_are_reported(tmp_path):
    source = tmp_path / "invalid.toml"
    source.write_text("blocks = 3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="block_size_m"):
        load_config(source)


def test_passenger_definition():
    passenger = Passenger("passenger-1", (0, 0), (3, 3), 2.5)
    assert passenger.state == "waiting"
    assert passenger.origin == (0, 0)
    assert passenger.destination == (3, 3)
    assert passenger.requested_at_seconds == 2.5


@pytest.mark.parametrize("changes", [
    {"passenger_id": ""}, {"origin": (-1, 0)}, {"destination": (4, 0)},
    {"requested_at_seconds": -1}, {"requested_at_seconds": float("inf")},
])
def test_invalid_passenger_is_rejected(changes):
    fields = dict(passenger_id="p1", origin=(0, 0), destination=(3, 3),
                  requested_at_seconds=0)
    with pytest.raises(ValueError):
        Passenger(**(fields | changes))
