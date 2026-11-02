"""Meaningful demand, coverage, chronology and leakage regressions."""

import copy
import csv

import pytest

from module2_preprocessing import aggregate_calls, build_dataset, write_coverage_template, write_dataset
from module2_preprocessing.dataset import ZONES


def inputs(n=100):
    # Interval i has exactly i calls in zone-0-0, with tick-aligned times.
    calls = [dict(call_id=f"{i}-{j}", requested_at_seconds=i*300,
                  origin=[0, 0], destination=[3, 3]) for i in range(n) for j in range(i)]
    coverage = [dict(interval_start_seconds=i*300, zone_id=z, is_complete="true")
                for i in range(n) for z in ZONES]
    return dict(schema_version="0.1", calls=calls), coverage


def build(scenario, coverage, n=100):
    return build_dataset(scenario, coverage, start_seconds=0, end_seconds=n*300,
                         tick_seconds=0.05, source_kind="synthetic",
                         coverage_evidence="Test fixture exhaustively generates each interval.")


def test_lags_rolling_targets_and_boundary_purge():
    result = build(*inputs())
    row = result["splits"]["train"][0]
    assert row["prediction_time_seconds"] == 3600
    assert [row[f"lag_{k}"] for k in (1, 2, 3, 6, 12)] == [11, 10, 9, 6, 0]
    assert [row[f"rolling_mean_{k}"] for k in (3, 6, 12)] == [10, 8.5, 5.5]
    assert [row[f"target_{k}"] for k in range(1, 7)] == list(range(12, 18))
    assert result["report"]["split_boundaries_seconds"] == [21000, 25500]
    for name, lower, upper in (("train", 0, 21000), ("validation", 21000, 25500), ("test", 25500, 30000)):
        rows = result["splits"][name]
        assert rows
        assert all(lower <= r["prediction_time_seconds"] and r["prediction_time_seconds"] + 1800 <= upper for r in rows)
    assert max(r["prediction_time_seconds"] for r in result["splits"]["train"]) == 19200
    assert min(r["prediction_time_seconds"] for r in result["splits"]["validation"]) == 21000


def test_future_call_changes_targets_but_not_features():
    scenario, coverage = inputs()
    before = build(scenario, coverage)["splits"]["train"][0]
    scenario["calls"].append(dict(call_id="future", requested_at_seconds=3600,
                                   origin=[0, 0], destination=[1, 1]))
    after = build(scenario, coverage)["splits"]["train"][0]
    assert after["target_1"] == before["target_1"] + 1
    for name in before:
        if not name.startswith("target_"):
            assert before[name] == after[name]


def test_zero_and_missing_coverage_remain_distinct():
    scenario, coverage = inputs()
    coverage = [r for r in coverage if not (r["interval_start_seconds"] == 3600 and r["zone_id"] == "zone-0-0")]
    result = build(scenario, coverage)
    cells = {(r["interval_start_seconds"], r["zone_id"]): r for r in result["aggregates"]}
    assert cells[3600, "zone-0-0"]["demand"] is None
    assert cells[3600, "zone-1-1"]["demand"] == 0
    assert not any(r["zone_id"] == "zone-0-0" and r["prediction_time_seconds"] == 3600
                   for rows in result["splits"].values() for r in rows)
    assert any(r["zone_id"] == "zone-1-1" and r["prediction_time_seconds"] == 3600
               for r in result["splits"]["train"])
    assert result["report"]["excluded"]["missing_coverage"] > 0


def test_template_never_assumes_collection_completion(tmp_path):
    path = tmp_path / "coverage.csv"
    write_coverage_template(path, start_seconds=0, end_seconds=600)
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 18
    assert {r["is_complete"] for r in rows} == {"false"}


@pytest.mark.parametrize("defect", ["duplicate", "unknown_zone", "invalid_status", "unaligned", "outside"])
def test_bad_coverage_is_rejected(defect):
    scenario, coverage = inputs(20)
    if defect == "duplicate":
        coverage.append(copy.copy(coverage[0]))
    elif defect == "unknown_zone":
        coverage[0]["zone_id"] = "zone-3-3"
    elif defect == "invalid_status":
        coverage[0]["is_complete"] = "yes"
    elif defect == "unaligned":
        coverage[0]["interval_start_seconds"] = 1
    else:
        coverage[0]["interval_start_seconds"] = 6000
    with pytest.raises(ValueError):
        build(scenario, coverage, 20)


@pytest.mark.parametrize("field,value", [("call_id", ""), ("origin", [4, 0]),
                                         ("destination", [True, 0]),
                                         ("requested_at_seconds", 0.01),
                                         ("requested_at_seconds", float("nan"))])
def test_bad_calls_are_rejected(field, value):
    scenario, coverage = inputs(20)
    scenario["calls"][0][field] = value
    with pytest.raises(ValueError):
        build(scenario, coverage, 20)


def test_output_preserves_provenance_and_null_cells(tmp_path):
    scenario, coverage = inputs(20)
    coverage[0]["is_complete"] = "false"
    result = build(scenario, coverage, 20)
    path = tmp_path / "dataset"
    write_dataset(result, path)
    with (path / "aggregates.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["demand"] == ""
    assert rows[1]["demand"] == "0"
    assert result["report"]["source_kind"] == "synthetic"
    with pytest.raises(FileExistsError):
        write_dataset(result, path)


def test_no_coverage_means_no_training_rows():
    scenario, _ = inputs()
    result = build(scenario, [])
    assert all(not rows for rows in result["splits"].values())
    assert result["report"]["incomplete_cells"] == 900


def test_short_constant_sample_reports_limitations():
    from module2_preprocessing import generate_scenario
    scenario = generate_scenario(seed=42, call_count=60, start_seconds=0,
                                 interval_seconds=10, tick_seconds=0.05)
    _, coverage = inputs(2)
    result = build(scenario, coverage, 2)
    assert any("identical" in w for w in result["report"]["warnings"])
    assert any("shorter" in w for w in result["report"]["warnings"])


def test_source_and_evidence_are_explicit():
    scenario, coverage = inputs(20)
    for source, evidence in (("unknown", "log"), ("real", "")):
        with pytest.raises(ValueError):
            build_dataset(scenario, coverage, start_seconds=0, end_seconds=6000,
                          tick_seconds=0.05, source_kind=source, coverage_evidence=evidence)
