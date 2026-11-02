"""The user-selected temporary demo rule; no preassigned taxi/call pairs."""

from dataclasses import replace
from pathlib import Path

from module1_simulation import Simulation, load_config
from module1_simulation.demo import DemoRunner


ROOT = Path(__file__).resolve().parents[2]


def config():
    return load_config(ROOT / "configs/module1_demo.toml")


def call(call_id, origin, destination, at=0):
    return dict(call_id=call_id, origin=origin, destination=destination, requested_at_seconds=at)


def test_new_call_id_uses_nearest_idle_taxi_without_any_script():
    sim = Simulation(config(), [call("not-in-any-script", [3, 2], [0, 0])])
    DemoRunner(sim, auto_assign=True)
    assert sim.passenger_snapshots()[0].taxi_id == "taxi-3"
    assert sim.passenger_snapshots()[0].state == "onboard"


def test_distance_is_road_distance_not_straight_line_or_taxi_number():
    original = config()
    taxis = tuple(replace(t, initial_node=point) for t, point in
                  zip(original.taxis, ((2, 2), (3, 0), (3, 3))))
    sim = Simulation(replace(original, taxis=taxis), [call("request", [0, 0], [1, 0])])
    DemoRunner(sim, auto_assign=True)
    # taxi-1 is closer in a straight line, but taxi-2 has the shortest road distance.
    assert sim.passenger_snapshots()[0].taxi_id == "taxi-2"


def test_equal_distances_use_stable_taxi_id_tie_break():
    original = config()
    sim = Simulation(replace(original, taxis=tuple(reversed(original.taxis))),
                     [call("request", [1, 0], [2, 0])])
    DemoRunner(sim, auto_assign=True)
    assert sim.passenger_snapshots()[0].taxi_id == "taxi-1"


def test_when_all_busy_oldest_call_gets_next_free_taxi_even_if_new_call_is_closer():
    sim = Simulation(config(), [
        call("a", [0, 0], [1, 0]), call("b", [1, 1], [2, 1]), call("c", [3, 2], [3, 3]),
        call("older", [0, 0], [0, 1], 1), call("newer", [3, 3], [3, 2], 3.35),
    ])
    runner = DemoRunner(sim, auto_assign=True)
    runner.advance(20)
    assert sim.passenger_snapshots()[-1].state == "waiting"
    runner.advance(47)
    people = {p.call_id: p for p in sim.passenger_snapshots()}
    assert people["older"].taxi_id == "taxi-3"
    assert people["older"].assigned_at_seconds == 3.35
    assert people["newer"].state == "waiting"
    assert sim.metrics()["rejected_commands"] == 0


def test_simultaneous_calls_use_different_available_taxis():
    sim = Simulation(config(), [call(name, [0, 0], [1, 0]) for name in ("a", "b", "c")])
    DemoRunner(sim, auto_assign=True)
    assert [p.taxi_id for p in sim.passenger_snapshots()] == ["taxi-1", "taxi-2", "taxi-3"]


def test_future_calls_are_not_assigned_until_they_occur():
    sim = Simulation(config(), [call("future", [3, 2], [3, 3], 1)])
    runner = DemoRunner(sim, auto_assign=True)
    runner.advance(19)
    assert all(t.state == "idle" for t in sim.snapshot())
    runner.advance()
    assert sim.passenger_snapshots()[0].taxi_id == "taxi-3"
