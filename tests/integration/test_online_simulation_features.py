"""Actual Module 1 observations feed Module 2 and Module 3 without targets."""

from copy import deepcopy
from dataclasses import replace

import pytest

from module1_simulation import Simulation, load_config
from module2_preprocessing import build_simulation_features
from module3_prediction import predict


def simulation():
    config = replace(load_config("configs/module1_demo.toml"), tick_seconds=1)
    calls = [dict(call_id=f"call-{i}", requested_at_seconds=i * 300,
                  origin=[0, 0], destination=[1, 0]) for i in range(14)]
    sim = Simulation(config, calls)
    sim.dispatch("taxi-1", "call-0")
    sim.advance(3600)
    return sim


def features(observation, start=0, evidence="Complete cumulative synthetic Simulation.observe history"):
    return build_simulation_features(observation, complete_since_seconds=start,
                                      coverage_evidence=evidence)


def test_simulation_observation_to_features_and_both_forecast_models():
    sim = simulation()
    observation = sim.observe()
    before = deepcopy(observation)
    assert observation["passengers"][0]["state"] == "completed"
    assert len(observation["passengers"]) == 13  # Includes t, excludes future reservation.
    rows = features(observation)
    assert observation == before
    assert len(rows) == 9
    assert rows[0]["lag_12"] == rows[0]["lag_1"] == 1
    assert rows[0]["rolling_mean_12"] == 1
    assert all(row["lag_1"] == 0 for row in rows[1:])
    for model in ("rolling-mean-12", "recent-trend"):
        forecasts = [predict(row, model=model) for row in rows]
        assert len(forecasts) == 9
        assert all(f["prediction_time_seconds"] == observation["time_seconds"] for f in forecasts)
        assert [p["predicted_demand"] for p in forecasts[0]["predictions"]] == [1] * 6
    sim.advance(300)
    assert all(row["prediction_time_seconds"] == 3900 for row in features(sim.observe()))
    assert features(simulation().observe()) == rows


def test_empty_complete_simulation_and_insufficient_confirmed_history():
    config = replace(load_config("configs/module1_demo.toml"), tick_seconds=1)
    sim = Simulation(config, [])
    sim.advance(3600)
    assert all(row["rolling_mean_12"] == 0 for row in features(sim.observe()))
    with pytest.raises(ValueError, match="coverage"):
        features(sim.observe(), start=300)
    with pytest.raises(ValueError, match="coverage_evidence"):
        features(sim.observe(), evidence="")


@pytest.mark.parametrize("defect", ["future", "missing_field", "time", "version"])
def test_observation_errors_are_not_hidden(defect):
    observation = simulation().observe()
    if defect == "future":
        observation["passengers"][0]["requested_at_seconds"] = 3601
    elif defect == "missing_field":
        del observation["passengers"][0]["origin"]
    elif defect == "time":
        observation["time_seconds"] = 3601
    else:
        observation["schema_version"] = "unknown"
    with pytest.raises(ValueError):
        features(observation)
