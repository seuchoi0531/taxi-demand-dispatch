"""Run the command-driven vehicle and passenger demo from the repository root."""

import argparse
import json

from . import Simulation, load_calls, load_config
from .demo import DemoRunner, load_call_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Module 1: 3×3 city and 3 taxis")
    parser.add_argument("--config", default="configs/module1_demo.toml")
    parser.add_argument("--scenario", help="optional finite recorded call scenario")
    parser.add_argument("--calls-config", default="configs/module1_calls.toml")
    parser.add_argument("--manual", action="store_true", help="select taxis and calls manually")
    parser.add_argument("--seed", type=int, help="override development call location seed")
    parser.add_argument("--call-interval", type=float, help="seconds between individual calls")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--steps", type=int, default=1200, help="headless tick count")
    parser.add_argument("--events", action="store_true", help="include event log in headless JSON")
    args = parser.parse_args()
    try:
        calls = load_calls(args.scenario) if args.scenario else ()
        simulation = Simulation(load_config(args.config), calls)
        if args.steps < 0:
            raise ValueError("--steps must be non-negative")
        if args.scenario:
            runner = DemoRunner(simulation, auto_assign=not args.manual)
        else:
            settings = load_call_settings(args.calls_config)
            interval = settings["interval_seconds"] if args.call_interval is None else args.call_interval
            seed = settings["seed"] if args.seed is None else args.seed
            runner = DemoRunner(simulation, call_interval_seconds=interval,
                                seed=seed, auto_assign=not args.manual)
        if args.headless:
            runner.advance(args.steps)
            result = simulation.observe()
            if args.events:
                result["events"] = simulation.events()
            print(json.dumps(result, indent=2, allow_nan=False))
        else:
            try:
                from .viewer import CityApp
            except ModuleNotFoundError as exc:
                if exc.name not in {"panda3d", "direct"}:
                    raise
                parser.error('3D dependency missing: python -m pip install -e ".[simulation]"')
            CityApp(runner).run()
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
