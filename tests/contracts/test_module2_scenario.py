"""The producer writes the exact existing Module 1 input contract."""

import json

from module1_simulation import Simulation, load_calls, load_config
from module2_preprocessing import generate_scenario


def test_generated_json_is_accepted_and_future_calls_are_hidden(tmp_path):
    config = load_config("configs/module1_demo.toml")
    scenario = generate_scenario(seed=42, call_count=3, start_seconds=0,
                                 interval_seconds=1, tick_seconds=config.tick_seconds)
    path = tmp_path / "calls.json"
    path.write_text(json.dumps(scenario), encoding="utf-8")
    sim = Simulation(config, load_calls(path))
    assert [p["call_id"] for p in sim.observe()["passengers"]] == ["call-1"]
    sim.advance(20)
    assert [p["call_id"] for p in sim.observe()["passengers"]] == ["call-1", "call-2"]
    assert all(event["call_id"] != "call-3" for event in sim.events())


def test_training_row_schema_and_module1_zone_compatibility():
    import re
    from pathlib import Path
    from module2_preprocessing import build_dataset
    from module2_preprocessing.dataset import COLUMNS, ZONES

    schema = json.loads(Path("docs/contracts/module2_training_row.schema.json").read_text(encoding="utf-8"))
    assert set(schema["required"]) == set(COLUMNS) == set(schema["properties"])
    assert schema["additionalProperties"] is False
    config = load_config("configs/module1_demo.toml")
    for x in range(4):
        for y in range(4):
            call = dict(call_id="edge", requested_at_seconds=0, origin=[x, y], destination=[0, 0])
            sim = Simulation(config, [call])
            sim.dispatch("taxi-1", "edge")
            sim.advance(2400)
            taxi = next(t for t in sim.observe()["taxis"] if t["taxi_id"] == "taxi-1")
            assert taxi["zone_id"] == "zone-0-0"
            # Observe a taxi at the origin immediately after pickup with a zero-length trip.
            call["destination"] = [x, y]
            sim = Simulation(config, [call])
            sim.dispatch("taxi-1", "edge")
            sim.advance(2400)
            expected = next(t["zone_id"] for t in sim.observe()["taxis"] if t["taxi_id"] == "taxi-1")
            coverage = [dict(interval_start_seconds=i*300, zone_id=z, is_complete="true")
                        for i in range(100) for z in ZONES]
            result = build_dataset(dict(schema_version="0.1", calls=[call]), coverage,
                                   start_seconds=0, end_seconds=30000, tick_seconds=0.05,
                                   source_kind="synthetic", coverage_evidence="bounded fixture")
            nonzero = [r for r in result["aggregates"] if r["demand"]]
            assert len(nonzero) == 1 and nonzero[0]["zone_id"] == expected
    for rows in result["splits"].values():
        for row in rows:
            assert set(row) == set(schema["required"])
            for key, value in row.items():
                rule = schema["properties"][key]
                if "enum" in rule:
                    assert value in rule["enum"]
                elif rule["type"] == "string":
                    assert re.fullmatch(rule["pattern"], value)
                else:
                    assert type(value) in ((int,) if rule["type"] == "integer" else (int, float))
                    assert value >= rule["minimum"]
                    if "multipleOf" in rule:
                        assert value % rule["multipleOf"] == 0
