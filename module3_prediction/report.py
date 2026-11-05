"""Self-contained HTML report for visually inspecting baseline forecasts."""

import html
import json
import math
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path

from .baseline import (
    DEFAULT_MODEL,
    FEATURE_COLUMNS,
    HORIZONS,
    RECENT_TREND_MODEL,
    ROLLING_MEAN_MODEL,
    TARGET_COLUMNS,
    ZONES,
    evaluate,
    predict,
)


def _number(value):
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _clock(seconds):
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    prefix = f"{days}일 " if days else ""
    return f"{prefix}{hours:02d}:{minutes:02d}"


def _line_chart(points):
    width, height = 920, 300
    left, right, top, bottom = 64, 24, 20, 48
    plot_width = width - left - right
    plot_height = height - top - bottom
    maximum = max(
        (max(point["actual"], point["baseline"], point["predicted"]) for point in points),
        default=0,
    )
    maximum = maximum if maximum > 0 else 1

    def x_position(index):
        return left + (plot_width / 2 if len(points) == 1 else index * plot_width / (len(points) - 1))

    def y_position(value):
        return top + plot_height - value * plot_height / maximum

    def path(name):
        return " ".join(
            f"{'M' if index == 0 else 'L'} {x_position(index):.2f} {y_position(point[name]):.2f}"
            for index, point in enumerate(points)
        )

    grid = []
    for index in range(5):
        value = maximum * index / 4
        y = y_position(value)
        grid.append(
            f'<line class="grid-line" x1="{left}" y1="{y:.2f}" x2="{width-right}" y2="{y:.2f}" />'
            f'<text class="axis-label" x="{left-10}" y="{y+4:.2f}" text-anchor="end">{_number(value)}</text>'
        )
    label_indexes = sorted({0, len(points) // 2, len(points) - 1}) if points else []
    x_labels = "".join(
        f'<text class="axis-label" x="{x_position(index):.2f}" y="{height-18}" text-anchor="middle">'
        f'{html.escape(_clock(points[index]["time"]))}</text>'
        for index in label_indexes
    )
    return f"""
<svg class="line-chart" viewBox="0 0 {width} {height}" role="img" aria-labelledby="line-title line-desc">
  <title id="line-title">첫 번째 예측 구간의 전체 구역 실제 수요와 예측 수요</title>
  <desc id="line-desc">사용 가능한 구역 행의 실제 수요, 60분 평균 기준선과 선택 모델 예측을 시각별로 합산한 선 그래프입니다.</desc>
  {''.join(grid)}
  <line class="axis-line" x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" />
  <line class="axis-line" x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" />
  <path class="series actual" d="{path('actual')}" />
  <path class="series baseline" d="{path('baseline')}" />
  <path class="series predicted" d="{path('predicted')}" />
  {x_labels}
  <text class="axis-title" x="18" y="{top + plot_height/2:.2f}" transform="rotate(-90 18 {top + plot_height/2:.2f})" text-anchor="middle">호출 수</text>
  <text class="axis-title" x="{left + plot_width/2:.2f}" y="{height-2}" text-anchor="middle">예측 시각</text>
</svg>"""


def _horizon_chart(by_horizon):
    width, height = 720, 280
    left, right, top, bottom = 64, 20, 20, 48
    plot_width = width - left - right
    plot_height = height - top - bottom
    maximum = max((item["mae"] for item in by_horizon), default=0)
    maximum = maximum if maximum > 0 else 1
    slot = plot_width / HORIZONS
    bar_width = slot * 0.56
    bars = []
    for index, item in enumerate(by_horizon):
        x = left + index * slot + (slot - bar_width) / 2
        bar_height = item["mae"] * plot_height / maximum
        y = top + plot_height - bar_height
        bars.append(
            f'<rect class="mae-bar" x="{x:.2f}" y="{y:.2f}" width="{bar_width:.2f}" height="{bar_height:.2f}">'
            f'<title>horizon {item["horizon"]}: MAE {_number(item["mae"])}</title></rect>'
            f'<text class="value-label" x="{x+bar_width/2:.2f}" y="{max(top+12, y-7):.2f}" text-anchor="middle">{_number(item["mae"])}</text>'
            f'<text class="axis-label" x="{x+bar_width/2:.2f}" y="{height-20}" text-anchor="middle">H{item["horizon"]}</text>'
        )
    return f"""
<svg class="bar-chart" viewBox="0 0 {width} {height}" role="img" aria-labelledby="bar-title bar-desc">
  <title id="bar-title">예측 구간별 평균 절대 오차</title>
  <desc id="bar-desc">H1부터 H6까지 각 5분 예측 구간의 MAE 막대 그래프입니다.</desc>
  <line class="axis-line" x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" />
  <line class="axis-line" x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" />
  {''.join(bars)}
  <text class="axis-title" x="18" y="{top + plot_height/2:.2f}" transform="rotate(-90 18 {top + plot_height/2:.2f})" text-anchor="middle">MAE</text>
  <text class="axis-title" x="{left + plot_width/2:.2f}" y="{height-2}" text-anchor="middle">5분 예측 구간</text>
</svg>"""


def _heatmap(title, stats, field, suffix=""):
    values = [stats[zone][field] for zone in ZONES if stats[zone]["count"]]
    maximum = max(values, default=0)
    cells = []
    for y in reversed(range(3)):
        for x in range(3):
            zone = f"zone-{x}-{y}"
            item = stats[zone]
            if item["count"]:
                value = item[field]
                intensity = 12 + (value / maximum * 76 if maximum else 0)
                display = f"{_number(value)}{suffix}"
                label = f"{zone}, {title} {display}"
            else:
                intensity = 0
                display = "데이터 없음"
                label = f"{zone}, 데이터 없음"
            cells.append(
                f'<div class="heat-cell" data-zone="{zone}" data-field="{field}" '
                f'style="--intensity:{intensity:.1f}%" aria-label="{html.escape(label)}">'
                f'<span>{zone}</span><strong data-value>{html.escape(display)}</strong></div>'
            )
    return f"""
<section class="heatmap-block" aria-label="{html.escape(title)}">
  <h3>{html.escape(title)}</h3>
  <div class="heat-grid">{''.join(cells)}</div>
  <div class="heat-legend"><span>낮음</span><i aria-hidden="true"></i><span>높음</span></div>
</section>"""


def build_html_report(rows: Iterable[Mapping], *, model=DEFAULT_MODEL):
    """Build a self-contained, browser-readable evaluation report."""
    rows = list(rows)
    evaluation = evaluate(rows, model=model)
    baseline_evaluation = evaluate(rows, model=ROLLING_MEAN_MODEL)
    time_points = defaultdict(
        lambda: {"actual": 0.0, "baseline": 0.0, "predicted": 0.0}
    )
    zone_totals = {
        zone: {"actual": 0.0, "predicted": 0.0, "error": 0.0, "count": 0}
        for zone in ZONES
    }
    detail_values = defaultdict(dict)
    for row in rows:
        features = {name: row[name] for name in FEATURE_COLUMNS}
        forecast = predict(features, model=model)
        baseline_forecast = predict(features, model=ROLLING_MEAN_MODEL)
        first_prediction = forecast["predictions"][0]["predicted_demand"]
        point = time_points[row["prediction_time_seconds"]]
        point["actual"] += row["target_1"]
        point["baseline"] += baseline_forecast["predictions"][0]["predicted_demand"]
        point["predicted"] += first_prediction
        zone = zone_totals[row["zone_id"]]
        for index, item in enumerate(forecast["predictions"]):
            actual = row[TARGET_COLUMNS[index]]
            detail_values[str(row["prediction_time_seconds"])].setdefault(
                str(index + 1), {}
            )[row["zone_id"]] = {
                "actual": actual,
                "predicted": item["predicted_demand"],
                "error": abs(item["predicted_demand"] - actual),
            }
            zone["actual"] += actual
            zone["predicted"] += item["predicted_demand"]
            zone["error"] += abs(item["predicted_demand"] - actual)
            zone["count"] += 1
    zone_stats = {}
    for zone, totals in zone_totals.items():
        count = totals["count"]
        zone_stats[zone] = {
            "count": count,
            "actual": totals["actual"] / count if count else 0,
            "predicted": totals["predicted"] / count if count else 0,
            "error": totals["error"] / count if count else 0,
        }
    fields = ("actual", "predicted", "error")
    average_scales = {
        field: max((item[field] for item in zone_stats.values() if item["count"]), default=0)
        for field in fields
    }
    individual_scales = {field: 0 for field in fields}
    for time_values in detail_values.values():
        for horizon_values in time_values.values():
            for item in horizon_values.values():
                for field in fields:
                    individual_scales[field] = max(individual_scales[field], item[field])
    points = [dict(time=time, **values) for time, values in sorted(time_points.items())]
    downsampled = False
    if len(points) > 240:
        step = math.ceil(len(points) / 240)
        points = points[::step]
        downsampled = True
    warnings = list(evaluation["warnings"])
    if downsampled:
        warnings.append("시간 그래프는 가독성을 위해 최대 240개 시점으로 축약했습니다.")
    warning_html = "".join(f"<li>{html.escape(warning)}</li>" for warning in warnings)
    source_text = ", ".join(evaluation["source_kinds"])
    model_label = "최근 추세 보정" if model == RECENT_TREND_MODEL else "과거 60분 평균"
    baseline_mae = baseline_evaluation["overall_mae"]
    improvement = (
        (baseline_mae - evaluation["overall_mae"]) / baseline_mae * 100
        if baseline_mae
        else 0.0
    )
    time_options = "".join(
        f'<option value="{time}">{html.escape(_clock(time))} ({time}초)</option>'
        for time in sorted(time_points)
    )
    report_data = json.dumps(
        {
            "average": zone_stats,
            "details": detail_values,
            "scales": {"average": average_scales, "individual": individual_scales},
        },
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Module 3 수요 예측 평가</title>
<style>
:root {{ color-scheme: light dark; --bg:#f6f7f9; --panel:#ffffff; --text:#18202a; --muted:#66717f; --border:#d9dee5; --actual:#2563eb; --baseline:#7c3aed; --predicted:#ea580c; --heat:#7c3aed; --bar:#2563eb; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#11151b; --panel:#1a2029; --text:#edf1f7; --muted:#a8b1be; --border:#35404d; --actual:#60a5fa; --baseline:#a78bfa; --predicted:#fb923c; --heat:#a78bfa; --bar:#60a5fa; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--text); font-family:system-ui,-apple-system,"Segoe UI",sans-serif; line-height:1.5; }}
main {{ width:min(1120px, calc(100% - 32px)); margin:32px auto 64px; }}
h1,h2,h3,p {{ margin-top:0; }} h1 {{ margin-bottom:6px; }} h2 {{ margin-bottom:14px; }} h3 {{ margin-bottom:10px; }}
.subtitle,.caption {{ color:var(--muted); }}
.summary {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin:24px 0; }}
.card,.panel {{ background:var(--panel); border:1px solid var(--border); border-radius:12px; }}
.card {{ padding:16px; }} .card span {{ display:block; color:var(--muted); }} .card strong {{ display:block; font-size:1.65rem; margin-top:3px; font-variant-numeric:tabular-nums; }}
.panel {{ padding:20px; margin-top:16px; }}
.legend {{ display:flex; flex-wrap:wrap; gap:18px; color:var(--muted); margin-bottom:8px; }}
.legend span::before {{ content:""; display:inline-block; width:18px; height:3px; margin:0 7px 3px 0; background:var(--series); }}
.legend .actual-key {{ --series:var(--actual); }} .legend .baseline-key {{ --series:var(--baseline); }} .legend .predicted-key {{ --series:var(--predicted); }}
svg {{ display:block; width:100%; height:auto; overflow:visible; }}
.grid-line {{ stroke:var(--border); stroke-width:1; }} .axis-line {{ stroke:var(--muted); stroke-width:1; }}
.axis-label,.axis-title,.value-label {{ fill:var(--muted); font-size:12px; }} .value-label {{ fill:var(--text); }}
.series {{ fill:none; stroke-width:2.5; stroke-linejoin:round; stroke-linecap:round; }} .series.actual {{ stroke:var(--actual); }} .series.baseline {{ stroke:var(--baseline); stroke-dasharray:6 4; }} .series.predicted {{ stroke:var(--predicted); }}
.mae-bar {{ fill:var(--bar); }}
.heatmaps {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:18px; }}
.view-controls {{ display:flex; flex-wrap:wrap; align-items:end; gap:12px; margin-bottom:16px; }}
.mode-toggle {{ display:inline-flex; border:1px solid var(--border); border-radius:9px; overflow:hidden; }}
.mode-toggle button {{ appearance:none; border:0; border-right:1px solid var(--border); background:var(--panel); color:var(--text); padding:9px 13px; font:inherit; }}
.mode-toggle button:last-child {{ border-right:0; }} .mode-toggle button[aria-pressed="true"] {{ background:var(--text); color:var(--panel); }}
.detail-controls {{ display:flex; flex-wrap:wrap; gap:10px; }} .detail-controls[hidden] {{ display:none; }}
.detail-controls label {{ display:grid; gap:4px; color:var(--muted); font-size:.82rem; }}
.detail-controls select {{ min-width:130px; border:1px solid var(--border); border-radius:8px; background:var(--panel); color:var(--text); padding:8px 28px 8px 9px; font:inherit; }}
.selection-summary {{ color:var(--muted); margin:0 0 12px; }}
.heat-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:6px; }}
.heat-cell {{ min-height:88px; padding:10px; display:flex; flex-direction:column; justify-content:space-between; background:color-mix(in srgb,var(--heat) var(--intensity),var(--panel)); border-radius:8px; }}
.heat-cell span {{ color:var(--muted); font-size:.78rem; }} .heat-cell strong {{ font-size:1.05rem; font-variant-numeric:tabular-nums; }}
.heat-legend {{ display:flex; align-items:center; gap:7px; color:var(--muted); font-size:.78rem; margin-top:8px; }}
.heat-legend i {{ flex:1; height:8px; border-radius:4px; background:linear-gradient(90deg,var(--panel),var(--heat)); }}
.warning {{ border-left:4px solid var(--predicted); }} .warning ul {{ margin-bottom:0; }}
table {{ width:100%; border-collapse:collapse; }} th,td {{ padding:9px 10px; text-align:right; border-bottom:1px solid var(--border); }} th:first-child,td:first-child {{ text-align:left; }}
@media (max-width:780px) {{ .summary,.heatmaps {{ grid-template-columns:1fr; }} main {{ width:min(100% - 20px,1120px); margin-top:18px; }} .panel {{ padding:14px; }} }}
</style>
</head>
<body>
<main>
  <header>
    <h1>Module 3 수요 예측 평가</h1>
    <p class="subtitle">{html.escape(model_label)} 모델 · 데이터 출처 {html.escape(source_text)}</p>
  </header>
  <section class="summary" aria-label="평가 요약">
    <div class="card"><span>{html.escape(model_label)} MAE</span><strong>{_number(evaluation['overall_mae'])}</strong></div>
    <div class="card"><span>60분 평균 baseline MAE</span><strong>{_number(baseline_mae)}</strong></div>
    <div class="card"><span>baseline 대비 개선</span><strong>{_number(improvement)}%</strong></div>
  </section>
  <section class="panel">
    <h2>실제 수요와 예측 수요</h2>
    <div class="legend"><span class="actual-key">실제 H1</span><span class="baseline-key">60분 평균 H1</span><span class="predicted-key">{html.escape(model_label)} H1</span></div>
    {_line_chart(points)}
    <p class="caption">각 시각에 사용 가능한 구역의 첫 번째 5분 구간 수요를 합산했습니다.</p>
  </section>
  <section class="panel">
    <h2>예측 구간별 오차</h2>
    {_horizon_chart(evaluation['by_horizon'])}
    <div class="table-wrap">
      <table><thead><tr><th>구간</th><th>대상 시간</th><th>MAE</th></tr></thead><tbody>
      {''.join(f'<tr><td>H{item["horizon"]}</td><td>+{(item["horizon"]-1)*5}~+{item["horizon"]*5}분</td><td>{_number(item["mae"])}</td></tr>' for item in evaluation['by_horizon'])}
      </tbody></table>
    </div>
  </section>
  <section class="panel">
    <h2>구역별 수요 상세</h2>
    <div id="zone-analysis">
      <div class="view-controls">
        <div class="mode-toggle" role="group" aria-label="구역별 값 표시 방식">
          <button type="button" data-mode="average" aria-pressed="true">전체 평균</button>
          <button type="button" data-mode="individual" aria-pressed="false">시점별 값</button>
        </div>
        <div class="detail-controls" data-detail-controls hidden>
          <label>예측 시각<select data-time-select>{time_options}</select></label>
          <label>예측 구간<select data-horizon-select>
            {''.join(f'<option value="{horizon}">H{horizon} (+{(horizon-1)*5}~+{horizon*5}분)</option>' for horizon in range(1, HORIZONS + 1))}
          </select></label>
        </div>
      </div>
      <p class="selection-summary" data-selection-summary aria-live="polite">모든 예측 시각과 6개 horizon의 평균</p>
      <div class="heatmaps">
      {_heatmap('실제 수요', zone_stats, 'actual')}
      {_heatmap('예측 수요', zone_stats, 'predicted')}
      {_heatmap('절대 오차', zone_stats, 'error')}
      </div>
    </div>
    <p class="caption">전체 평균과 선택한 시각·horizon의 개별 구역 값을 전환할 수 있습니다.</p>
  </section>
  {f'<section class="panel warning"><h2>해석 주의사항</h2><ul>{warning_html}</ul></section>' if warnings else ''}
</main>
<script type="application/json" id="module3-report-data">{report_data}</script>
<script>
(() => {{
  const root = document.getElementById("zone-analysis");
  const data = JSON.parse(document.getElementById("module3-report-data").textContent);
  const modeButtons = Array.from(root.querySelectorAll("[data-mode]"));
  const detailControls = root.querySelector("[data-detail-controls]");
  const timeSelect = root.querySelector("[data-time-select]");
  const horizonSelect = root.querySelector("[data-horizon-select]");
  const summary = root.querySelector("[data-selection-summary]");
  let mode = "average";

  const format = value => Number(value).toFixed(3).replace(/\\.?0+$/, "");
  const update = () => {{
    const values = mode === "average"
      ? data.average
      : ((data.details[timeSelect.value] || {{}})[horizonSelect.value] || {{}});
    for (const field of ["actual", "predicted", "error"]) {{
      const maximum = Number(data.scales[mode][field]);
      root.querySelectorAll(`[data-field="${{field}}"]`).forEach(cell => {{
        const item = values[cell.dataset.zone];
        const hasValue = item && item.count !== 0 && item[field] !== undefined;
        const value = hasValue ? Number(item[field]) : 0;
        const intensity = hasValue ? 12 + (maximum ? value / maximum * 76 : 0) : 0;
        const display = hasValue ? format(value) : "데이터 없음";
        cell.style.setProperty("--intensity", `${{intensity.toFixed(1)}}%`);
        cell.querySelector("[data-value]").textContent = display;
        cell.setAttribute("aria-label", `${{cell.dataset.zone}}, ${{field}} ${{display}}`);
      }});
    }}
    if (mode === "average") {{
      summary.textContent = "모든 예측 시각과 6개 horizon의 평균";
    }} else {{
      const option = timeSelect.options[timeSelect.selectedIndex];
      summary.textContent = `${{option.text}} · H${{horizonSelect.value}}의 개별 구역 값`;
    }}
  }};

  modeButtons.forEach(button => button.addEventListener("click", () => {{
    mode = button.dataset.mode;
    modeButtons.forEach(item => item.setAttribute("aria-pressed", String(item === button)));
    detailControls.hidden = mode !== "individual";
    update();
  }}));
  timeSelect.addEventListener("change", update);
  horizonSelect.addEventListener("change", update);
}})();
</script>
</body>
</html>
"""


def write_html_report(rows: Iterable[Mapping], path, *, model=DEFAULT_MODEL):
    """Write HTML, preserving an existing result with an incremented suffix."""
    document = build_html_report(rows, model=model)
    requested = Path(path)
    requested.parent.mkdir(parents=True, exist_ok=True)
    match = re.fullmatch(r"(.*?)(?:_(\d+))?", requested.stem)
    base = match.group(1)
    number = int(match.group(2)) + 1 if match.group(2) else 2
    output = requested
    while True:
        try:
            with output.open("x", encoding="utf-8") as stream:
                stream.write(document)
            return output
        except FileExistsError:
            output = requested.with_name(f"{base}_{number}{requested.suffix}")
            number += 1
