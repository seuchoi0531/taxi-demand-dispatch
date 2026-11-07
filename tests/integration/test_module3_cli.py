"""Module 2 CSV consumption and Module 3 result overwrite protection."""

import json
import subprocess
import sys

from module2_preprocessing import build_dataset, write_dataset
from module2_preprocessing.dataset import ZONES


def test_evaluate_cli_reads_module2_shape_and_preserves_prior_result(tmp_path):
    calls = [
        {
            "call_id": f"call-{interval}-{index}",
            "requested_at_seconds": interval * 300,
            "origin": [0, 0],
            "destination": [3, 3],
        }
        for interval in range(100)
        for index in range(interval % 5)
    ]
    coverage = [
        {"interval_start_seconds": interval * 300, "zone_id": zone, "is_complete": "true"}
        for interval in range(100)
        for zone in ZONES
    ]
    dataset = build_dataset(
        {"schema_version": "0.1", "calls": calls},
        coverage,
        start_seconds=0,
        end_seconds=30000,
        tick_seconds=0.05,
        source_kind="synthetic",
        coverage_evidence="Bounded integration fixture generated every interval.",
    )
    dataset_path = tmp_path / "module2-dataset"
    write_dataset(dataset, dataset_path)
    source = dataset_path / "validation.csv"
    output = tmp_path / "results" / "evaluation.json"
    command = [
        sys.executable,
        "-m",
        "module3_prediction",
        "evaluate",
        "--input",
        str(source),
        "--output",
        str(output),
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["rows"] == dataset["report"]["rows"]["validation"] > 0
    assert report["overall_mae"] >= 0
    original = output.read_bytes()
    rejected = subprocess.run(command, capture_output=True, text=True)
    assert rejected.returncode != 0
    assert output.read_bytes() == original

    report_output = tmp_path / "results" / "evaluation.html"
    report_command = [
        sys.executable,
        "-m",
        "module3_prediction",
        "report",
        "--input",
        str(source),
        "--output",
        str(report_output),
    ]
    report_completed = subprocess.run(report_command, capture_output=True, text=True)
    assert report_completed.returncode == 0, report_completed.stderr
    document = report_output.read_text(encoding="utf-8")
    assert "Module 3 수요 예측 평가" in document
    assert "<svg" in document and "class=\"heat-grid\"" in document
    assert "전체 평균" in document and "시점별 값" in document
    original_report = report_output.read_bytes()
    report_numbered = subprocess.run(report_command, capture_output=True, text=True)
    assert report_numbered.returncode == 0, report_numbered.stderr
    assert report_output.read_bytes() == original_report
    assert (report_output.parent / "evaluation_2.html").is_file()
    assert "evaluation_2.html" in report_numbered.stdout
