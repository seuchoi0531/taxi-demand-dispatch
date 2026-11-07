"""Online features from observed history, without targets or file access."""

import math

from .dataset import LAGS, WINDOWS, ZONES, _node, _aggregate_calls


def build_inference_features(observed_calls, coverage, *, prediction_time_seconds,
                             source_kind):
    """Return nine complete rows using only [t-3600, t).

    Validate all observed calls, including older history and calls at t. Future
    calls are errors even when they would fall outside the feature window.
    """
    t = prediction_time_seconds
    if type(t) is not int or t < 3600 or t % 300:
        raise ValueError("prediction_time_seconds: expected a 300-second boundary >= 3600")
    if source_kind not in ("real", "synthetic"):
        raise ValueError("source_kind: explicitly choose real or synthetic")
    if not isinstance(observed_calls, list):
        raise ValueError("observed_calls: expected a call array")
    calls, ids = [], set()
    for call in observed_calls:
        if not isinstance(call, dict) or set(call) != {
            "call_id", "requested_at_seconds", "origin", "destination"
        }:
            raise ValueError("call: invalid fields")
        ident = call["call_id"]
        if not isinstance(ident, str) or not ident.strip() or ident in ids:
            raise ValueError(f"call: invalid or duplicate call_id {ident!r}")
        ids.add(ident)
        _node(call["origin"], f"{ident}.origin")
        _node(call["destination"], f"{ident}.destination")
        at = call["requested_at_seconds"]
        if type(at) not in (int, float) or not math.isfinite(at) or at < 0:
            raise ValueError(f"{ident}: expected a finite non-negative call time")
        if at > t:
            raise ValueError(f"{ident}: future calls are not observable")
        if t - 3600 <= at < t:
            calls.append(call)
    cells = _aggregate_calls(dict(schema_version="0.1", calls=calls), coverage,
                             start_seconds=t - 3600, end_seconds=t)
    for cell in cells:
        if not cell["is_complete"]:
            raise ValueError(f"coverage: incomplete cell "
                             f"{(cell['interval_start_seconds'], cell['zone_id'])}")
    grid = {(cell["interval_start_seconds"], cell["zone_id"]): cell["demand"]
            for cell in cells}
    rows = []
    for zone in ZONES:
        history = [grid[t - k * 300, zone] for k in range(1, 13)]
        row = dict(prediction_time_seconds=t, zone_id=zone, source_kind=source_kind)
        row.update({f"lag_{k}": history[k - 1] for k in LAGS})
        row.update({f"rolling_mean_{k}": sum(history[:k]) / k for k in WINDOWS})
        rows.append(row)
    return rows
