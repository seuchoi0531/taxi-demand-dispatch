"""Integration of call inputs, current automatic selection and the Module 1 runtime."""

from pathlib import Path
import json
import subprocess
import sys

import pytest

from module1_simulation import Simulation, load_calls, load_config
from module1_simulation.demo import DemoRunner


ROOT = Path(__file__).resolve().parents[2]


def demo():
    sim = Simulation(load_config(ROOT / "configs/module1_demo.toml"),
                     load_calls(ROOT / "tests/fixtures/module1_calls.json"))
    return sim, DemoRunner(sim, auto_assign=True)


def test_three_taxis_complete_calls_with_consistent_measurements():
    sim, runner = demo()
    for _ in range(1200):
        runner.advance()
        observed = sim.observe()
        taxis = {t["taxi_id"]: t for t in observed["taxis"]}
        assigned = set()
        for taxi in taxis.values():
            assert 0 <= taxi["x_m"] <= 60 and 0 <= taxi["y_m"] <= 60
            assert (taxi["x_m"] / 20 == pytest.approx(round(taxi["x_m"] / 20))
                    or taxi["y_m"] / 20 == pytest.approx(round(taxi["y_m"] / 20)))
            if taxi["call_id"] is not None:
                assert taxi["call_id"] not in assigned
                assigned.add(taxi["call_id"])
        for passenger in observed["passengers"]:
            assert passenger["requested_at_seconds"] <= sim.time_seconds
            if passenger["state"] in ("assigned", "onboard"):
                taxi = taxis[passenger["taxi_id"]]
                assert taxi["call_id"] == passenger["call_id"]
                assert taxi["state"] == ("to_pickup" if passenger["state"] == "assigned" else "occupied")
            if passenger["state"] == "onboard":
                assert (passenger["x_m"], passenger["y_m"]) == (taxi["x_m"], taxi["y_m"])
        for measured in observed["metrics"]["by_taxi"].values():
            times = [measured[k] for k in ("idle_seconds", "pickup_seconds", "occupied_seconds")]
            assert all(t >= 0 for t in times)
            assert sum(times) == pytest.approx(sim.time_seconds)
            assert 0 <= measured["empty_distance_m"] <= measured["distance_m"] + 1e-9
    measured = sim.metrics()
    assert measured["completed_calls"] == 6
    assert measured["pending_calls"] == 0
    assert measured["rejected_commands"] == 0
    assert all(t.state == "idle" for t in sim.snapshot())
    assert [p.wait_seconds for p in sim.passenger_snapshots()] == pytest.approx([4, 5, 10 / 3, 20 / 3, 5, 4])
    assert measured["mean_wait_seconds"] == pytest.approx(14 / 3)
    assert [e["time_seconds"] for e in sim.events()] == sorted(e["time_seconds"] for e in sim.events())


def test_replay_is_identical_for_different_frame_batching_and_reset():
    sim1, runner1 = demo()
    sim2, runner2 = demo()
    runner1.advance(1200)
    for _ in range(60):
        runner2.advance(20)
    assert sim1.observe() == sim2.observe()
    assert sim1.events() == sim2.events()
    original, events = sim1.observe(), sim1.events()
    runner1.reset()
    runner1.advance(1200)
    assert sim1.observe() == original
    assert sim1.events() == events


def test_manual_mode_never_implicitly_dispatches():
    sim, _ = demo()
    sim.reset()
    runner = DemoRunner(sim)
    runner.advance(1200)
    assert not runner.auto_assign
    assert all(t.state == "idle" and t.distance_m == 0 for t in sim.snapshot())
    assert all(p.state == "waiting" for p in sim.passenger_snapshots())


def test_invalid_external_assignment_is_raised_and_recorded():
    sim, _ = demo()
    sim.reset()
    sim.advance(20)
    with pytest.raises(ValueError, match="not available"):
        sim.dispatch("taxi-1", "call-6")
    assert sim.metrics()["rejected_commands"] == 1
    assert sim.snapshot()[0].state == "idle"


@pytest.mark.parametrize("manual", [False, True])
def test_documented_headless_cli_outputs_valid_result(manual):
    command = [sys.executable, "-m", "module1_simulation", "--headless", "--steps", "1200", "--events",
               "--scenario", "tests/fixtures/module1_calls.json"]
    if manual:
        command.append("--manual")
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    observed = json.loads(result.stdout)
    assert observed["metrics"]["completed_calls"] == (0 if manual else 6)
    assert observed["time_seconds"] == 60
    assert observed["events"]


@pytest.mark.parametrize("manual", [False, True])
def test_default_cli_streams_one_person_at_a_time_without_scenario_files(manual):
    command = [sys.executable, '-m', 'module1_simulation', '--headless', '--steps', '1200', '--events']
    if manual:
        command.append('--manual')
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    observed = json.loads(result.stdout)
    assert observed['time_seconds'] == 60
    assert [p['requested_at_seconds'] for p in observed['passengers']] == list(range(0, 61, 10))
    assert [p['call_id'] for p in observed['passengers']] == [f'call-{i}' for i in range(1, 8)]
    assert all(p['origin'] != p['destination'] for p in observed['passengers'])
    assert observed['metrics']['rejected_commands'] == 0
    if manual:
        assert all(t['state'] == 'idle' for t in observed['taxis'])


def test_finite_scenario_does_not_depend_on_continuous_call_settings(tmp_path):
    command = [sys.executable, '-m', 'module1_simulation', '--headless', '--steps', '1200',
               '--scenario', str(ROOT / 'tests/fixtures/module1_calls.json'),
               '--calls-config', str(tmp_path / 'not-needed.toml')]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)['metrics']['completed_calls'] == 6

