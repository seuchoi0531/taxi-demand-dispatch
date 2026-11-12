"""Online history boundaries, completeness, and offline feature parity."""

from copy import deepcopy

import pytest

from module2_preprocessing import build_inference_features
from tests.module2.test_dataset import inputs, build


def online(calls, coverage, t=3600):
    return build_inference_features(calls, coverage,
                                    prediction_time_seconds=t, source_kind="synthetic")


def fixture():
    scenario, coverage = inputs(12)
    return scenario["calls"], coverage


def test_matches_offline_features_without_targets_and_does_not_mutate():
    scenario, coverage = inputs()
    expected = [{k: v for k, v in row.items() if not k.startswith("target_")}
                for row in build(scenario, coverage)["splits"]["train"]
                if row["prediction_time_seconds"] == 3600]
    calls, history_coverage = fixture()
    original = deepcopy((calls, history_coverage))
    assert online(calls, history_coverage) == expected
    assert online(calls, history_coverage) == expected
    assert (calls, history_coverage) == original


def test_time_boundary_and_old_history():
    calls, coverage = fixture()
    # At a later prediction time, old calls are validated but not aggregated.
    for call in calls:
        call["requested_at_seconds"] += 300
    for row in coverage:
        row["interval_start_seconds"] += 300
    expected = online(calls, coverage, 3900)
    calls.extend([
        dict(call_id="old", requested_at_seconds=0, origin=[0, 0], destination=[1, 1]),
        dict(call_id="now", requested_at_seconds=3900, origin=[0, 0], destination=[1, 1]),
    ])
    assert online(calls, coverage, 3900) == expected
    calls[-1]["requested_at_seconds"] = 3900.001
    with pytest.raises(ValueError, match="future"):
        online(calls, coverage, 3900)


def test_completed_empty_cells_are_zero_and_fractional_times_are_valid():
    _, coverage = fixture()
    rows = online([], coverage)
    assert len(rows) == 9
    assert all(value == 0 for row in rows for key, value in row.items()
               if key.startswith(("lag_", "rolling_mean_")))
    calls = [dict(call_id="fractional", requested_at_seconds=3599.98765,
                  origin=[3, 3], destination=[0, 0])]
    assert online(calls, coverage)[-1]["lag_1"] == 1


@pytest.mark.parametrize("defect", ["missing", "false", "duplicate", "outside", "columns"])
def test_invalid_coverage_rejected(defect):
    calls, coverage = fixture()
    if defect == "missing":
        coverage.pop()
    elif defect == "false":
        coverage[-1]["is_complete"] = "false"
    elif defect == "duplicate":
        coverage.append(dict(coverage[0]))
    elif defect == "outside":
        coverage[-1]["interval_start_seconds"] = 3600
    else:
        coverage[-1]["extra"] = True
    with pytest.raises(ValueError, match="coverage"):
        online(calls, coverage)


@pytest.mark.parametrize("t", [True, 3599, 3601, 3600.0, float("nan")])
def test_invalid_prediction_time(t):
    with pytest.raises(ValueError, match="prediction_time_seconds"):
        online(*fixture(), t)


@pytest.mark.parametrize("field,value", [
    ("call_id", ""), ("requested_at_seconds", -1),
    ("requested_at_seconds", float("inf")), ("requested_at_seconds", True),
    ("origin", [4, 0]), ("destination", [True, 1]),
])
def test_invalid_observed_calls(field, value):
    calls, coverage = fixture()
    calls[0][field] = value
    with pytest.raises(ValueError):
        online(calls, coverage)


def test_duplicate_ids_and_invalid_source_rejected():
    calls, coverage = fixture()
    calls.append(dict(calls[0]))
    with pytest.raises(ValueError, match="duplicate"):
        online(calls, coverage)
    with pytest.raises(ValueError, match="source_kind"):
        build_inference_features([], coverage, prediction_time_seconds=3600,
                                 source_kind="unknown")
