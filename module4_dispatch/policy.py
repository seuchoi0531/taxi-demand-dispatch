"""Pure Module 4 policy logic over public observation and forecast contracts."""

from collections.abc import Mapping, Sequence
import math


ZONES = tuple(f"zone-{x}-{y}" for x in range(3) for y in range(3))
FORECAST_MODELS = ("rolling-mean-12", "recent-trend")
TAXI_STATES = ("idle", "to_pickup", "occupied", "repositioning")
PASSENGER_STATES = ("waiting", "assigned", "onboard", "completed")


def _number(value, name, *, positive=False):
    valid = type(value) in (int, float) and math.isfinite(value)
    if not valid or (value <= 0 if positive else value < 0):
        bound = "positive" if positive else "non-negative"
        raise ValueError(f"{name}: expected a finite {bound} number")
    return value


def _finite_number(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name}: expected a finite number")
    return value


def _identifier(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name}: expected a non-empty string")
    return value


def _exact_fields(value, expected, name):
    if not isinstance(value, Mapping) or set(value) != set(expected):
        raise ValueError(f"{name}: expected exactly these fields: {sorted(expected)}")


def _node(value, name):
    if (not isinstance(value, (list, tuple)) or len(value) != 2
            or any(type(part) is not int or not 0 <= part <= 3 for part in value)):
        raise ValueError(f"{name}: expected an intersection [x,y] with integers 0..3")
    return tuple(value)


def _zone_at(x_m, y_m, block_size_m):
    extent = 3 * block_size_m
    if not 0 <= x_m <= extent or not 0 <= y_m <= extent:
        raise ValueError("taxi position: expected coordinates inside the city")
    x = min(int(x_m / block_size_m), 2)
    y = min(int(y_m / block_size_m), 2)
    return f"zone-{x}-{y}"


def _validate_observation(observation, block_size_m):
    _number(block_size_m, "block_size_m", positive=True)
    _exact_fields(
        observation,
        {"schema_version", "tick", "time_seconds", "taxis", "passengers", "metrics"},
        "observation",
    )
    if observation["schema_version"] != "0.1":
        raise ValueError("observation.schema_version: expected 0.1")
    if type(observation["tick"]) is not int or observation["tick"] < 0:
        raise ValueError("observation.tick: expected a non-negative integer")
    now = _number(observation["time_seconds"], "observation.time_seconds")
    if not isinstance(observation["taxis"], list):
        raise ValueError("observation.taxis: expected a list")
    if not isinstance(observation["passengers"], list):
        raise ValueError("observation.passengers: expected a list")
    if not isinstance(observation["metrics"], Mapping):
        raise ValueError("observation.metrics: expected an object")

    taxis = []
    taxi_ids = set()
    taxi_fields = {
        "taxi_id", "x_m", "y_m", "heading_degrees", "distance_m", "state",
        "call_id", "zone_id",
    }
    for index, taxi in enumerate(observation["taxis"]):
        name = f"observation.taxis[{index}]"
        _exact_fields(taxi, taxi_fields, name)
        taxi_id = _identifier(taxi["taxi_id"], f"{name}.taxi_id")
        if taxi_id in taxi_ids:
            raise ValueError(f"{name}.taxi_id: duplicate {taxi_id}")
        taxi_ids.add(taxi_id)
        x_m = _number(taxi["x_m"], f"{name}.x_m")
        y_m = _number(taxi["y_m"], f"{name}.y_m")
        _finite_number(taxi["heading_degrees"], f"{name}.heading_degrees")
        _number(taxi["distance_m"], f"{name}.distance_m")
        if taxi["state"] not in TAXI_STATES:
            raise ValueError(f"{name}.state: unsupported taxi state")
        if taxi["call_id"] is not None:
            _identifier(taxi["call_id"], f"{name}.call_id")
        expected_zone = _zone_at(x_m, y_m, block_size_m)
        if taxi["zone_id"] != expected_zone:
            raise ValueError(f"{name}.zone_id: expected {expected_zone}")
        taxis.append(dict(taxi))

    passengers = []
    call_ids = set()
    passenger_fields = {
        "call_id", "origin", "destination", "requested_at_seconds", "state",
        "taxi_id", "assigned_at_seconds", "picked_up_at_seconds",
        "completed_at_seconds", "x_m", "y_m", "wait_seconds",
    }
    for index, passenger in enumerate(observation["passengers"]):
        name = f"observation.passengers[{index}]"
        _exact_fields(passenger, passenger_fields, name)
        call_id = _identifier(passenger["call_id"], f"{name}.call_id")
        if call_id in call_ids:
            raise ValueError(f"{name}.call_id: duplicate {call_id}")
        call_ids.add(call_id)
        _node(passenger["origin"], f"{name}.origin")
        _node(passenger["destination"], f"{name}.destination")
        requested = _number(passenger["requested_at_seconds"], f"{name}.requested_at_seconds")
        if requested > now:
            raise ValueError(f"{name}.requested_at_seconds: future calls are not observable")
        if passenger["state"] not in PASSENGER_STATES:
            raise ValueError(f"{name}.state: unsupported passenger state")
        if passenger["taxi_id"] is not None:
            _identifier(passenger["taxi_id"], f"{name}.taxi_id")
        for field in ("assigned_at_seconds", "picked_up_at_seconds", "completed_at_seconds"):
            if passenger[field] is not None:
                _number(passenger[field], f"{name}.{field}")
        _number(passenger["x_m"], f"{name}.x_m")
        _number(passenger["y_m"], f"{name}.y_m")
        _number(passenger["wait_seconds"], f"{name}.wait_seconds")
        passengers.append(dict(passenger))
    return now, taxis, passengers


