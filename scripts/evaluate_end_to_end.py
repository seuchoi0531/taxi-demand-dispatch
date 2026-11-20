"""Evaluate the public Module 1-4 flow and write a self-contained HTML report."""

import argparse
from collections import Counter
from html import escape
import json
from pathlib import Path

from module1_simulation import Simulation, load_config
from module2_preprocessing import build_simulation_features
from module3_prediction import predict
from module4_dispatch import build_plan
from scripts.visualize_end_to_end import (
    HISTORY_INTERVALS,
    HISTORY_INTERVAL_SECONDS,
    LIVE_START_SECONDS,
    MODELS,
    VISUAL_CALLS,
    build_history_calls,
)


EVALUATION_END_SECONDS = LIVE_START_SECONDS + 200


def _apply_plan(simulation, *, forecasts=None):
    plan = build_plan(
        simulation.observe(),
        block_size_m=simulation.config.block_size_m,
        forecasts=forecasts,
    )
    for command in plan["commands"]:
        simulation.apply_command(command)
    return plan


def _new_simulation():
    calls = [*build_history_calls(), *(dict(call) for call in VISUAL_CALLS)]
    return Simulation(load_config("configs/module1_demo.toml"), calls)


def _advance_history(simulation):
    ticks_per_second = round(1 / simulation.config.tick_seconds)
    for _ in range(LIVE_START_SECONDS):
        _apply_plan(simulation)
        simulation.advance(ticks_per_second)


def _run_live(simulation):
    decisions = []
    ticks = round(
        (EVALUATION_END_SECONDS - LIVE_START_SECONDS)
        / simulation.config.tick_seconds
    )
    for _ in range(ticks):
        plan = _apply_plan(simulation)
        decisions.extend(plan["decisions"])
        simulation.advance(1)
    return decisions


def _zone_for_origin(origin):
    return f"zone-{min(origin[0], 2)}-{min(origin[1], 2)}"


def _fleet_metric(metrics, field):
    return sum(taxi[field] for taxi in metrics["by_taxi"].values())


def _policy_result(simulation, before_metrics, decisions):
    observation = simulation.observe()
    metrics = observation["metrics"]
    live = [
        passenger for passenger in observation["passengers"]
        if passenger["call_id"].startswith("live-")
    ]
    pickup_distance = sum(
        decision["pickup_distance_m"] for decision in decisions
        if decision["type"] == "dispatch"
        and decision["call_id"].startswith("live-")
    )
    return {
        "completed_live_calls": sum(passenger["state"] == "completed" for passenger in live),
        "pending_live_calls": sum(passenger["state"] != "completed" for passenger in live),
        "mean_live_wait_seconds": sum(passenger["wait_seconds"] for passenger in live) / len(live),
        "total_live_wait_seconds": sum(passenger["wait_seconds"] for passenger in live),
        "pickup_distance_m": pickup_distance,
        "fleet_distance_m": _fleet_metric(metrics, "distance_m")
        - _fleet_metric(before_metrics, "distance_m"),
        "empty_distance_m": _fleet_metric(metrics, "empty_distance_m")
        - _fleet_metric(before_metrics, "empty_distance_m"),
        "idle_seconds": _fleet_metric(metrics, "idle_seconds")
        - _fleet_metric(before_metrics, "idle_seconds"),
        "pickup_seconds": _fleet_metric(metrics, "pickup_seconds")
        - _fleet_metric(before_metrics, "pickup_seconds"),
        "occupied_seconds": _fleet_metric(metrics, "occupied_seconds")
        - _fleet_metric(before_metrics, "occupied_seconds"),
        "reposition_seconds": _fleet_metric(metrics, "reposition_seconds")
        - _fleet_metric(before_metrics, "reposition_seconds"),
        "rejected_commands": metrics["rejected_commands"]
        - before_metrics["rejected_commands"],
    }


