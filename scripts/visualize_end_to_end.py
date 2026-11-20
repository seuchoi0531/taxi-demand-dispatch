"""Visualize one deterministic Module 1→2→3→4→1 forecast decision."""

import argparse
import json

from module1_simulation import Simulation, load_config
from module1_simulation.demo import DemoRunner
from module2_preprocessing import build_simulation_features
from module3_prediction import predict
from module4_dispatch import build_plan


HISTORY_INTERVAL_SECONDS = 300
HISTORY_INTERVALS = 12
LIVE_START_SECONDS = HISTORY_INTERVAL_SECONDS * HISTORY_INTERVALS
FIRST_LIVE_CALL_SECONDS = LIVE_START_SECONDS + 20
QUEUED_BURST_SECONDS = LIVE_START_SECONDS + 23
HEADLESS_RUN_SECONDS = 200
MODELS = ("rolling-mean-12", "recent-trend")
VISUAL_CALLS = (
    {
        "call_id": "live-01-hot",
        "requested_at_seconds": FIRST_LIVE_CALL_SECONDS,
        # [2,3] is in zone-2-2 but remains 20 m from its anchor, so the
        # passenger is visible briefly before pickup.
        "origin": [2, 3],
        "destination": [0, 0],
    },
    {
        "call_id": "live-02-hot",
        "requested_at_seconds": FIRST_LIVE_CALL_SECONDS,
        "origin": [3, 2],
        "destination": [0, 0],
    },
    {
        "call_id": "live-03-local",
        "requested_at_seconds": FIRST_LIVE_CALL_SECONDS,
        "origin": [0, 1],
        "destination": [3, 3],
    },
    {
        "call_id": "live-04-queue",
        "requested_at_seconds": QUEUED_BURST_SECONDS,
        "origin": [1, 0],
        "destination": [2, 3],
    },
    {
        "call_id": "live-05-queue",
        "requested_at_seconds": QUEUED_BURST_SECONDS,
        "origin": [2, 3],
        "destination": [0, 1],
    },
)


def build_history_calls():
    """Return irregular all-zone history with zone-2-2 as the demand hotspot."""
    background_zones = [
        (0, 0), (0, 1), (0, 2), (1, 0),
        (1, 1), (1, 2), (2, 0), (2, 1),
    ]
    primary_offsets = (17, 93, 41, 226, 68, 154, 12, 187, 109, 53, 219, 132)
    secondary_offsets = (181, 207, 163, 119, 214, 172, 201, 146, 193, 128, 177, 221)
    calls = []
    for index in range(HISTORY_INTERVALS):
        interval_start = index * HISTORY_INTERVAL_SECONDS
        entries = [((2, 2), primary_offsets[index], "hotspot-a")]
        if index not in {0, 3, 5, 9}:
            entries.append(((2, 2), secondary_offsets[index], "hotspot-b"))

        # The two rotations guarantee at least three calls in every non-hotspot
        # zone; the optional third call breaks the otherwise regular pattern.
        first = background_zones[index % len(background_zones)]
        second = background_zones[(index + 4) % len(background_zones)]
        entries.append((first, 37 + (index * 47) % 151, "background-a"))
        if second != first:
            entries.append((second, 61 + (index * 31) % 137, "background-b"))
        if index % 2:
            third = background_zones[(index * 7 + 1) % len(background_zones)]
            if third not in {first, second}:
                entries.append((third, 29 + (index * 59) % 173, "background-c"))

        for sequence, (origin, offset, kind) in enumerate(sorted(entries, key=lambda item: item[1])):
            destination = (
                [0, 0]
                if index == HISTORY_INTERVALS - 1
                else [(origin[0] + index + 1) % 3, (origin[1] + 2 * index + 1) % 3]
            )
            calls.append({
                "call_id": f"history-{index:02d}-{sequence}-{kind}",
                "requested_at_seconds": interval_start + offset,
                "origin": list(origin),
                "destination": destination,
            })
    return calls


