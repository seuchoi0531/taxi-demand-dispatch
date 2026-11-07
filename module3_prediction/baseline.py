"""Leakage-safe rolling-mean demand baseline using only the standard library."""

import csv
import json
import math
from collections.abc import Iterable, Mapping
from pathlib import Path

INTERVAL_SECONDS = 300
HORIZONS = 6
ROLLING_MEAN_MODEL = "rolling-mean-12"
RECENT_TREND_MODEL = "recent-trend"
MODELS = (ROLLING_MEAN_MODEL, RECENT_TREND_MODEL)
DEFAULT_MODEL = RECENT_TREND_MODEL
ZONES = tuple(f"zone-{x}-{y}" for x in range(3) for y in range(3))
LAG_COLUMNS = ("lag_1", "lag_2", "lag_3", "lag_6", "lag_12")
ROLLING_COLUMNS = ("rolling_mean_3", "rolling_mean_6", "rolling_mean_12")
TARGET_COLUMNS = tuple(f"target_{horizon}" for horizon in range(1, HORIZONS + 1))
FEATURE_COLUMNS = (
    "prediction_time_seconds",
    "zone_id",
    "source_kind",
    *LAG_COLUMNS,
    *ROLLING_COLUMNS,
)
TRAINING_COLUMNS = (*FEATURE_COLUMNS, *TARGET_COLUMNS)


def _non_negative_integer(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(f"{name}: expected a non-negative integer")
    return value


def _non_negative_number(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name}: expected a finite non-negative number")
    return value


def _validate_features(row):
    if not isinstance(row, Mapping) or set(row) != set(FEATURE_COLUMNS):
        raise ValueError("features: expected exactly the Module 3 feature fields")
    prediction_time = _non_negative_integer(
        row["prediction_time_seconds"], "prediction_time_seconds"
    )
    if prediction_time % INTERVAL_SECONDS:
        raise ValueError("prediction_time_seconds: expected a 300-second boundary")
    if row["zone_id"] not in ZONES:
        raise ValueError("zone_id: expected zone-0-0 through zone-2-2")
    if row["source_kind"] not in ("real", "synthetic"):
        raise ValueError("source_kind: expected real or synthetic")
    for name in LAG_COLUMNS:
        _non_negative_integer(row[name], name)
    for name in ROLLING_COLUMNS:
        _non_negative_number(row[name], name)


def _validate_training_row(row):
    if not isinstance(row, Mapping) or set(row) != set(TRAINING_COLUMNS):
        raise ValueError("training row: expected exactly the Module 2 training fields")
    _validate_features({name: row[name] for name in FEATURE_COLUMNS})
    for name in TARGET_COLUMNS:
        _non_negative_integer(row[name], name)


def predict(features, *, model=DEFAULT_MODEL):
    """Forecast six 5-minute intervals with an explicit supported model."""
    _validate_features(features)
    if model not in MODELS:
        raise ValueError(f"model: expected one of {', '.join(MODELS)}")
    prediction_time = features["prediction_time_seconds"]
    if model == ROLLING_MEAN_MODEL:
        demands = [float(features["rolling_mean_12"])] * HORIZONS
    else:
        level = float(features["lag_1"])
        trend_per_interval = (float(features["lag_1"]) - float(features["lag_6"])) / 5
        demands = [
            max(0.0, level + 0.5 * trend_per_interval * horizon)
            for horizon in range(1, HORIZONS + 1)
        ]
    return {
        "schema_version": "module3-forecast-0.1",
        "model": model,
        "prediction_time_seconds": prediction_time,
        "zone_id": features["zone_id"],
        "interval_seconds": INTERVAL_SECONDS,
        "predictions": [
            {
                "horizon": horizon,
                "interval_start_seconds": prediction_time
                + (horizon - 1) * INTERVAL_SECONDS,
                "predicted_demand": demands[horizon - 1],
            }
            for horizon in range(1, HORIZONS + 1)
        ],
    }


def evaluate(rows: Iterable[Mapping], *, model=DEFAULT_MODEL):
    """Return transparent MAE diagnostics without fitting or tuning on the rows."""
    rows = list(rows)
    if not rows:
        raise ValueError("evaluation: at least one complete row is required")
    absolute_errors = [0.0] * HORIZONS
    source_kinds = set()
    for row in rows:
        _validate_training_row(row)
        source_kinds.add(row["source_kind"])
        forecast = predict({name: row[name] for name in FEATURE_COLUMNS}, model=model)
        for index, item in enumerate(forecast["predictions"]):
            absolute_errors[index] += abs(
                item["predicted_demand"] - row[TARGET_COLUMNS[index]]
            )
    by_horizon = [
        {"horizon": index + 1, "mae": error / len(rows)}
        for index, error in enumerate(absolute_errors)
    ]
    warnings = []
    if "synthetic" in source_kinds:
        warnings.append(
            "Synthetic data: MAE does not establish real-world predictive performance."
        )
    return {
        "schema_version": "module3-evaluation-0.1",
        "model": model,
        "metric": "mean_absolute_error",
        "rows": len(rows),
        "predictions": len(rows) * HORIZONS,
        "source_kinds": sorted(source_kinds),
        "overall_mae": sum(absolute_errors) / (len(rows) * HORIZONS),
        "by_horizon": by_horizon,
        "warnings": warnings,
    }


def _csv_integer(value, name):
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
        raise ValueError(f"{name}: expected a non-negative integer in CSV")
    return int(value)


def _csv_number(value, name):
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name}: expected a number in CSV") from exc
    return _non_negative_number(parsed, name)


def load_rows(path):
    """Load and strictly validate an ordered Module 2 training CSV."""
    with Path(path).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != list(TRAINING_COLUMNS):
            raise ValueError(
                "training CSV: expected ordered columns " + ",".join(TRAINING_COLUMNS)
            )
        rows = []
        previous_key = None
        for line_number, raw in enumerate(reader, start=2):
            if None in raw or set(raw) != set(TRAINING_COLUMNS):
                raise ValueError(f"training CSV line {line_number}: invalid columns")
            row = {
                "prediction_time_seconds": _csv_integer(
                    raw["prediction_time_seconds"], "prediction_time_seconds"
                ),
                "zone_id": raw["zone_id"],
                "source_kind": raw["source_kind"],
            }
            row.update({name: _csv_integer(raw[name], name) for name in LAG_COLUMNS})
            row.update({name: _csv_number(raw[name], name) for name in ROLLING_COLUMNS})
            row.update({name: _csv_integer(raw[name], name) for name in TARGET_COLUMNS})
            _validate_training_row(row)
            key = (row["prediction_time_seconds"], row["zone_id"])
            if previous_key is not None and key <= previous_key:
                raise ValueError(
                    f"training CSV line {line_number}: rows must be uniquely ordered by time and zone"
                )
            previous_key = key
            rows.append(row)
    return rows


def write_json(value, path):
    """Write a new JSON result without silently replacing prior results."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
