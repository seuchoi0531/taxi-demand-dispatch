"""Coverage-aware offline demand datasets using only Python's standard library."""

import csv
import json
import math
from pathlib import Path

ZONES = tuple(f"zone-{x}-{y}" for x in range(3) for y in range(3))
LAGS = (1, 2, 3, 6, 12)
WINDOWS = (3, 6, 12)
COLUMNS = ("prediction_time_seconds", "zone_id", "source_kind",
           *(f"lag_{k}" for k in LAGS), *(f"rolling_mean_{k}" for k in WINDOWS),
           *(f"target_{k}" for k in range(1, 7)))
COVERAGE_COLUMNS = ("interval_start_seconds", "zone_id", "is_complete")


def _bounds(start, end):
    if any(type(v) is not int or v < 0 or v % 300 for v in (start, end)) or end <= start:
        raise ValueError("observation bounds: expected increasing non-negative integer multiples of 300")


def _node(value, name):
    if (not isinstance(value, (list, tuple)) or len(value) != 2
            or any(type(v) is not int or not 0 <= v <= 3 for v in value)):
        raise ValueError(f"{name}: expected intersection coordinates 0..3")


def _csv(path, columns, rows):
    with Path(path).open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def write_coverage_template(path, *, start_seconds, end_seconds):
    """Create an explicitly unconfirmed coverage grid, never infer completeness."""
    _bounds(start_seconds, end_seconds)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _csv(path, COVERAGE_COLUMNS, (
        dict(interval_start_seconds=t, zone_id=z, is_complete="false")
        for t in range(start_seconds, end_seconds, 300) for z in ZONES))


