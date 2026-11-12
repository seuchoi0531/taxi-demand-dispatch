"""Reposition lifecycle, atomic rejection, measurements and replay."""

from dataclasses import replace

import pytest

from module1_simulation import Simulation, load_config


def simulation():
    return Simulation(load_config('configs/module1_demo.toml'))


def test_reposition_moves_on_roads_and_preserves_time_and_distance():
    sim = simulation()
    sim.reposition('taxi-1', [2, 1])
    sim.advance(100)
    taxi = sim.observe()['taxis'][0]
    assert taxi['state'] == 'repositioning'
    assert taxi['call_id'] is None
    assert (taxi['x_m'], taxi['y_m']) == pytest.approx((25, 0))
    sim.advance(160)
    taxi = sim.observe()['taxis'][0]
    assert (taxi['x_m'], taxi['y_m'], taxi['state']) == (40, 20, 'idle')
    measured = sim.metrics()['by_taxi']['taxi-1']
    assert measured['reposition_seconds'] == pytest.approx(12)
    assert measured['idle_seconds'] == pytest.approx(1)
    assert measured['distance_m'] == pytest.approx(60)
    assert measured['empty_distance_m'] == pytest.approx(60)
    assert sum(measured[k] for k in ('idle_seconds', 'pickup_seconds', 'occupied_seconds',
                                   'reposition_seconds')) == pytest.approx(sim.time_seconds)
    events = [e for e in sim.events() if e['event'].startswith('reposition_')]
    assert [e['time_seconds'] for e in events] == [0, 12]
    assert all(e['taxi_id'] == 'taxi-1' and e['call_id'] is None and
               e['details'] == {'destination': [2, 1]} for e in events)
    before, events = sim.observe(), sim.events()
    sim.reset()
    sim.reposition('taxi-1', [2, 1])
    for _ in range(13):
        sim.advance(20)
    assert sim.observe() == before
    assert sim.events() == events


def test_same_position_completes_immediately_without_time_or_distance():
    sim = simulation()
    sim.reposition('taxi-1', [0, 0])
    assert sim.snapshot()[0].state == 'idle'
    assert [e['event'] for e in sim.events()][-2:] == ['reposition_started', 'reposition_completed']
    assert all(e['time_seconds'] == 0 for e in sim.events())
    assert sim.metrics()['by_taxi']['taxi-1']['reposition_seconds'] == 0


@pytest.mark.parametrize('command', [
    {'type': 'reposition', 'taxi_id': 'missing', 'destination': [1, 1]},
    *[{'type': 'reposition', 'taxi_id': 'taxi-1', 'destination': dest}
      for dest in ([4, 0], [-1, 0], [True, 0], [1.0, 0], None, [1])],
    {'type': 'reposition', 'taxi_id': 'taxi-1'},
    {'type': 'reposition', 'taxi_id': 'taxi-1', 'destination': [1, 1], 'call_id': 'a'},
])
def test_invalid_commands_leave_runtime_unchanged(command):
    sim = simulation()
    before = sim.observe()
    with pytest.raises(ValueError):
        sim.apply_command(command)
    after = sim.observe()
    after['metrics']['rejected_commands'] = before['metrics']['rejected_commands']
    assert after == before
    assert sim.events()[-1]['event'] == 'command_rejected'


@pytest.mark.parametrize('state', ['to_pickup', 'occupied', 'repositioning'])
def test_busy_taxi_rejects_both_command_types(state):
    sim = simulation()
    sim.add_calls([dict(call_id='a', origin=[1, 0] if state == 'to_pickup' else [0, 0],
                        destination=[3, 3], requested_at_seconds=0)])
    if state == 'repositioning':
        sim.reposition('taxi-1', [1, 1])
    else:
        sim.dispatch('taxi-1', 'a')
    assert sim.snapshot()[0].state == state
    before = sim.observe()
    for command in (dict(type='reposition', taxi_id='taxi-1', destination=[2, 2]),
                    dict(type='dispatch', taxi_id='taxi-1', call_id='a')):
        with pytest.raises(ValueError, match='must be idle'):
            sim.apply_command(command)
    after = sim.observe()
    after['metrics']['rejected_commands'] -= 2
    assert after == before


def test_subtick_arrival_records_exact_time_and_remaining_idle_time():
    config = load_config('configs/module1_demo.toml')
    sim = Simulation(replace(config, tick_seconds=3))
    sim.reposition('taxi-1', [1, 0])
    sim.advance(2)
    assert sim.events()[-1]['time_seconds'] == pytest.approx(4)
    measured = sim.metrics()['by_taxi']['taxi-1']
    assert measured['reposition_seconds'] == pytest.approx(4)
    assert measured['idle_seconds'] == pytest.approx(2)
