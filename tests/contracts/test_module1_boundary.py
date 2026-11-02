"""Test the documented plain-data interface via the public Module 1 facade."""

import json
from pathlib import Path

import pytest

from module1_simulation import Simulation, load_calls, load_config


ROOT = Path(__file__).resolve().parents[2]


def make_sim():
    return Simulation(load_config(ROOT / "configs/module1_demo.toml"),
                      load_calls(ROOT / "tests/fixtures/module1_calls.json"))


def test_public_observation_is_json_data_and_has_no_future_calls():
    sim = make_sim()
    observation = sim.observe()
    assert json.loads(json.dumps(observation, allow_nan=False)) == observation
    assert set(observation) == {"schema_version", "tick", "time_seconds", "taxis", "passengers", "metrics"}
    assert [p["call_id"] for p in observation["passengers"]] == ["call-1"]
    assert observation["metrics"]["pending_calls"] == 1
    assert observation["metrics"]["mean_wait_seconds"] is None
    assert observation["metrics"]["occupancy_percent"] is None
    assert "call-2" not in json.dumps(sim.events())
    with pytest.raises(ValueError, match="not available"):
        sim.dispatch("taxi-1", "call-2")


def test_read_results_and_input_data_cannot_mutate_runtime():
    calls = load_calls(ROOT / "tests/fixtures/module1_calls.json")
    sim = Simulation(load_config(ROOT / "configs/module1_demo.toml"), calls)
    calls[0]["origin"][0] = 99
    before = sim.observe()
    modified = sim.observe()
    modified["passengers"][0]["origin"][0] = 99
    modified["taxis"][0]["state"] = "occupied"
    modified["metrics"]["by_taxi"]["taxi-1"]["idle_seconds"] = 100
    events = sim.events()
    events[-1]["details"]["origin"][0] = 99
    assert sim.observe() == before
    assert sim.events()[-1]["details"]["origin"] == [1, 0]


@pytest.mark.parametrize("boundary", [4, 12])
def test_same_time_completion_then_call_then_command(boundary):
    config = load_config(ROOT / "configs/module1_demo.toml")
    sim = Simulation(config, [
        dict(call_id="a", requested_at_seconds=0, origin=[0, 0],
             destination=[1, 0] if boundary == 4 else [2, 1]),
        dict(call_id="b", requested_at_seconds=boundary,
             origin=[1, 0] if boundary == 4 else [2, 1], destination=[1, 1]),
    ])
    sim.apply_command(dict(type="dispatch", taxi_id="taxi-1", call_id="a"))
    sim.advance(boundary * 20)
    sim.apply_command(dict(type="dispatch", taxi_id="taxi-1", call_id="b"))
    events = [e["event"] for e in sim.events() if e["time_seconds"] == boundary]
    assert events == ["dropoff_completed", "call_created", "assigned", "pickup_completed", "trip_started"]
    assert sim.observe()["passengers"][1]["state"] == "onboard"


def test_added_calls_release_at_their_time_without_resetting_existing_state():
    sim = make_sim()
    sim.dispatch("taxi-1", "call-1")
    sim.advance(20)
    before = sim.observe()
    sim.add_calls([
        dict(call_id="new-now", requested_at_seconds=1, origin=[0, 0], destination=[1, 0]),
        dict(call_id="new-later", requested_at_seconds=3, origin=[0, 1], destination=[1, 1]),
    ])
    assert sim.tick == 20
    assert sim.observe()["taxis"] == before["taxis"]
    assert "new-now" in {p.call_id for p in sim.passenger_snapshots()}
    assert "new-later" not in {p.call_id for p in sim.passenger_snapshots()}
    sim.advance(40)
    assert "new-later" in {p.call_id for p in sim.passenger_snapshots()}


@pytest.mark.parametrize("bad", [
    dict(call_id="call-1", requested_at_seconds=2, origin=[0, 0], destination=[1, 0]),
    dict(call_id="past", requested_at_seconds=0, origin=[0, 0], destination=[1, 0]),
])
def test_bad_incremental_input_is_rejected_atomically(bad):
    sim = make_sim()
    sim.advance(20)
    before, events = sim.observe(), sim.events()
    with pytest.raises(ValueError):
        sim.add_calls([dict(call_id="valid", requested_at_seconds=1, origin=[0, 0], destination=[1, 0]), bad])
    assert sim.observe() == before
    assert sim.events() == events
