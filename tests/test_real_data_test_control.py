"""Tests for opt-in real-data pytest controls."""

import conftest
import numpy as np
import xarray as xr


class _Group:
    def __init__(self):
        self.options = []

    def addoption(self, *args, **kwargs):
        self.options.append((args, kwargs))


class _Parser:
    def __init__(self):
        self.group = _Group()

    def getgroup(self, name):
        assert name == "real-data"
        return self.group


class _Config:
    def __init__(self, run_real_data):
        self.run_real_data = run_real_data

    def getoption(self, name):
        assert name == "--run-real-data"
        return self.run_real_data


class _Item:
    def __init__(self, real_data):
        self.real_data = real_data
        self.markers = []

    def get_closest_marker(self, name):
        assert name == "real_data"
        return object() if self.real_data else None

    def add_marker(self, marker):
        self.markers.append(marker)


def test_adds_run_real_data_option():
    parser = _Parser()

    conftest.pytest_addoption(parser)

    assert parser.group.options == [
        (("--run-real-data",), {"action": "store_true", "default": False}),
    ]


def test_skips_marked_items_without_run_real_data():
    item = _Item(real_data=True)

    conftest.pytest_collection_modifyitems(_Config(False), [item])

    assert [marker.name for marker in item.markers] == ["skip"]


def test_leaves_marked_items_enabled_with_run_real_data():
    item = _Item(real_data=True)

    conftest.pytest_collection_modifyitems(_Config(True), [item])

    assert item.markers == []


def test_school_detection_subset_caps_real_data_grid():
    dataset = xr.Dataset(
        {"Sv": (("ping_time", "range_sample"), np.zeros((80, 5000)))},
    )

    subset = conftest.subset_for_school_detection(dataset)

    assert dict(subset.sizes) == {"ping_time": 64, "range_sample": 4096}