def evaluate_scenario(model="rolling-mean-12"):
    """Run forecast and control policies over the same hidden future scenario."""
    if model not in MODELS:
        raise ValueError(f"model: expected one of {', '.join(MODELS)}")
    forecast_simulation = _new_simulation()
    control_simulation = _new_simulation()
    _advance_history(forecast_simulation)
    _advance_history(control_simulation)

    forecast_observation = forecast_simulation.observe()
    control_observation = control_simulation.observe()
    before_forecast_metrics = forecast_observation["metrics"]
    before_control_metrics = control_observation["metrics"]

    features = build_simulation_features(
        forecast_observation,
        complete_since_seconds=0,
        coverage_evidence="Complete deterministic synthetic simulation history",
    )
    forecasts = [predict(row, model=model) for row in features]
    forecast_h1 = {
        forecast["zone_id"]: forecast["predictions"][0]["predicted_demand"]
        for forecast in forecasts
    }
    actual_h1 = Counter(
        _zone_for_origin(call["origin"])
        for call in VISUAL_CALLS
        if LIVE_START_SECONDS <= call["requested_at_seconds"] < LIVE_START_SECONDS + 300
    )
    forecast_mae = sum(
        abs(forecast_h1[zone] - actual_h1.get(zone, 0))
        for zone in sorted(forecast_h1)
    ) / len(forecast_h1)

    reposition_plan = _apply_plan(forecast_simulation, forecasts=forecasts)
    forecast_decisions = _run_live(forecast_simulation)
    control_decisions = _run_live(control_simulation)
    forecast_result = _policy_result(
        forecast_simulation, before_forecast_metrics, forecast_decisions
    )
    control_result = _policy_result(
        control_simulation, before_control_metrics, control_decisions
    )

    history_counts = Counter(
        _zone_for_origin(call["origin"]) for call in build_history_calls()
    )
    return {
        "schema_version": "end-to-end-evaluation-0.1",
        "scope": "Single synthetic scenario policy comparison",
        "model": model,
        "prediction_time_seconds": LIVE_START_SECONDS,
        "evaluation_end_seconds": EVALUATION_END_SECONDS,
        "history": {
            "interval_seconds": HISTORY_INTERVAL_SECONDS,
            "interval_count": HISTORY_INTERVALS,
            "call_count": len(build_history_calls()),
            "calls_by_zone": dict(sorted(history_counts.items())),
        },
        "forecast_h1": forecast_h1,
        "actual_h1": {
            zone: actual_h1.get(zone, 0) for zone in sorted(forecast_h1)
        },
        "forecast_h1_mae": forecast_mae,
        "reposition_plan": reposition_plan,
        "forecast_policy": forecast_result,
        "control_policy": control_result,
    }


def _number(value):
    return f"{value:.2f}" if isinstance(value, float) else str(value)


