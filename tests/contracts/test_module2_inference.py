"""Online rows must be consumed directly by the integrated Module 3 API."""

from module2_preprocessing import build_inference_features
from module3_prediction import predict
from tests.module2.test_inference import fixture


def test_nine_online_rows_consumed_directly_by_module3():
    rows = build_inference_features(*fixture(), prediction_time_seconds=3600,
                                    source_kind="synthetic")
    for model in ("rolling-mean-12", "recent-trend"):
        forecasts = [predict(row, model=model) for row in rows]
        assert [f["zone_id"] for f in forecasts] == [r["zone_id"] for r in rows]
        assert len(forecasts) == 9
        assert all(f["prediction_time_seconds"] == 3600 for f in forecasts)
        assert all(len(f["predictions"]) == 6 for f in forecasts)
