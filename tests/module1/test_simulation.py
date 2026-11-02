"""Runtime behavior and failure paths, independent of rendering and policies."""

from dataclasses import replace
from pathlib import Path

import pytest

from module1_simulation import Simulation, SimulationClock, load_config
from module1_simulation.city import City


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def config():
    return load_config(ROOT / "configs/module1_demo.toml")


def call(call_id="p1", origin=(1, 0), destination=(2, 1), at=0):
    return dict(call_id=call_id, origin=list(origin), destination=list(destination),
                requested_at_seconds=at)


def taxi(simulation, index=0):
    return simulation.snapshot()[index]


def passenger(simulation, index=0):
    return simulation.passenger_snapshots()[index]


def test_taxis_wait_without_commands(config):
    simulation = Simulation(config)
    initial = simulation.snapshot()
    simulation.advance(2000)
    assert len(initial) == 3
    assert simulation.snapshot() == initial
    assert all(t.state == "idle" for t in initial)
    assert all(m["idle_seconds"] == pytest.approx(100)
               for m in simulation.metrics()["by_taxi"].values())


def test_complete_passenger_journey_and_time_accounting(config):
    sim = Simulation(config, [call()])
    sim.advance(20)  # one second waiting before assignment
    sim.dispatch("taxi-1", "p1")
    assert taxi(sim).state == "to_pickup"
    assert passenger(sim).state == "assigned"
    sim.advance(40)
    assert (taxi(sim).x_m, taxi(sim).y_m) == pytest.approx((10, 0))
    assert (passenger(sim).x_m, passenger(sim).y_m) == (20, 0)
    sim.advance(40)
    assert taxi(sim).state == "occupied"
    assert passenger(sim).state == "onboard"
    assert passenger(sim).picked_up_at_seconds == pytest.approx(5)
    sim.advance(80)
    assert (taxi(sim).x_m, taxi(sim).y_m) == pytest.approx((40, 0))
    assert passenger(sim).x_m == taxi(sim).x_m
    assert passenger(sim).y_m == taxi(sim).y_m
    sim.advance(80)
    assert taxi(sim).state == "idle" and taxi(sim).call_id is None
    assert passenger(sim).state == "completed"
    assert passenger(sim).completed_at_seconds == pytest.approx(13)
    assert (passenger(sim).x_m, passenger(sim).y_m) == (40, 20)
    sim.advance(40)
    measured = sim.metrics()
    assert measured["by_taxi"]["taxi-1"] == pytest.approx(dict(
        idle_seconds=3, pickup_seconds=4, occupied_seconds=8,
        distance_m=60, empty_distance_m=20, completed_calls=1))
    assert measured["mean_wait_seconds"] == pytest.approx(5)
    assert measured["occupancy_percent"] == pytest.approx(100 * 8 / 45)
    assert measured["completed_calls"] == 1 and measured["pending_calls"] == 0
    events = [e["event"] for e in sim.events()]
    assert events == ["simulation_started", "call_created", "assigned",
                      "pickup_completed", "trip_started", "dropoff_completed"]


def test_sub_tick_arrival_and_remaining_time_are_not_rounded(config):
    fast = replace(config.taxis[0], speed_mps=30)
    config = replace(config, tick_seconds=1, taxis=(fast, *config.taxis[1:]))
    sim = Simulation(config, [call(destination=(1, 1))])
    sim.dispatch("taxi-1", "p1")
    sim.advance()
    assert passenger(sim).picked_up_at_seconds == pytest.approx(2 / 3)
    assert taxi(sim).y_m == pytest.approx(10)
    sim.advance()
    assert passenger(sim).completed_at_seconds == pytest.approx(4 / 3)
    measured = sim.metrics()["by_taxi"]["taxi-1"]
    for field in ("idle_seconds", "pickup_seconds", "occupied_seconds"):
        assert measured[field] == pytest.approx(2 / 3)


def test_multiple_edges_and_transitions_in_one_tick(config):
    fast = replace(config.taxis[0], speed_mps=200)
    config = replace(config, tick_seconds=1, taxis=(fast, *config.taxis[1:]))
    sim = Simulation(config, [call(origin=(3, 3), destination=(0, 0))])
    sim.dispatch("taxi-1", "p1")
    sim.advance(2)
    assert passenger(sim).completed_at_seconds == pytest.approx(1.2)
    assert taxi(sim).distance_m == pytest.approx(240)
    assert sim.metrics()["by_taxi"]["taxi-1"]["idle_seconds"] == pytest.approx(0.8)


