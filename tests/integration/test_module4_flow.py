"""Public Module 4 commands execute without a development matching policy."""

import pytest

from module1_simulation import Simulation, load_config
from module1_simulation.demo import DemoRunner
from module4_dispatch import build_plan
from tests.module4.test_policy import forecasts


def run_flow():
    sim = Simulation(load_config('configs/module1_demo.toml'))
    runner = DemoRunner(sim, auto_assign=False)
    plan = build_plan(sim.observe(), block_size_m=sim.config.block_size_m,
                      forecasts=forecasts({'zone-0-2': 1}, prediction_time=0))
    assert any(c['type'] == 'reposition' for c in plan['commands'])
    for command in plan['commands']:
        sim.apply_command(command)
    runner.advance(400)
    destination = next(c['destination'] for c in plan['commands'] if c['type'] == 'reposition')
    sim.add_calls([dict(call_id='after-reposition', origin=destination, destination=[0, 0],
                        requested_at_seconds=sim.time_seconds)])
    runner.advance()
    assert sim.passenger_snapshots()[0].state == 'waiting'
    plan = build_plan(sim.observe(), block_size_m=sim.config.block_size_m)
    for command in plan['commands']:
        sim.apply_command(command)
    runner.advance(400)
    assert sim.metrics()['completed_calls'] == 1
    assert sim.metrics()['rejected_commands'] == 0
    assert any(e['event'] == 'reposition_completed' for e in sim.events())
    for measured in sim.metrics()['by_taxi'].values():
        assert sum(measured[k] for k in ('idle_seconds', 'pickup_seconds', 'occupied_seconds',
                                       'reposition_seconds')) == pytest.approx(sim.time_seconds)
    return sim.observe(), sim.events()


def test_module4_commands_complete_and_replay_identically():
    assert run_flow() == run_flow()
