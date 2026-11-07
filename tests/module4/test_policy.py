from copy import deepcopy

import pytest

from module4_dispatch import build_plan


BLOCK_SIZE_M = 20.0


def taxi(taxi_id, node, *, state="idle", call_id=None):
    x, y = node
    return {
        "taxi_id": taxi_id,
        "x_m": x * BLOCK_SIZE_M,
        "y_m": y * BLOCK_SIZE_M,
        "heading_degrees": 0.0,
        "distance_m": 0.0,
        "state": state,
        "call_id": call_id,
        "zone_id": f"zone-{min(x, 2)}-{min(y, 2)}",
    }


def passenger(call_id, origin, requested_at, *, state="waiting", taxi_id=None):
    return {
        "call_id": call_id,
        "origin": list(origin),
        "destination": [3, 3],
        "requested_at_seconds": requested_at,
        "state": state,
        "taxi_id": taxi_id,
        "assigned_at_seconds": None,
        "picked_up_at_seconds": None,
        "completed_at_seconds": None,
        "x_m": origin[0] * BLOCK_SIZE_M,
        "y_m": origin[1] * BLOCK_SIZE_M,
        "wait_seconds": 300 - requested_at,
    }


def observation(*, taxis, passengers=(), time_seconds=300):
    return {
        "schema_version": "0.1",
        "tick": 300,
        "time_seconds": time_seconds,
        "taxis": list(taxis),
        "passengers": list(passengers),
        "metrics": {},
    }


def forecasts(demands=None, *, prediction_time=300, model="recent-trend"):
    demands = demands or {}
    result = []
    for x in range(3):
        for y in range(3):
            zone_id = f"zone-{x}-{y}"
            demand = demands.get(zone_id, 0.0)
            result.append({
                "schema_version": "module3-forecast-0.1",
                "model": model,
                "prediction_time_seconds": prediction_time,
                "zone_id": zone_id,
                "interval_seconds": 300,
                "predictions": [
                    {
                        "horizon": horizon,
                        "interval_start_seconds": prediction_time + (horizon - 1) * 300,
                        "predicted_demand": demand,
                    }
                    for horizon in range(1, 7)
                ],
            })
    return result


def test_dispatches_oldest_call_to_nearest_idle_taxi_with_stable_ties():
    state = observation(
        taxis=[taxi("taxi-b", (0, 0)), taxi("taxi-a", (2, 0)), taxi("taxi-busy", (1, 1), state="occupied", call_id="call-x")],
        passengers=[passenger("call-new", (0, 0), 200), passenger("call-old", (1, 0), 100)],
    )

    plan = build_plan(state, block_size_m=BLOCK_SIZE_M)

    assert plan["policy"] == "nearest-idle"
    assert plan["commands"] == [
        {"type": "dispatch", "taxi_id": "taxi-a", "call_id": "call-old"},
        {"type": "dispatch", "taxi_id": "taxi-b", "call_id": "call-new"},
    ]
    assert plan["decisions"][0]["pickup_distance_m"] == 20.0
    assert plan["decisions"][0]["wait_seconds"] == 200


def test_forecast_repositions_only_idle_taxis_left_after_dispatch():
    state = observation(
        taxis=[taxi("taxi-a", (0, 0)), taxi("taxi-b", (0, 0)), taxi("taxi-c", (0, 0))],
        passengers=[passenger("call-1", (0, 0), 100)],
    )

    plan = build_plan(
        state,
        block_size_m=BLOCK_SIZE_M,
        forecasts=forecasts({"zone-2-2": 2.0}),
    )

    assert plan["policy"] == "nearest-idle+forecast-surplus-reposition"
    assert plan["commands"] == [
        {"type": "dispatch", "taxi_id": "taxi-a", "call_id": "call-1"},
        {"type": "reposition", "taxi_id": "taxi-b", "destination": [2, 2]},
        {"type": "reposition", "taxi_id": "taxi-c", "destination": [2, 2]},
    ]
    assert all(item["taxi_id"] != "taxi-a" for item in plan["commands"][1:])
    assert plan["decisions"][1]["target_zone_id"] == "zone-2-2"


def test_forecast_keeps_supply_required_in_its_current_zone():
    state = observation(taxis=[taxi("taxi-a", (0, 0)), taxi("taxi-b", (2, 2))])
    plan = build_plan(
        state,
        block_size_m=BLOCK_SIZE_M,
        forecasts=forecasts({"zone-0-0": 1.0, "zone-2-2": 1.0}),
    )
    assert plan["commands"] == []
    assert plan["decisions"] == []


def test_rejects_incomplete_or_misaligned_forecasts():
    state = observation(taxis=[taxi("taxi-a", (0, 0))])
    with pytest.raises(ValueError, match="exactly one forecast"):
        build_plan(state, block_size_m=BLOCK_SIZE_M, forecasts=forecasts()[:-1])
    with pytest.raises(ValueError, match="prediction time"):
        build_plan(state, block_size_m=BLOCK_SIZE_M, forecasts=forecasts(prediction_time=600))


def test_rejects_future_calls_and_inconsistent_zones_without_mutating_input():
    state = observation(taxis=[taxi("taxi-a", (0, 0))], passengers=[passenger("call-1", (0, 0), 100)])
    original = deepcopy(state)
    build_plan(state, block_size_m=BLOCK_SIZE_M)
    assert state == original

    future = deepcopy(state)
    future["passengers"][0]["requested_at_seconds"] = 301
    with pytest.raises(ValueError, match="future calls"):
        build_plan(future, block_size_m=BLOCK_SIZE_M)

    wrong_zone = deepcopy(state)
    wrong_zone["taxis"][0]["zone_id"] = "zone-2-2"
    with pytest.raises(ValueError, match="zone_id"):
        build_plan(wrong_zone, block_size_m=BLOCK_SIZE_M)
