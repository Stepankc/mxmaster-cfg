# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from mxmaster_cfg.status_hold import (
    AUTO_WAKE_COOLDOWN_S,
    LAST_GOOD_HOLD_S,
    device_dicts,
    should_auto_wake,
    should_hold_last_good,
    soft_miss_quirk,
)


def test_device_dicts_ignores_path_strings() -> None:
    wake_payload = {
        "devices": ["/pizza/pixl/logiops/devices/0"],
        "device_count": 1,
    }
    assert device_dicts(wake_payload) == []
    full = {
        "devices": [
            {"path": "/pizza/pixl/logiops/devices/0", "name": "MX Master 3S"}
        ]
    }
    assert len(device_dicts(full)) == 1


def test_hold_last_good_within_window() -> None:
    good = {
        "devices": [
            {"path": "/x", "name": "MX Master 3S", "product_id": 45108}
        ]
    }
    assert should_hold_last_good(
        has_devices=False,
        last_good=good,
        last_good_mono=100.0,
        now_mono=100.0 + LAST_GOOD_HOLD_S - 1,
    )
    assert not should_hold_last_good(
        has_devices=False,
        last_good=good,
        last_good_mono=100.0,
        now_mono=100.0 + LAST_GOOD_HOLD_S + 1,
    )
    assert not should_hold_last_good(
        has_devices=True,
        last_good=good,
        last_good_mono=100.0,
        now_mono=101.0,
    )


def test_auto_wake_cooldown() -> None:
    assert should_auto_wake(
        has_devices=False,
        now_mono=100.0,
        last_wake_mono=0.0,
    )
    assert not should_auto_wake(
        has_devices=False,
        now_mono=100.0,
        last_wake_mono=90.0,
        cooldown_s=AUTO_WAKE_COOLDOWN_S,
    )
    assert should_auto_wake(
        has_devices=False,
        now_mono=100.0 + AUTO_WAKE_COOLDOWN_S,
        last_wake_mono=100.0,
    )
    assert not should_auto_wake(
        has_devices=False,
        now_mono=200.0,
        last_wake_mono=0.0,
        blocked=True,
    )
    assert not should_auto_wake(
        has_devices=True,
        now_mono=200.0,
        last_wake_mono=0.0,
    )


def test_soft_miss_quirk_ru() -> None:
    text = soft_miss_quirk(12.3)
    assert "D-Bus" in text
    assert "снимок" in text
