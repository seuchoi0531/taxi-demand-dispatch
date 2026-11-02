"""Individual continuous calls, without batches or recorded input dependencies."""

from pathlib import Path
import random

import pytest

from module1_simulation import Simulation, load_config
from module1_simulation.demo import DemoRunner, load_call_settings

ROOT = Path(__file__).resolve().parents[2]


def make_demo(seed=42, interval=5, manual=False):
    sim = Simulation(load_config(ROOT / 'configs/module1_demo.toml'))
    return sim, DemoRunner(sim, call_interval_seconds=interval, seed=seed, auto_assign=not manual)


def test_exactly_one_new_passenger_at_each_interval():
    sim, runner = make_demo(manual=True)
    assert len(sim.passenger_snapshots()) == 1
    for i in range(1, 21):
        before = sim.observe()['taxis']
        runner.advance(99)
        assert len(sim.passenger_snapshots()) == i
        runner.advance()
        assert len(sim.passenger_snapshots()) == i + 1
        person = sim.passenger_snapshots()[-1]
        assert person.call_id == f'call-{i + 1}'
        assert person.requested_at_seconds == i * 5
        assert sim.observe()['taxis'] == before
    assert sim.time_seconds == 100
    assert all(p.state == 'waiting' for p in sim.passenger_snapshots())
    assert not any('@' in p.call_id for p in sim.passenger_snapshots())


def test_random_locations_are_valid_distinct_and_use_private_rng():
    state = random.getstate()
    sim, runner = make_demo(manual=True)
    runner.advance(2400)
    assert random.getstate() == state
    assert len(sim.passenger_snapshots()) == 25
    positions = set()
    for passenger in sim.passenger_snapshots():
        assert passenger.origin != passenger.destination
        for point in (passenger.origin, passenger.destination):
            assert all(type(n) is int and 0 <= n <= 3 for n in point)
        positions.add((passenger.origin, passenger.destination))
    assert len(positions) > 1


def test_seed_batching_and_reset_are_reproducible():
    sim1, runner1 = make_demo()
    sim2, runner2 = make_demo()
    sim3, runner3 = make_demo(seed=7)
    runner1.advance(2401)
    for ticks in (1000, 400, 1001):
        runner2.advance(ticks)
    runner3.advance(2401)
    observed, events = sim1.observe(), sim1.events()
    assert observed == sim2.observe()
    assert events == sim2.events()
    assert [(p.origin, p.destination) for p in sim1.passenger_snapshots()] != [
        (p.origin, p.destination) for p in sim3.passenger_snapshots()]
    assert sim1.metrics()['rejected_commands'] == 0
    assert sim1.metrics()['completed_calls'] > 0
    runner1.reset()
    assert sim1.tick == 0 and len(sim1.passenger_snapshots()) == 1
    runner1.advance(2401)
    assert sim1.observe() == observed
    assert sim1.events() == events


def test_nondefault_interval():
    sim, runner = make_demo(interval=2, manual=True)
    runner.advance(200)
    assert [p.requested_at_seconds for p in sim.passenger_snapshots()] == [0, 2, 4, 6, 8, 10]


@pytest.mark.parametrize('interval', [0, -1, float('inf'), float('nan'), True, 0.023, 1e-14])
def test_invalid_interval_is_rejected(interval):
    with pytest.raises(ValueError):
        make_demo(interval=interval)


def test_call_settings_load_and_reject_invalid_seed(tmp_path):
    assert load_call_settings(ROOT / 'configs/module1_calls.toml') == dict(interval_seconds=10.0, seed=42)
    source = tmp_path / 'invalid.toml'
    source.write_text('interval_seconds = 5.0\nseed = true\n')
    with pytest.raises(ValueError, match='seed'):
        load_call_settings(source)


@pytest.mark.parametrize('at', [0, 30])
def test_continuous_input_rejects_initial_scenario_even_before_first_call(at):
    config = load_config(ROOT / 'configs/module1_demo.toml')
    sim = Simulation(config, [dict(call_id='recorded', requested_at_seconds=at,
                                   origin=[0, 0], destination=[1, 0])])
    assert sim.has_initial_calls
    with pytest.raises(ValueError, match='cannot be combined'):
        DemoRunner(sim, call_interval_seconds=10)
    assert sim.tick == 0
    assert len(sim.passenger_snapshots()) == (1 if at == 0 else 0)
