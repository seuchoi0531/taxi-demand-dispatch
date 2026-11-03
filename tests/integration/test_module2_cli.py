"""Configured generation, replay, and accidental overwrite protection."""

import json
import subprocess
import sys

from module1_simulation import Simulation, load_calls, load_config


def test_generate_and_replay_cli(tmp_path):
    output = tmp_path / "nested" / "calls.json"
    command = [sys.executable, "-m", "module2_preprocessing", "--config",
               "configs/module2_scenario.toml", "--output", str(output)]
    created = subprocess.run(command, capture_output=True, text=True)
    assert created.returncode == 0, created.stderr
    original = output.read_bytes()
    assert len(json.loads(original)["calls"]) == 60
    simulation = Simulation(load_config("configs/module1_demo.toml"), load_calls(output))
    simulation.advance(1200)
    assert len(simulation.observe()["passengers"]) == 7
    rejected = subprocess.run(command, capture_output=True, text=True)
    assert rejected.returncode != 0
    assert output.read_bytes() == original


def test_dataset_cli_uses_explicit_coverage_and_provenance(tmp_path):
    import csv
    from module2_preprocessing import generate_scenario
    from module2_preprocessing.dataset import ZONES

    calls = tmp_path / "calls.json"
    calls.write_text(json.dumps(generate_scenario(seed=3, call_count=300, start_seconds=0,
                                                 interval_seconds=100, tick_seconds=0.05)), encoding="utf-8")
    coverage = tmp_path / "coverage.csv"
    with coverage.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["interval_start_seconds", "zone_id", "is_complete"])
        writer.writerows((t, z, "true") for t in range(0, 30000, 300) for z in ZONES)
    output = tmp_path / "dataset"
    command = [sys.executable, "-m", "module2_preprocessing", "dataset", "--calls", str(calls),
               "--coverage", str(coverage), "--start-seconds", "0", "--end-seconds", "30000",
               "--tick-seconds", "0.05", "--source-kind", "synthetic", "--coverage-evidence",
               "Fixture generated every scheduled call in the bounded interval.", "--output", str(output)]
    completed = subprocess.run(command, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    report = json.loads((output / "report.json").read_text())
    assert report["source_kind"] == "synthetic"
    assert report["incomplete_cells"] == 0
    for split in ("train", "validation", "test"):
        with (output / f"{split}.csv").open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        assert len(rows) == report["rows"][split] > 0
        assert {r["source_kind"] for r in rows} == {"synthetic"}
