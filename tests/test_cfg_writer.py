# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from pathlib import Path

from mxmaster_cfg.adapter.logiops_cfg import CfgWriter, load_profile

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "profiles" / "mx-master-3s-default.yaml"


def test_render_contains_device_and_smartshift() -> None:
    profile = load_profile(EXAMPLE)
    text = CfgWriter(profile).render()
    assert 'name: "MX Master 3S"' in text
    assert "smartshift:" in text
    assert "hiresscroll:" in text
    assert "ToggleSmartShift" in text
    assert "Gestures" in text


def test_render_hiresscroll_fields() -> None:
    profile = {
        "device": {"name": "MX Master 3S"},
        "dpi": 1000,
        "hiresscroll": {"hires": False, "invert": True, "target": True},
    }
    text = CfgWriter(profile).render()
    assert "hiresscroll:" in text
    assert "hires: false;" in text
    assert "invert: true;" in text
    assert "target: true;" in text


def test_render_thumbwheel_divert_invert_and_axis() -> None:
    profile = {
        "device": {"name": "MX Master 3S"},
        "dpi": 1000,
        "thumbwheel": {
            "divert": True,
            "invert": False,
            "left": {
                "mode": "Axis",
                "axis": "REL_HWHEEL_HI_RES",
                "axis_multiplier": -1,
            },
            "right": {
                "mode": "Axis",
                "axis": "REL_HWHEEL_HI_RES",
                "axis_multiplier": 1,
            },
            "tap": {"type": "Keypress", "keys": ["KEY_MUTE"]},
        },
    }
    text = CfgWriter(profile).render()
    assert "thumbwheel:" in text
    assert "divert: true;" in text
    assert "invert: false;" in text
    assert 'mode: "Axis";' in text
    assert 'axis: "REL_HWHEEL_HI_RES";' in text
    assert "axis_multiplier: -1;" in text
    assert "tap =" in text
    assert 'type: "Keypress";' in text
    assert '"KEY_MUTE"' in text
    # No haptic in logiops schema — writer must not invent it.
    assert "haptic" not in text


def test_render_thumbwheel_nopress() -> None:
    profile = {
        "device": {"name": "MX Master 3S"},
        "thumbwheel": {
            "divert": True,
            "invert": True,
            "left": {"mode": "NoPress"},
            "right": {"mode": "NoPress"},
        },
    }
    text = CfgWriter(profile).render()
    assert "divert: true;" in text
    assert "invert: true;" in text
    assert 'mode: "NoPress";' in text


def test_render_cycle_dpi_in_gestures() -> None:
    profile = {
        "device": {"name": "MX Master 3S"},
        "dpi": 1000,
        "smartshift": {"on": True, "threshold": 25},
        "buttons": [
            {
                "cid": 0xC3,
                "action": {
                    "type": "Gestures",
                    "gestures": [
                        {
                            "direction": "Left",
                            "mode": "OnRelease",
                            "action": {
                                "type": "CycleDPI",
                                "dpis": [400, 800, 1200],
                            },
                        },
                        {
                            "direction": "None",
                            "mode": "OnRelease",
                            "action": {"type": "None"},
                        },
                    ],
                },
            }
        ],
    }
    text = CfgWriter(profile).render()
    assert 'type: "CycleDPI"' in text
    assert "dpis: [400, 800, 1200]" in text
    assert "threshold: 25" in text
    assert 'direction: "None"' in text
