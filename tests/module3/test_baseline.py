"""Baseline forecasts, strict inputs, and leakage-safe evaluation diagnostics."""

import csv
import math

import pytest

from module3_prediction import (
    build_html_report,
    evaluate,
    load_rows,
    predict,
    write_html_report,
)
from module3_prediction.baseline import (
    RECENT_TREND_MODEL,
    ROLLING_MEAN_MODEL,
    TRAINING_COLUMNS,
)


def training_row(**changes):
    row = {
        "prediction_time_seconds": 3600,
        "zone_id": "zone-0-0",
        "source_kind": "synthetic",
        "lag_1": 1,
        "lag_2": 2,
        "lag_3": 3,
        "lag_6": 2,
        "lag_12": 1,
        "rolling_mean_3": 2.0,
        "rolling_mean_6": 2.0,
        "rolling_mean_12": 2.0,
        "target_1": 1,
        "target_2": 2,
        "target_3": 3,
        "target_4": 4,
        "target_5": 5,
        "target_6": 6,
    }
    row.update(changes)
    return row


def features(row=None):
    row = training_row() if row is None else row
    return {name: value for name, value in row.items() if not name.startswith("target_")}


def test_predict_repeats_prior_hour_mean_for_exact_six_intervals():
    result = predict(features(), model=ROLLING_MEAN_MODEL)
    assert result["schema_version"] == "module3-forecast-0.1"
    assert result["prediction_time_seconds"] == 3600
    assert result["zone_id"] == "zone-0-0"
    assert [item["horizon"] for item in result["predictions"]] == list(range(1, 7))
    assert [item["interval_start_seconds"] for item in result["predictions"]] == [
        3600,
        3900,
        4200,
        4500,
        4800,
        5100,
    ]
    assert {item["predicted_demand"] for item in result["predictions"]} == {2.0}


def test_evaluate_reports_overall_and_each_horizon_mae():
    result = evaluate([training_row()], model=ROLLING_MEAN_MODEL)
    assert result["rows"] == 1
    assert result["predictions"] == 6
    assert result["overall_mae"] == pytest.approx(11 / 6)
    assert [item["mae"] for item in result["by_horizon"]] == [1, 0, 1, 2, 3, 4]
    assert result["source_kinds"] == ["synthetic"]
    assert result["warnings"]


def test_recent_trend_uses_only_past_lags_and_clips_negative_demand():
    rising = predict(features(training_row(lag_1=4, lag_6=0)), model=RECENT_TREND_MODEL)
    assert [item["predicted_demand"] for item in rising["predictions"]] == pytest.approx(
        [4.4, 4.8, 5.2, 5.6, 6.0, 6.4]
    )
    falling = predict(features(training_row(lag_1=0, lag_6=5)), model=RECENT_TREND_MODEL)
    assert [item["predicted_demand"] for item in falling["predictions"]] == [0] * 6


def test_unknown_model_is_rejected():
    with pytest.raises(ValueError, match="model"):
        predict(features(), model="unknown")


@pytest.mark.parametrize(
    "change",
    [
        {"prediction_time_seconds": 1},
        {"prediction_time_seconds": True},
        {"zone_id": "zone-3-0"},
        {"source_kind": "unknown"},
        {"lag_1": -1},
        {"rolling_mean_12": math.inf},
    ],
)
def test_predict_rejects_invalid_or_ambiguous_features(change):
    with pytest.raises(ValueError):
        predict(features(training_row(**change)))


def test_predict_rejects_targets_and_evaluate_rejects_empty_rows():
    with pytest.raises(ValueError):
        predict(training_row())
    with pytest.raises(ValueError):
        evaluate([])


def test_load_rows_parses_contract_csv_and_requires_unique_order(tmp_path):
    path = tmp_path / "validation.csv"
    rows = [training_row(), training_row(zone_id="zone-0-1")]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=TRAINING_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    loaded = load_rows(path)
    assert loaded == rows

    duplicate = tmp_path / "duplicate.csv"
    with duplicate.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=TRAINING_COLUMNS)
        writer.writeheader()
        writer.writerows([rows[0], rows[0]])
    with pytest.raises(ValueError, match="uniquely ordered"):
        load_rows(duplicate)


def test_load_rows_rejects_column_reordering(tmp_path):
    path = tmp_path / "wrong.csv"
    columns = list(reversed(TRAINING_COLUMNS))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerow(training_row())
    with pytest.raises(ValueError, match="ordered columns"):
        load_rows(path)


def test_html_report_contains_charts_heatmaps_and_accessible_labels():
    rows = [
        training_row(zone_id=f"zone-{x}-{y}", target_1=x + y)
        for y in range(3)
        for x in range(3)
    ]
    document = build_html_report(rows)
    assert document.startswith("<!doctype html>")
    assert "실제 수요와 예측 수요" in document
    assert "예측 구간별 오차" in document
    assert "최근 추세 보정 모델" in document
    assert "baseline 대비 개선" in document
    assert document.count("class=\"heat-cell\"") == 27
    assert "role=\"img\"" in document
    assert "Synthetic data" in document
    assert "전체 평균" in document and "시점별 값" in document
    assert "data-time-select" in document and "data-horizon-select" in document
    assert '"details"' in document
    assert '"scales":{"average"' in document
    assert "fetch(" not in document


def test_html_report_uses_next_number_without_overwriting(tmp_path):
    rows = [training_row()]
    requested = tmp_path / "report.html"
    first = write_html_report(rows, requested)
    second = write_html_report(rows, requested)
    third = write_html_report(rows, requested)
    assert first == requested
    assert second == tmp_path / "report_2.html"
    assert third == tmp_path / "report_3.html"
    assert requested.read_text(encoding="utf-8") == first.read_text(encoding="utf-8")

    numbered = write_html_report(rows, tmp_path / "report_3.html")
    assert numbered == tmp_path / "report_4.html"
