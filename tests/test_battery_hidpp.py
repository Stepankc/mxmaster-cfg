# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for HID++ Unified Battery status mapping (helper helpers)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path

import pytest

HELPER = Path(__file__).resolve().parents[1] / "helper" / "mxmaster-cfg-helper"


def _load_helper():
    # Helper is installed without a .py suffix; use SourceFileLoader explicitly.
    loader = importlib.machinery.SourceFileLoader(
        "mxmaster_cfg_helper", str(HELPER)
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Helper runs main only under __main__, so a normal exec is fine.
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def helper():
    return _load_helper()


@pytest.mark.parametrize(
    "byte,charging,status",
    [
        (0, False, "discharging"),
        (1, True, "charging"),
        (2, True, "almost_full"),
        (3, False, "full"),
        (4, None, "error"),
        (9, None, "unknown_9"),
    ],
)
def test_map_unified_battery_status(helper, byte, charging, status):
    assert helper._map_unified_battery_status(byte) == (charging, status)


def test_coerce_percent(helper):
    assert helper._coerce_percent(30) == 30
    assert helper._coerce_percent(150) == 100
    assert helper._coerce_percent(-1) == 0
    assert helper._coerce_percent("42") == 42
    assert helper._coerce_percent(True) is None
