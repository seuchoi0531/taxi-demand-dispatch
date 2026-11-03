"""Generate a finite call scenario from explicit, reproducible settings."""

import argparse
import json
from pathlib import Path
import tomllib
import sys

from . import generate_scenario


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "dataset":
        from .dataset import dataset_main
        dataset_main(sys.argv[2:])
        return
    parser = argparse.ArgumentParser(description="Module 2 synthetic call scenario")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        with Path(args.config).open("rb") as source:
            settings = tomllib.load(source)
        required = {"seed", "call_count", "start_seconds", "interval_seconds", "tick_seconds"}
        if set(settings) != required:
            raise ValueError(f"configuration: expected exactly {sorted(required)}")
        scenario = generate_scenario(**settings)
        serialized = json.dumps(scenario, indent=2, allow_nan=False) + "\n"
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as target:
            target.write(serialized)
        print(f"Generated {len(scenario['calls'])} calls: {output}")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