def build_html_report(result):
    """Build a standalone report of one policy-comparison experiment."""
    forecast = result["forecast_policy"]
    control = result["control_policy"]
    zone_cells = "".join(
        f'<article class="zone"><h3>{escape(zone)}</h3>'
        f'<p>history <strong>{result["history"]["calls_by_zone"][zone]}</strong></p>'
        f'<p>forecast <strong>{result["forecast_h1"][zone]:.2f}</strong></p>'
        f'<p>actual <strong>{result["actual_h1"][zone]}</strong></p></article>'
        for zone in result["forecast_h1"]
    )
    comparison_fields = (
        ("Completed live calls", "completed_live_calls"),
        ("Mean live wait (s)", "mean_live_wait_seconds"),
        ("Total live wait (s)", "total_live_wait_seconds"),
        ("Pickup distance (m)", "pickup_distance_m"),
        ("Empty distance (m)", "empty_distance_m"),
        ("Idle time (s)", "idle_seconds"),
        ("Pickup travel time (s)", "pickup_seconds"),
        ("Occupied time (s)", "occupied_seconds"),
        ("Reposition time (s)", "reposition_seconds"),
        ("Rejected commands", "rejected_commands"),
    )
    comparison_rows = "".join(
        f"<tr><td>{escape(label)}</td><td>{_number(control[field])}</td>"
        f"<td>{_number(forecast[field])}</td></tr>"
        for label, field in comparison_fields
    )
    decisions = "".join(
        f'<li><strong>{escape(item["taxi_id"])}</strong>: '
        f'{escape(item["source_zone_id"])} → {escape(item["target_zone_id"])}; '
        f'forecast {item["forecast_demand"]:.2f}, distance '
        f'{item["reposition_distance_m"]:.1f} m</li>'
        for item in result["reposition_plan"]["decisions"]
        if item["type"] == "reposition"
    )
    raw = escape(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Module 1-4 통합 평가</title>
<style>
:root{{--bg:#f4f6f8;--panel:#fff;--text:#17202a;--muted:#66717f;--line:#dce2e8;--accent:#2563eb}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,"Segoe UI",sans-serif;line-height:1.5}}
main{{width:min(1080px,calc(100% - 32px));margin:32px auto 64px}} h1,h2,h3,p{{margin-top:0}}
.hero,.panel{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:22px;margin-bottom:16px}}
.hero{{border-left:6px solid var(--accent)}} .scope{{color:var(--muted)}}
.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:18px}} .card{{background:var(--bg);border-radius:10px;padding:14px}}
.card span{{display:block;color:var(--muted)}} .card strong{{font-size:1.45rem}}
.zones{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}} .zone{{padding:13px;border:1px solid var(--line);border-radius:10px}}
.zone h3{{margin-bottom:8px}} .zone p{{display:flex;justify-content:space-between;margin:3px 0;color:var(--muted)}}
table{{width:100%;border-collapse:collapse}} th,td{{padding:9px 10px;border-bottom:1px solid var(--line);text-align:right}} th:first-child,td:first-child{{text-align:left}}
code,pre{{font-family:ui-monospace,Consolas,monospace}}
pre{{overflow:auto;background:#111827;color:#e5e7eb;padding:16px;border-radius:10px;font-size:.8rem}} li{{margin:7px 0}}
@media(max-width:700px){{.cards,.zones{{grid-template-columns:1fr}} main{{width:calc(100% - 20px);margin-top:12px}}}}
</style></head><body><main>
<section class="hero"><h1>Module 1–4 정책 비교 실험</h1>
<p class="scope">단일 합성 시나리오에서 예측 사용 정책과 미사용 대조군의 실행 결과를 비교합니다. 통합 완료 판정이나 실제 데이터의 모델 일반화 성능을 의미하지 않습니다.</p>
<div class="cards"><div class="card"><span>Model</span><strong>{escape(result["model"])}</strong></div>
<div class="card"><span>H1 forecast MAE</span><strong>{result["forecast_h1_mae"]:.3f}</strong></div>
<div class="card"><span>History calls</span><strong>{result["history"]["call_count"]}</strong></div></div></section>
<section class="panel"><h2>예측 사용/미사용 비교</h2><table><thead><tr><th>Metric</th><th>Control</th><th>Forecast</th></tr></thead><tbody>{comparison_rows}</tbody></table></section>
<section class="panel"><h2>구역별 과거·예측·실제 H1 수요</h2><p class="scope">H1은 t=3600부터 5분 구간입니다.</p><div class="zones">{zone_cells}</div></section>
<section class="panel"><h2>재배치 결정</h2><ul>{decisions or '<li>재배치 없음</li>'}</ul></section>
<section class="panel"><details><summary>원본 평가 JSON</summary><pre>{raw}</pre></details></section>
</main></body></html>"""


def write_html_report(result, requested_path):
    requested = Path(requested_path)
    requested.parent.mkdir(parents=True, exist_ok=True)
    output = requested
    suffix = 2
    while output.exists():
        output = requested.with_name(f"{requested.stem}_{suffix}{requested.suffix}")
        suffix += 1
    output.write_text(build_html_report(result), encoding="utf-8")
    return output


def main():
    parser = argparse.ArgumentParser(description="Evaluate and report the Module 1-4 flow")
    parser.add_argument("--model", choices=MODELS, default="rolling-mean-12")
    parser.add_argument(
        "--output",
        default="data/generated/end_to_end_report.html",
        help="HTML output path; an existing report is preserved with a numbered suffix",
    )
    args = parser.parse_args()
    result = evaluate_scenario(args.model)
    output = write_html_report(result, args.output)
    print(f"Generated report: {output}")
    print(json.dumps({
        "forecast_pickup_distance_m": result["forecast_policy"]["pickup_distance_m"],
        "control_pickup_distance_m": result["control_policy"]["pickup_distance_m"],
        "forecast_mean_wait_seconds": result["forecast_policy"]["mean_live_wait_seconds"],
        "control_mean_wait_seconds": result["control_policy"]["mean_live_wait_seconds"],
    }, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