def _validate_forecasts(forecasts, now):
    if not isinstance(forecasts, Sequence) or isinstance(forecasts, (str, bytes)):
        raise ValueError("forecasts: expected a sequence")
    if len(forecasts) != len(ZONES):
        raise ValueError("forecasts: expected exactly one forecast for each of 9 zones")
    demands = {}
    model = None
    forecast_fields = {
        "schema_version", "model", "prediction_time_seconds", "zone_id",
        "interval_seconds", "predictions",
    }
    prediction_fields = {"horizon", "interval_start_seconds", "predicted_demand"}
    for index, forecast in enumerate(forecasts):
        name = f"forecasts[{index}]"
        _exact_fields(forecast, forecast_fields, name)
        if forecast["schema_version"] != "module3-forecast-0.1":
            raise ValueError(f"{name}.schema_version: expected module3-forecast-0.1")
        if forecast["model"] not in FORECAST_MODELS:
            raise ValueError(f"{name}.model: unsupported forecast model")
        model = forecast["model"] if model is None else model
        if forecast["model"] != model:
            raise ValueError("forecasts: all zones must use the same model")
        prediction_time = forecast["prediction_time_seconds"]
        if type(prediction_time) is not int or prediction_time < 0 or prediction_time % 300:
            raise ValueError(f"{name}.prediction_time_seconds: expected a 300-second boundary")
        if not math.isclose(prediction_time, now, rel_tol=0, abs_tol=1e-9):
            raise ValueError("forecasts: prediction time must match observation time")
        zone_id = forecast["zone_id"]
        if zone_id not in ZONES or zone_id in demands:
            raise ValueError(f"{name}.zone_id: expected one unique known zone")
        if forecast["interval_seconds"] != 300:
            raise ValueError(f"{name}.interval_seconds: expected 300")
        predictions = forecast["predictions"]
        if not isinstance(predictions, list) or len(predictions) != 6:
            raise ValueError(f"{name}.predictions: expected six horizons")
        for offset, prediction in enumerate(predictions):
            item_name = f"{name}.predictions[{offset}]"
            _exact_fields(prediction, prediction_fields, item_name)
            horizon = offset + 1
            if prediction["horizon"] != horizon:
                raise ValueError(f"{item_name}.horizon: expected {horizon}")
            if prediction["interval_start_seconds"] != prediction_time + offset * 300:
                raise ValueError(f"{item_name}.interval_start_seconds: invalid horizon time")
            _number(prediction["predicted_demand"], f"{item_name}.predicted_demand")
        demands[zone_id] = float(predictions[0]["predicted_demand"])
    if set(demands) != set(ZONES):
        raise ValueError("forecasts: expected all zones exactly once")
    return model, demands


def _road_distance(x_m, y_m, destination, block_size_m):
    target_x, target_y = (part * block_size_m for part in destination)
    return abs(x_m - target_x) + abs(y_m - target_y)


