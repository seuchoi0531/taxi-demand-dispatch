"""Executable checks for the temporary Module 3 forecast boundary."""

import json
import math
import re
from pathlib import Path

from module3_prediction import predict


def test_forecast_matches_schema_and_time_semantics():
    schema = json.loads(
        Path("docs/contracts/module3_forecast.schema.json").read_text(encoding="utf-8")
    )
    features = {
        "prediction_time_seconds": 7200,
        "zone_id": "zone-2-1",
        "source_kind": "real",
        "lag_1": 0,
        "lag_2": 1,
        "lag_3": 2,
        "lag_6": 3,
        "lag_12": 4,
        "rolling_mean_3": 1.0,
        "rolling_mean_6": 1.5,
        "rolling_mean_12": 2.25,
    }
    forecast = predict(features)
    assert set(forecast) == set(schema["required"]) == set(schema["properties"])
    assert forecast["schema_version"] == schema["properties"]["schema_version"]["const"]
    assert re.fullmatch(schema["properties"]["zone_id"]["pattern"], forecast["zone_id"])
    assert forecast["interval_seconds"] == 300
    predictions = forecast["predictions"]
    assert len(predictions) == 6
    item_schema = schema["properties"]["predictions"]["items"]
    for horizon, item in enumerate(predictions, start=1):
        assert set(item) == set(item_schema["required"]) == set(item_schema["properties"])
        assert item["horizon"] == horizon
        assert item["interval_start_seconds"] == 7200 + (horizon - 1) * 300
        assert math.isfinite(item["predicted_demand"]) and item["predicted_demand"] >= 0
