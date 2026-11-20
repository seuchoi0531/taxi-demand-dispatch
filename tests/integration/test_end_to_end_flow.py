"""Public cross-module flow with hidden future demand and a no-forecast control."""

from dataclasses import replace

import pytest

from module1_simulation import Simulation, load_config
from module2_preprocessing import build_simulation_features
from module3_prediction import predict
from module4_dispatch import build_plan
from scripts.visualize_end_to_end import build_history_calls


LIVE_CALLS = (
    {
        "call_id": "live-01-hot",
        "requested_at_seconds": 3620,
        "origin": [2, 3],
        "destination": [0, 0],
    },
    {
        "call_id": "live-02-hot",
        "requested_at_seconds": 3620,
        "origin": [3, 2],
        "destination": [0, 0],
    },
    {
        "call_id": "live-03-local",
        "requested_at_seconds": 3620,
        "origin": [0, 1],
        "destination": [3, 3],
    },
)


def _apply_plan(simulation, forecasts=None):
    plan = build_plan(
        simulation.observe(),
        block_size_m=simulation.config.block_size_m,
        forecasts=forecasts,
    )
    taxi_ids = [command["taxi_id"] for command in plan["commands"]]
    assert len(taxi_ids) == len(set(taxi_ids))
    for command in plan["commands"]:
        simulation.apply_command(command)
    return plan


def _simulation_at_prediction_time():
    config = replace(load_config("configs/module1_demo.toml"), tick_seconds=1)
    simulation = Simulation(
        config,
        [*build_history_calls(), *(dict(call) for call in LIVE_CALLS)],
    )
    for _ in range(3600):
        _apply_plan(simulation)
        simulation.advance(1)
    return simulation


def _live_waits(simulation):
    return {
        passenger.call_id: passenger.wait_seconds
        for passenger in simulation.passenger_snapshots()
        if passenger.call_id.startswith("live-")
    }


def _run_flow():
    forecast_simulation = _simulation_at_prediction_time()
    control_simulation = _simulation_at_prediction_time()

    observation = forecast_simulation.observe()
    assert observation["time_seconds"] == 3600
    assert observation["metrics"]["completed_calls"] == 50
    assert not any(
        passenger["call_id"].startswith("live-")
        for passenger in observation["passengers"]
    )

    features = build_simulation_features(
        observation,
        complete_since_seconds=0,
        coverage_evidence="Complete deterministic synthetic simulation history",
    )
    forecasts = [predict(row, model="rolling-mean-12") for row in features]
    first_horizon = {
        forecast["zone_id"]: forecast["predictions"][0]["predicted_demand"]
        for forecast in forecasts
    }
    assert len(first_horizon) == 9
    assert all(demand > 0 for demand in first_horizon.values())
    assert first_horizon["zone-2-2"] == pytest.approx(20 / 12)
    assert first_horizon["zone-2-2"] > max(
        demand for zone, demand in first_horizon.items() if zone != "zone-2-2"
    )

    forecast_plan = _apply_plan(forecast_simulation, forecasts)
    assert forecast_plan["policy"] == "nearest-idle+forecast-surplus-reposition"
    assert forecast_plan["commands"] == [
        {"type": "reposition", "taxi_id": "taxi-1", "destination": [2, 2]},
        {"type": "reposition", "taxi_id": "taxi-2", "destination": [2, 2]},
    ]

    forecast_simulation.advance(20)
    control_simulation.advance(20)
    forecast_dispatch = _apply_plan(forecast_simulation)
    control_dispatch = _apply_plan(control_simulation)
    forecast_pickup_distance = sum(
        decision["pickup_distance_m"] for decision in forecast_dispatch["decisions"]
    )
    control_pickup_distance = sum(
        decision["pickup_distance_m"] for decision in control_dispatch["decisions"]
    )
    assert forecast_pickup_distance == pytest.approx(60)
    assert control_pickup_distance == pytest.approx(220)

    forecast_simulation.advance(100)
    control_simulation.advance(100)
    forecast_waits = _live_waits(forecast_simulation)
    control_waits = _live_waits(control_simulation)
    assert sum(forecast_waits.values()) < sum(control_waits.values())

    final = forecast_simulation.observe()
    assert final["metrics"]["completed_calls"] == 53
    assert final["metrics"]["pending_calls"] == 0
    assert final["metrics"]["rejected_commands"] == 0
    for measured in final["metrics"]["by_taxi"].values():
        assert sum(
            measured[field]
            for field in (
                "idle_seconds",
                "pickup_seconds",
                "occupied_seconds",
                "reposition_seconds",
            )
        ) == pytest.approx(final["time_seconds"])

    return {
        "forecast_plan": forecast_plan,
        "forecast_pickup_distance": forecast_pickup_distance,
        "control_pickup_distance": control_pickup_distance,
        "forecast_waits": forecast_waits,
        "control_waits": control_waits,
        "events": forecast_simulation.events(),
    }


def test_public_modules_use_history_to_improve_hidden_future_pickups():
    assert _run_flow() == _run_flow()