def aggregate_calls(scenario, coverage, *, start_seconds, end_seconds, tick_seconds):
    """Return all time/zone cells; unknown coverage is None rather than zero."""
    _bounds(start_seconds, end_seconds)
    if (type(tick_seconds) not in (int, float) or not math.isfinite(tick_seconds)
            or tick_seconds <= 0):
        raise ValueError("tick_seconds: expected a finite positive number")
    if (not isinstance(scenario, dict) or set(scenario) != {"schema_version", "calls"}
            or scenario["schema_version"] != "0.1" or not isinstance(scenario["calls"], list)):
        raise ValueError("scenario: expected existing Module 1 JSON contract 0.1")
    complete = {}
    for row in coverage:
        if not isinstance(row, dict) or set(row) != set(COVERAGE_COLUMNS):
            raise ValueError("coverage: invalid columns")
        raw = row["interval_start_seconds"]
        if type(raw) is int:
            t = raw
        elif isinstance(raw, str) and raw.isascii() and raw.isdecimal():
            t = int(raw)
        else:
            raise ValueError("coverage: invalid interval start")
        z, status = row["zone_id"], row["is_complete"]
        if t % 300 or not start_seconds <= t < end_seconds or z not in ZONES:
            raise ValueError("coverage: invalid interval or zone")
        if status not in ("true", "false"):
            raise ValueError("coverage: is_complete must be 'true' or 'false'")
        if (t, z) in complete:
            raise ValueError(f"coverage: duplicate cell {(t, z)}")
        complete[t, z] = status == "true"
    counts = {}
    ids = set()
    for call in scenario["calls"]:
        if not isinstance(call, dict) or set(call) != {"call_id", "requested_at_seconds", "origin", "destination"}:
            raise ValueError("call: invalid fields")
        ident = call["call_id"]
        if not isinstance(ident, str) or not ident.strip() or ident in ids:
            raise ValueError(f"call: invalid or duplicate call_id {ident!r}")
        ids.add(ident)
        _node(call["origin"], f"{ident}.origin")
        _node(call["destination"], f"{ident}.destination")
        t = call["requested_at_seconds"]
        if type(t) not in (int, float) or not math.isfinite(t) or not start_seconds <= t < end_seconds:
            raise ValueError(f"{ident}: time outside observation bounds or invalid")
        ratio = t / tick_seconds
        if not math.isfinite(ratio) or not math.isclose(round(ratio) * tick_seconds, t, rel_tol=0, abs_tol=1e-9):
            raise ValueError(f"{ident}: time must be tick aligned")
        x, y = call["origin"]
        key = (int(t // 300) * 300, f"zone-{min(x, 2)}-{min(y, 2)}")
        counts[key] = counts.get(key, 0) + 1
    return [dict(interval_start_seconds=t, zone_id=z,
                 is_complete=complete.get((t, z), False),
                 demand=counts.get((t, z), 0) if complete.get((t, z), False) else None)
            for t in range(start_seconds, end_seconds, 300) for z in ZONES]


def build_dataset(scenario, coverage, *, start_seconds, end_seconds, tick_seconds,
                  source_kind, coverage_evidence):
    """Build split rows with no future inputs and no cross-boundary targets."""
    if source_kind not in ("real", "synthetic"):
        raise ValueError("source_kind: explicitly choose real or synthetic")
    if not isinstance(coverage_evidence, str) or not coverage_evidence.strip():
        raise ValueError("coverage_evidence: collection/generation evidence is required")
    aggregates = aggregate_calls(scenario, coverage, start_seconds=start_seconds,
                                 end_seconds=end_seconds, tick_seconds=tick_seconds)
    n = (end_seconds - start_seconds) // 300
    b1, b2 = start_seconds + (n * 70 // 100) * 300, start_seconds + (n * 85 // 100) * 300
    grid = {(r["interval_start_seconds"], r["zone_id"]): r["demand"] for r in aggregates}
    splits = {"train": [], "validation": [], "test": []}
    excluded = dict(insufficient_history=0, target_crosses_boundary=0, missing_coverage=0)
    for t in range(start_seconds, end_seconds, 300):
        split, end = ("train", b1) if t < b1 else (("validation", b2) if t < b2 else ("test", end_seconds))
        for z in ZONES:
            if t - 3600 < start_seconds:
                excluded["insufficient_history"] += 1
                continue
            if t + 1800 > end:
                excluded["target_crosses_boundary"] += 1
                continue
            history = [grid[t - k * 300, z] for k in range(1, 13)]
            targets = [grid[t + k * 300, z] for k in range(6)]
            if any(v is None for v in history + targets):
                excluded["missing_coverage"] += 1
                continue
            row = dict(prediction_time_seconds=t, zone_id=z, source_kind=source_kind)
            row.update({f"lag_{k}": history[k-1] for k in LAGS})
            row.update({f"rolling_mean_{k}": sum(history[:k]) / k for k in WINDOWS})
            row.update({f"target_{k+1}": v for k, v in enumerate(targets)})
            splits[split].append(row)
    totals = [sum(grid[t, z] for z in ZONES) for t in range(start_seconds, end_seconds, 300)
              if all(grid[t, z] is not None for z in ZONES)]
    warnings = []
    if source_kind == "synthetic":
        warnings.append("Synthetic data: results do not establish real-world predictive performance.")
    if len(totals) >= 2 and len(set(totals)) == 1:
        warnings.append("All fully observed 5-minute city totals are identical; training variability is limited.")
    if n < 18:
        warnings.append("Observation span is shorter than 60-minute history plus 30-minute targets.")
    for name, rows in splits.items():
        if not rows:
            warnings.append(f"{name}: no usable training rows.")
    return dict(aggregates=aggregates, splits=splits, report=dict(
        schema_version="module2-training-1.0", source_kind=source_kind,
        coverage_evidence=coverage_evidence, start_seconds=start_seconds, end_seconds=end_seconds,
        tick_seconds=tick_seconds, interval_seconds=300, history_intervals=12, target_intervals=6,
        split_boundaries_seconds=[b1, b2], rows={k: len(v) for k, v in splits.items()},
        excluded=excluded, incomplete_cells=sum(r["demand"] is None for r in aggregates),
        warnings=warnings))


def write_dataset(dataset, output_dir):
    """Write a new dataset directory; never overwrite an existing result."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    for name, rows in dataset["splits"].items():
        _csv(output / f"{name}.csv", COLUMNS, rows)
    aggregate_rows = [dict(r, is_complete=str(r["is_complete"]).lower()) for r in dataset["aggregates"]]
    _csv(output / "coverage.csv", COVERAGE_COLUMNS,
         ({key: row[key] for key in COVERAGE_COLUMNS} for row in aggregate_rows))
    _csv(output / "aggregates.csv", (*COVERAGE_COLUMNS, "demand"), aggregate_rows)
    with (output / "report.json").open("x", encoding="utf-8") as stream:
        json.dump(dataset["report"], stream, indent=2, allow_nan=False)
        stream.write("\n")


def dataset_main(argv):
    """Separate dataset command, preserving the original scenario CLI."""
    import argparse
    parser = argparse.ArgumentParser(description="Coverage-aware 5-minute demand datasets")
    parser.add_argument("--start-seconds", type=int, required=True)
    parser.add_argument("--end-seconds", type=int, required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--coverage-template", action="store_true")
    parser.add_argument("--calls")
    parser.add_argument("--coverage")
    parser.add_argument("--tick-seconds", type=float)
    parser.add_argument("--source-kind", choices=("real", "synthetic"))
    parser.add_argument("--coverage-evidence")
    args = parser.parse_args(argv)
    try:
        if args.coverage_template:
            write_coverage_template(args.output, start_seconds=args.start_seconds, end_seconds=args.end_seconds)
        else:
            if any(v is None for v in (args.calls, args.coverage, args.tick_seconds, args.source_kind, args.coverage_evidence)):
                parser.error("dataset requires --calls, --coverage, --tick-seconds, --source-kind, --coverage-evidence")
            with Path(args.calls).open(encoding="utf-8") as stream:
                scenario = json.load(stream)
            with Path(args.coverage).open(newline="", encoding="utf-8") as stream:
                reader = csv.DictReader(stream)
                if reader.fieldnames != list(COVERAGE_COLUMNS):
                    raise ValueError("coverage: expected ordered columns " + ",".join(COVERAGE_COLUMNS))
                coverage = list(reader)
            dataset = build_dataset(scenario, coverage, start_seconds=args.start_seconds,
                                    end_seconds=args.end_seconds, tick_seconds=args.tick_seconds,
                                    source_kind=args.source_kind, coverage_evidence=args.coverage_evidence)
            write_dataset(dataset, args.output)
            print(json.dumps(dataset["report"], indent=2))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
