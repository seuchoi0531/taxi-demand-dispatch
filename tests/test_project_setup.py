"""Tests for the initial project setup."""

from __future__ import annotations

import importlib
import sys


MODULE_NAMES = (
    "module1_simulation",
    "module2_preprocessing",
    "module3_prediction",
    "module4_dispatch",
)


def test_supported_python_version() -> None:
    """The project runs on Python 3.13 only."""
    assert (3, 13) <= sys.version_info < (3, 14)


def test_top_level_modules_are_importable() -> None:
    """Editable installs expose every project module."""
    for module_name in MODULE_NAMES:
        assert importlib.import_module(module_name) is not None
