"""Public entry points for reproducible preprocessing."""

from .scenario import generate_scenario
from .inference import build_inference_features
from .dataset import aggregate_calls, build_dataset, write_dataset, write_coverage_template

__all__ = ["generate_scenario", "aggregate_calls", "build_dataset", "write_dataset", "write_coverage_template", "build_inference_features"]