def _dispatch(now, taxis, passengers, block_size_m):
    available = {taxi["taxi_id"]: taxi for taxi in taxis if taxi["state"] == "idle"}
    waiting = sorted(
        (passenger for passenger in passengers if passenger["state"] == "waiting"),
        key=lambda passenger: (passenger["requested_at_seconds"], passenger["call_id"]),
    )
    commands = []
    decisions = []
    for passenger in waiting:
        if not available:
            break
        taxi = min(
            available.values(),
            key=lambda item: (
                _road_distance(item["x_m"], item["y_m"], passenger["origin"], block_size_m),
                item["taxi_id"],
            ),
        )
        distance = _road_distance(taxi["x_m"], taxi["y_m"], passenger["origin"], block_size_m)
        commands.append({"type": "dispatch", "taxi_id": taxi["taxi_id"], "call_id": passenger["call_id"]})
        decisions.append({
            "type": "dispatch",
            "taxi_id": taxi["taxi_id"],
            "call_id": passenger["call_id"],
            "wait_seconds": now - passenger["requested_at_seconds"],
            "pickup_distance_m": distance,
        })
        del available[taxi["taxi_id"]]
    return commands, decisions, set(available)


def _zone_anchor(zone_id):
    _, x, y = zone_id.split("-")
    return [int(x), int(y)]


def _reposition(taxis, available_ids, demands, block_size_m):
    available = {taxi["taxi_id"]: taxi for taxi in taxis if taxi["taxi_id"] in available_ids}
    by_zone = {zone_id: [] for zone_id in ZONES}
    for taxi in available.values():
        by_zone[taxi["zone_id"]].append(taxi)
    for zone_taxis in by_zone.values():
        zone_taxis.sort(key=lambda taxi: taxi["taxi_id"])

    required = {zone: math.ceil(demands[zone]) for zone in ZONES}
    surplus = {zone: max(0, len(by_zone[zone]) - required[zone]) for zone in ZONES}
    deficit = {zone: max(0, required[zone] - len(by_zone[zone])) for zone in ZONES}
    candidates = dict(available)
    commands = []
    decisions = []
    while any(surplus.values()) and any(deficit.values()):
        target_zone = min(
            (zone for zone in ZONES if deficit[zone] > 0),
            key=lambda zone: (-deficit[zone], -demands[zone], zone),
        )
        destination = _zone_anchor(target_zone)
        taxi = min(
            (
                taxi for taxi in candidates.values()
                if surplus[taxi["zone_id"]] > 0 and taxi["zone_id"] != target_zone
            ),
            key=lambda item: (
                _road_distance(item["x_m"], item["y_m"], destination, block_size_m),
                item["taxi_id"],
            ),
            default=None,
        )
        if taxi is None:
            break
        source_zone = taxi["zone_id"]
        distance = _road_distance(taxi["x_m"], taxi["y_m"], destination, block_size_m)
        commands.append({"type": "reposition", "taxi_id": taxi["taxi_id"], "destination": destination})
        decisions.append({
            "type": "reposition",
            "taxi_id": taxi["taxi_id"],
            "source_zone_id": source_zone,
            "target_zone_id": target_zone,
            "destination": destination,
            "forecast_demand": demands[target_zone],
            "target_deficit_before": deficit[target_zone],
            "reposition_distance_m": distance,
        })
        surplus[source_zone] -= 1
        deficit[target_zone] -= 1
        del candidates[taxi["taxi_id"]]
    return commands, decisions


def build_plan(observation, *, block_size_m, forecasts=None):
    """Return deterministic commands and auditable reasons without mutating inputs.

    Dispatch always uses released calls only. Repositioning is added only when a
    complete nine-zone Module 3 forecast set is explicitly supplied.
    """
    now, taxis, passengers = _validate_observation(observation, block_size_m)
    commands, decisions, available_ids = _dispatch(now, taxis, passengers, block_size_m)
    policy = "nearest-idle"
    if forecasts is not None:
        _, demands = _validate_forecasts(forecasts, now)
        reposition_commands, reposition_decisions = _reposition(
            taxis, available_ids, demands, block_size_m
        )
        commands.extend(reposition_commands)
        decisions.extend(reposition_decisions)
        policy = "nearest-idle+forecast-surplus-reposition"
    return {
        "schema_version": "module4-plan-0.1",
        "policy": policy,
        "time_seconds": now,
        "commands": commands,
        "decisions": decisions,
    }
