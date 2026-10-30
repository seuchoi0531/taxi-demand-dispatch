"""Run the movement demo from the repository root."""

import argparse
from dataclasses import asdict
import json

from .simulation import Simulation, load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Module 1: 3×3 city and 3 taxis")
    parser.add_argument("--config", default="configs/module1_demo.toml")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--steps", type=int, default=400, help="headless tick count")
    args = parser.parse_args()
    try:
        simulation = Simulation(load_config(args.config))
        if args.steps < 0:
            raise ValueError("--steps must be non-negative")
        if args.headless:
            simulation.advance(args.steps)
            print(json.dumps({"tick": simulation.tick,
                              "time_seconds": simulation.time_seconds,
                              "taxis": [asdict(t) for t in simulation.snapshot()]}, indent=2))
        else:
            try:
                from .viewer import CityApp
            except ModuleNotFoundError as exc:
                if exc.name not in {"panda3d", "direct"}:
                    raise
                parser.error('3D dependency missing: python -m pip install -e ".[simulation]"')
            CityApp(simulation).run()
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
