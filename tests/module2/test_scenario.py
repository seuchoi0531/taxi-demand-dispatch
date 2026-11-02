"""Reproducibility, input rejection and generator boundaries."""

import random

import pytest

from module2_preprocessing import generate_scenario


def settings(**overrides):
    return dict(seed=42, call_count=8, start_seconds=0.0,
                interval_seconds=10.0, tick_seconds=0.05) | overrides


def test_reproducibility_and_private_random_stream():
    before = random.getstate()
    first = generate_scenario(**settings())
    assert random.getstate() == before
    assert first == generate_scenario(**settings())
    assert first != generate_scenario(**settings(seed=7))


def test_call_times_and_distinct_valid_nodes():
    scenario = generate_scenario(**settings(start_seconds=0.1, interval_seconds=0.15))
    assert len(scenario["calls"]) == 8
    assert len({call["call_id"] for call in scenario["calls"]}) == 8
    for index, call in enumerate(scenario["calls"]):
        assert call["requested_at_seconds"] == pytest.approx(0.1 + index * 0.15)
        assert call["origin"] != call["destination"]
        assert all(type(axis) is int and 0 <= axis <= 3
                   for point in (call["origin"], call["destination"]) for axis in point)


def test_empty_scenario_is_valid():
    assert generate_scenario(**settings(call_count=0)) == {"schema_version": "0.1", "calls": []}


@pytest.mark.parametrize("overrides", [
    {"seed": True}, {"seed": 1.5}, {"call_count": -1}, {"call_count": True},
    {"call_count": 1.5}, {"start_seconds": -1}, {"start_seconds": 0.01},
    {"start_seconds": float("nan")}, {"interval_seconds": 0},
    {"interval_seconds": 0.03}, {"interval_seconds": float("inf")},
    {"tick_seconds": 0}, {"tick_seconds": True}, {"tick_seconds": float("nan")},
])
def test_invalid_settings_are_rejected(overrides):
    with pytest.raises(ValueError):
        generate_scenario(**settings(**overrides))