def test_zero_distance_pickup_and_trip(config):
    sim = Simulation(config, [call(origin=(0, 0), destination=(0, 0))])
    sim.dispatch("taxi-1", "p1")
    assert passenger(sim).state == "completed"
    assert passenger(sim).wait_seconds == 0
    assert taxi(sim).state == "idle"
    sim.advance()
    assert sim.metrics()["by_taxi"]["taxi-1"]["idle_seconds"] == config.tick_seconds


def test_release_at_exact_time_and_deterministic_call_order(config):
    sim = Simulation(config, [call("b", at=2), call("a", at=2)])
    sim.advance(39)
    assert sim.passenger_snapshots() == ()
    sim.advance()
    assert [p.call_id for p in sim.passenger_snapshots()] == ["a", "b"]
    assert all(p.state == "waiting" for p in sim.passenger_snapshots())


def test_busy_taxi_and_duplicate_call_assignment_are_rejected(config):
    sim = Simulation(config, [call(), call("p2")])
    sim.dispatch("taxi-1", "p1")
    before = sim.observe()
    for taxi_id, call_id in (("taxi-1", "p2"), ("taxi-2", "p1")):
        with pytest.raises(ValueError):
            sim.dispatch(taxi_id, call_id)
    assert sim.observe()["taxis"] == before["taxis"]
    assert sim.observe()["passengers"] == before["passengers"]
    assert sim.metrics()["rejected_commands"] == 2


def test_completed_call_cannot_be_assigned_again(config):
    sim = Simulation(config, [call(origin=(0, 0), destination=(0, 0))])
    sim.dispatch("taxi-1", "p1")
    with pytest.raises(ValueError, match="completed"):
        sim.dispatch("taxi-2", "p1")


@pytest.mark.parametrize("command", [
    {"type": "dispatch", "taxi_id": "unknown", "call_id": "p1"},
    {"type": "dispatch", "taxi_id": "taxi-1", "call_id": "unknown"},
    {"type": "relocate", "taxi_id": "taxi-1", "zone_id": "zone-1-1"},
    {"type": "dispatch", "taxi_id": "taxi-1"},
    {"type": "dispatch", "taxi_id": [], "call_id": "p1"},
    {"type": "cancel"}, None,
])
def test_invalid_commands_do_not_mutate_runtime(config, command):
    sim = Simulation(config, [call()])
    before = sim.observe()
    with pytest.raises(ValueError):
        sim.apply_command(command)
    assert sim.observe()["taxis"] == before["taxis"]
    assert sim.observe()["passengers"] == before["passengers"]
    assert sim.events()[-1]["event"] == "command_rejected"


@pytest.mark.parametrize("ticks", [-1, 0.5, True])
def test_clock_and_simulation_reject_invalid_progress(config, ticks):
    clock = SimulationClock(0.05)
    clock.advance(20)
    with pytest.raises(ValueError):
        clock.advance(ticks)
    assert clock.time_seconds == 1
    sim = Simulation(config)
    with pytest.raises(ValueError):
        sim.advance(ticks)
    assert sim.tick == 0


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
        replace(config.taxis[0], speed_mps=-1)
    with pytest.raises(ValueError, match="intersection"):
        replace(config.taxis[0], initial_node=(4, 0))


@pytest.mark.parametrize("changes", [
    {"call_id": ""}, {"origin": [-1, 0]}, {"destination": [4, 0]},
    {"origin": [True, 1]}, {"requested_at_seconds": -1},
    {"requested_at_seconds": float("inf")}, {"requested_at_seconds": 0.023},
    {"requested_at_seconds": True}, {"extra": 0},
])
def test_invalid_call_is_rejected_before_running(config, changes):
    with pytest.raises(ValueError):
        Simulation(config, [call() | changes])


def test_missing_and_duplicate_call_fields_are_errors(config):
    with pytest.raises(ValueError):
        Simulation(config, [dict(call_id="p1")])
    with pytest.raises(ValueError, match="duplicate"):
        Simulation(config, [call(), call()])


def test_missing_config_fields_are_reported(tmp_path):
    source = tmp_path / "invalid.toml"
    source.write_text("blocks = 3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="block_size_m"):
        load_config(source)


def test_all_pairs_paths_and_all_zones():
    city = City(20)
    nodes = [(x, y) for x in range(4) for y in range(4)]
    for start in nodes:
        for end in nodes:
            path = city.shortest_path(start, end)
            assert len(path) == abs(start[0] - end[0]) + abs(start[1] - end[1])
            assert all(0 <= x <= 3 and 0 <= y <= 3 for x, y in path)
            for a, b in zip((start,) + path, path):
                assert abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
            assert (path[-1] if path else start) == end
    for x in range(3):
        for y in range(3):
            assert city.zone_at(x * 20, y * 20) == f"zone-{x}-{y}"
    assert city.zone_at(60, 60) == "zone-2-2"
    with pytest.raises(ValueError):
        city.zone_at(-1, 0)
