"""Command-line entry points for baseline prediction and evaluation."""

import argparse
import json
from pathlib import Path

from . import evaluate, load_rows, predict, write_html_report, write_json
from .baseline import DEFAULT_MODEL, MODELS


def main(argv=None):
    parser = argparse.ArgumentParser(description="Module 3 baseline demand forecast")
    commands = parser.add_subparsers(dest="command", required=True)

    evaluate_parser = commands.add_parser("evaluate", help="evaluate a Module 2 CSV")
    evaluate_parser.add_argument("--input", required=True)
    evaluate_parser.add_argument("--output", required=True)
    evaluate_parser.add_argument("--model", choices=MODELS, default=DEFAULT_MODEL)

    predict_parser = commands.add_parser("predict", help="forecast one targetless feature row")
    predict_parser.add_argument("--input", required=True)
    predict_parser.add_argument("--output", required=True)
    predict_parser.add_argument("--model", choices=MODELS, default=DEFAULT_MODEL)

    report_parser = commands.add_parser("report", help="create a visual HTML evaluation report")
    report_parser.add_argument("--input", required=True)
    report_parser.add_argument("--output", required=True)
    report_parser.add_argument("--model", choices=MODELS, default=DEFAULT_MODEL)

    args = parser.parse_args(argv)
    try:
        if args.command == "report":
            output = write_html_report(load_rows(args.input), args.output, model=args.model)
            print(f"Generated HTML report: {output}")
            return
        if args.command == "evaluate":
            result = evaluate(load_rows(args.input), model=args.model)
        else:
            with Path(args.input).open(encoding="utf-8") as stream:
                result = predict(json.load(stream), model=args.model)
        write_json(result, args.output)
        print(json.dumps(result, indent=2, allow_nan=False))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
