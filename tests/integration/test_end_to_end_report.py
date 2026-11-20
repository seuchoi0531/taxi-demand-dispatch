"""The integration evaluator reports experiment results without completion gates."""

import pytest

from scripts.evaluate_end_to_end import evaluate_scenario, write_html_report


def test_evaluation_report_exposes_policy_results_without_completion_gates(tmp_path):
    result = evaluate_scenario()

    assert "verdict" not in result
    assert "checks" not in result
    assert result["history"]["call_count"] == 50
    assert set(result["history"]["calls_by_zone"]) == set(result["forecast_h1"])
    assert result["forecast_policy"]["pickup_distance_m"] == pytest.approx(260)
    assert result["control_policy"]["pickup_distance_m"] == pytest.approx(420)
    assert (
        result["forecast_policy"]["mean_live_wait_seconds"]
        < result["control_policy"]["mean_live_wait_seconds"]
    )
    # In this fixture, repositioning moves the same empty travel earlier rather
    # than reducing total empty distance. The report must preserve this tradeoff.
    assert result["forecast_policy"]["empty_distance_m"] == pytest.approx(
        result["control_policy"]["empty_distance_m"]
    )

    first = write_html_report(result, tmp_path / "integration.html")
    second = write_html_report(result, tmp_path / "integration.html")
    assert first.name == "integration.html"
    assert second.name == "integration_2.html"
    document = first.read_text(encoding="utf-8")
    assert "Module 1–4 정책 비교 실험" in document
    assert "통합 완료 판정이나 실제 데이터의 모델 일반화 성능을 의미하지 않습니다" in document
    assert "통합 완료 판정 조건" not in document
    assert ">PASS<" not in document
    assert "원본 평가 JSON" in document
