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


def build_simulation_features(observation, *, complete_since_seconds, coverage_evidence):
    """Adapt a complete synthetic Module 1 observation to online feature rows.

    The caller must attest that the cumulative observation includes every call
    since complete_since_seconds. Never use this adapter for external real data.
    """
    if not isinstance(coverage_evidence, str) or not coverage_evidence.strip():
        raise ValueError("coverage_evidence: complete simulation history evidence is required")
    start = complete_since_seconds
    if type(start) is not int or start < 0 or start % 300:
        raise ValueError("complete_since_seconds: expected a non-negative 300-second boundary")
    if not isinstance(observation, dict) or observation.get("schema_version") != "0.1":
        raise ValueError("observation: expected Module 1 contract 0.1")
    now = observation.get("time_seconds")
    if type(now) not in (int, float) or not math.isfinite(now) or now < 3600 or now % 300:
        raise ValueError("observation.time_seconds: expected a 300-second boundary >= 3600")
    if start > now - 3600:
        raise ValueError("coverage: complete simulation history must span the previous 60 minutes")
    passengers = observation.get("passengers")
    if not isinstance(passengers, list):
        raise ValueError("observation.passengers: expected cumulative passenger history")
    fields = ("call_id", "requested_at_seconds", "origin", "destination")
    calls = []
    for passenger in passengers:
        if not isinstance(passenger, dict) or any(key not in passenger for key in fields):
            raise ValueError("observation.passengers: missing required call fields")
        calls.append({key: passenger[key] for key in fields})
    t = int(now)
    coverage = [dict(interval_start_seconds=at, zone_id=zone, is_complete="true")
                for at in range(t - 3600, t, 300) for zone in ZONES]
    return build_inference_features(calls, coverage, prediction_time_seconds=t,
                                    source_kind="synthetic")