class VisualizationRunner:
    """Prepare and run the repeatable cross-module visualization scene."""

    mode_label = "Integration demo / Module 4 automatic dispatch"
    manual_controls = False
    initial_message = (
        "t=0-3600 history is preloaded; live calls begin at t=3620. R replays from t=3600."
    )
    reset_message = "Replay reset: history rebuilt and live scene restarted at t=3600."

    def __init__(self, base_runner: DemoRunner, model: str) -> None:
        self._base_runner = base_runner
        self.simulation = base_runner.simulation
        self.model = model
        self.plan = self._prepare_scene()

    @property
    def auto_assign(self) -> bool:
        return False

    def _apply_dispatch_plan(self, *, forecasts=None):
        plan = build_plan(
            self.simulation.observe(),
            block_size_m=self.simulation.config.block_size_m,
            forecasts=forecasts,
        )
        for command in plan["commands"]:
            self.simulation.apply_command(command)
        return plan

    def _prepare_scene(self):
        ticks_per_second = round(1 / self.simulation.config.tick_seconds)
        for _ in range(LIVE_START_SECONDS):
            self._apply_dispatch_plan()
            self._base_runner.advance(ticks_per_second)

        features = build_simulation_features(
            self.simulation.observe(),
            complete_since_seconds=0,
            coverage_evidence="Complete deterministic synthetic simulation history",
        )
        forecasts = [predict(row, model=self.model) for row in features]
        self.forecasts = forecasts
        plan = self._apply_dispatch_plan(forecasts=forecasts)
        if not any(command["type"] == "reposition" for command in plan["commands"]):
            raise RuntimeError("integration visualization: expected a reposition command")
        first_horizon = {
            forecast["zone_id"]: forecast["predictions"][0]["predicted_demand"]
            for forecast in forecasts
        }
        self.forecast_h1 = first_horizon
        moved = [
            decision["taxi_id"]
            for decision in plan["decisions"]
            if decision["type"] == "reposition"
        ]
        rows = []
        for x in range(3):
            rows.append("  ".join(
                f"z{x}{y}={first_horizon[f'zone-{x}-{y}']:.2f}"
                for y in range(3)
            ))
        self.integration_summary = (
            "H1 FORECAST CALLS / 5 MIN\n"
            + "\n".join(rows)
            + f"\nREPOSITION {', '.join(moved)} -> z22"
        )
        return plan

    def advance(self, ticks: int = 1) -> None:
        if type(ticks) is not int or ticks < 0:
            raise ValueError("ticks: expected a non-negative integer")
        for _ in range(ticks):
            self._base_runner.advance()
            plan = build_plan(
                self.simulation.observe(),
                block_size_m=self.simulation.config.block_size_m,
            )
            for command in plan["commands"]:
                self.simulation.apply_command(command)

    def reset(self) -> None:
        self._base_runner.reset()
        self.plan = self._prepare_scene()


def prepare_visualization(model: str):
    """Build complete synthetic history and apply one forecast-based plan."""
    config = load_config("configs/module1_demo.toml")
    calls = build_history_calls()
    calls.extend(dict(call) for call in VISUAL_CALLS)
    simulation = Simulation(config, calls)
    runner = VisualizationRunner(DemoRunner(simulation, auto_assign=False), model)
    return runner, runner.plan


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Visualize the public Module 1→2→3→4→1 integration flow"
    )
    parser.add_argument("--model", choices=MODELS, default="rolling-mean-12")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="finish the reposition and print JSON without opening Panda3D",
    )
    args = parser.parse_args()

    runner, plan = prepare_visualization(args.model)
    if args.headless:
        runner.advance(round(HEADLESS_RUN_SECONDS / runner.simulation.config.tick_seconds))
        observation = runner.simulation.observe()
        visual_calls = [
            {
                "call_id": passenger["call_id"],
                "requested_at_seconds": passenger["requested_at_seconds"],
                "origin": passenger["origin"],
                "destination": passenger["destination"],
                "state": passenger["state"],
                "taxi_id": passenger["taxi_id"],
            }
            for passenger in observation["passengers"]
            if passenger["call_id"].startswith("live-")
        ]
        result = {
            "plan": plan,
            "forecast_h1": runner.forecast_h1,
            "final": {
                "time_seconds": observation["time_seconds"],
                "taxis": observation["taxis"],
                "metrics": observation["metrics"],
            },
            "visual_calls": visual_calls,
            "reposition_events": [
                event
                for event in runner.simulation.events()
                if event["event"].startswith("reposition_")
            ],
        }
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        return

    print(json.dumps(plan, indent=2, ensure_ascii=False, allow_nan=False))
    try:
        from module1_simulation.viewer import CityApp
    except ModuleNotFoundError as exc:
        if exc.name not in {"panda3d", "direct"}:
            raise
        parser.error('3D dependency missing: python -m pip install -e ".[simulation]"')
    CityApp(runner).run()


if __name__ == "__main__":
    main()
