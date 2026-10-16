"""Offline by default. Live tests never run just because a key is present."""
import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_example(relative):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pytest_collection_modifyitems(items):
    if os.environ.get("COOKBOOK_LIVE") != "1":
        for item in items:
            if "live" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="Set COOKBOOK_LIVE=1 to explicitly enable Runtime/model tests"))
