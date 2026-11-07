"""Public entry points for the first reproducible demand baseline."""

from .baseline import evaluate, load_rows, predict, write_json
from .report import build_html_report, write_html_report

__all__ = [
    "build_html_report",
    "evaluate",
    "load_rows",
    "predict",
    "write_html_report",
    "write_json",
]
