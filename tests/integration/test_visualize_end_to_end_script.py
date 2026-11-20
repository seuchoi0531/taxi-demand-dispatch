"""The repeatable integration visualization script also works headlessly."""

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def test_visualization_script_prepares_and_completes_reposition():
    completed = subprocess.run(
        [sys.executable, "scripts/visualize_end_to_end.py", "--headless"],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
    )
    result = json.loads(completed.stdout)

    assert result["plan"]["commands"] == [
        {"type": "reposition", "taxi_id": "taxi-1", "destination": [2, 2]},
        {"type": "reposition", "taxi_id": "taxi-2", "destination": [2, 2]},
    ]
    assert len(result["forecast_h1"]) == 9
    assert all(demand > 0 for demand in result["forecast_h1"].values())
    assert result["forecast_h1"]["zone-2-2"] == max(result["forecast_h1"].values())
    assert [call["call_id"] for call in result["visual_calls"]] == [
        "live-01-hot",
        "live-02-hot",
        "live-03-local",
        "live-04-queue",
        "live-05-queue",
    ]
    assert [call["requested_at_seconds"] for call in result["visual_calls"]] == [
        3620, 3620, 3620, 3623, 3623,
    ]
    assert all(call["state"] == "completed" for call in result["visual_calls"])
    assert result["final"]["metrics"]["completed_calls"] == 55
    assert [event["event"] for event in result["reposition_events"]] == [
        "reposition_started",
        "reposition_started",
        "reposition_completed",
        "reposition_completed",
    ]
