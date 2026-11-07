"""Consumer contract runs once Module 3 is available, or against a pinned file."""

import importlib.util
import os

import pytest

from module2_preprocessing import build_inference_features
from tests.module2.test_inference import fixture


def test_nine_online_rows_consumed_directly_by_module3():
    path = os.environ.get("MODULE3_CONTRACT_BASELINE")
    if path:
        spec = importlib.util.spec_from_file_location("module3_contract_baseline", path)
        consumer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(consumer)
        predict = consumer.predict
    else:
        import module3_prediction
        if not hasattr(module3_prediction, "predict"):
            pytest.skip("Module 3 is absent; set MODULE3_CONTRACT_BASELINE to its pinned baseline.py")
        predict = module3_prediction.predict
    rows = build_inference_features(*fixture(), prediction_time_seconds=3600,
                                    source_kind="synthetic")
    for model in ("rolling-mean-12", "recent-trend"):
        forecasts = [predict(row, model=model) for row in rows]
        assert [f["zone_id"] for f in forecasts] == [r["zone_id"] for r in rows]
        assert len(forecasts) == 9
        assert all(f["prediction_time_seconds"] == 3600 for f in forecasts)
        assert all(len(f["predictions"]) == 6 for f in forecasts)
