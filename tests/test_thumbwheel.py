# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from mxmaster_cfg.adapter.logiops_cfg import CfgWriter
from mxmaster_cfg.buttons import ACTION_KEY_CUSTOM
from mxmaster_cfg.thumbwheel import (
    SCROLL_AXIS_CUSTOM,
    SCROLL_AXIS_HIRES,
    SCROLL_AXIS_HWHEEL,
    SCROLL_INTERVAL_KEY_CUSTOM,
    SCROLL_NOPRESS,
    SCROLL_OMIT,
    SCROLL_VOLUME,
    THUMB_ACTION_NONE,
    THUMB_ACTION_OMIT,
    build_thumbwheel,
    extract_custom_axis_fields,
    extract_custom_interval_fields,
    match_scroll_preset,
    match_thumb_action,
    resolve_scroll_sides,
    resolve_thumb_action,
)


def test_match_scroll_omit_and_presets() -> None:
    assert match_scroll_preset({}) == SCROLL_OMIT
    assert match_scroll_preset({"divert": True}) == SCROLL_OMIT
    hires = build_thumbwheel(
        divert=True,
        invert=False,
        scroll_preset=SCROLL_AXIS_HIRES,
    )
    assert match_scroll_preset(hires) == SCROLL_AXIS_HIRES
    assert match_scroll_preset(
        build_thumbwheel(divert=True, invert=False, scroll_preset=SCROLL_NOPRESS)
    ) == SCROLL_NOPRESS
    assert match_scroll_preset(
        build_thumbwheel(divert=True, invert=False, scroll_preset=SCROLL_VOLUME)
    ) == SCROLL_VOLUME


def test_match_scroll_unknown_axis_is_custom() -> None:
    tw = {
        "left": {
            "mode": "Axis",
            "axis": "REL_HWHEEL",
            "axis_multiplier": -3,
        },
        "right": {
            "mode": "Axis",
            "axis": "REL_HWHEEL",
            "axis_multiplier": 3,
        },
    }
    assert match_scroll_preset(tw) == SCROLL_AXIS_CUSTOM
    axis, mult = extract_custom_axis_fields(tw)
    assert axis == "REL_HWHEEL"
    assert mult == 3.0


def test_match_scroll_stock_axis_hwheel() -> None:
    tw = build_thumbwheel(
        divert=True, invert=False, scroll_preset=SCROLL_AXIS_HWHEEL
    )
    assert match_scroll_preset(tw) == SCROLL_AXIS_HWHEEL


def test_match_scroll_custom_interval_keypress() -> None:
    tw = build_thumbwheel(
        divert=True,
        invert=False,
        scroll_preset=SCROLL_INTERVAL_KEY_CUSTOM,
        interval=4,
        scroll_keys_text="KEY_LEFTCTRL + KEY_TAB",
    )
    assert match_scroll_preset(tw) == SCROLL_INTERVAL_KEY_CUSTOM
    iv, keys = extract_custom_interval_fields(tw)
    assert iv == 4
    assert "KEY_LEFTCTRL" in keys and "KEY_TAB" in keys


def test_match_thumb_action_unknown_keypress() -> None:
    assert match_thumb_action(None) == THUMB_ACTION_OMIT
    assert match_thumb_action({"type": "None"}) == THUMB_ACTION_NONE
    assert match_thumb_action({"type": "Keypress", "keys": ["KEY_MUTE"]}) == (
        "key_mute"
    )
    assert match_thumb_action(
        {"type": "Keypress", "keys": ["KEY_LEFTCTRL", "KEY_M"]}
    ) == ACTION_KEY_CUSTOM


def test_resolve_and_build_round_trip() -> None:
    tw = build_thumbwheel(
        divert=True,
        invert=True,
        scroll_preset=SCROLL_AXIS_CUSTOM,
        axis="REL_HWHEEL_HI_RES",
        multiplier=1.5,
        tap_preset=ACTION_KEY_CUSTOM,
        tap_keys_text="KEY_MUTE",
        touch_preset="key_playpause",
        proxy_preset=ACTION_KEY_CUSTOM,
        proxy_keys_text="KEY_A + KEY_B",
    )
    assert tw["divert"] is True
    assert tw["invert"] is True
    assert tw["left"]["axis_multiplier"] == -1.5
    assert tw["right"]["axis_multiplier"] == 1.5
    assert tw["tap"]["keys"] == ["KEY_MUTE"]
    assert tw["touch"]["keys"] == ["KEY_PLAYPAUSE"]
    assert tw["proxy"]["keys"] == ["KEY_A", "KEY_B"]
    assert match_scroll_preset(tw) == SCROLL_AXIS_CUSTOM
    assert match_thumb_action(tw["tap"]) == "key_mute"
    assert match_thumb_action(tw["proxy"]) == ACTION_KEY_CUSTOM


def test_divert_false_omits_gestures() -> None:
    tw = build_thumbwheel(
        divert=False,
        invert=False,
        scroll_preset=SCROLL_AXIS_HIRES,
        tap_preset="key_mute",
        touch_preset="key_mute",
        proxy_preset="key_mute",
    )
    assert tw == {"divert": False, "invert": False}


def test_empty_custom_keypress_skipped() -> None:
    tw = build_thumbwheel(
        divert=True,
        invert=False,
        scroll_preset=SCROLL_OMIT,
        tap_preset=ACTION_KEY_CUSTOM,
        tap_keys_text="  ",
        touch_preset=ACTION_KEY_CUSTOM,
        touch_keys_text="",
    )
    assert "tap" not in tw
    assert "touch" not in tw


def test_cfg_writer_touch_proxy_and_custom_axis() -> None:
    profile = {
        "device": {"name": "MX Master 3S"},
        "thumbwheel": build_thumbwheel(
            divert=True,
            invert=False,
            scroll_preset=SCROLL_AXIS_CUSTOM,
            axis="REL_HWHEEL",
            multiplier=2,
            tap_preset="key_mute",
            touch_preset=ACTION_KEY_CUSTOM,
            touch_keys_text="KEY_LEFTMETA",
            proxy_preset=ACTION_KEY_CUSTOM,
            proxy_keys_text="KEY_LEFTCTRL + KEY_X",
        ),
    }
    text = CfgWriter(profile).render()
    assert "thumbwheel:" in text
    assert "divert: true;" in text
    assert 'axis: "REL_HWHEEL";' in text
    assert "axis_multiplier: -2;" in text
    assert "axis_multiplier: 2;" in text
    assert "tap =" in text
    assert "touch =" in text
    assert "proxy =" in text
    assert '"KEY_LEFTMETA"' in text
    assert '"KEY_LEFTCTRL"' in text
    assert '"KEY_X"' in text
    assert "haptic" not in text


def test_resolve_scroll_sides_omit() -> None:
    assert resolve_scroll_sides(SCROLL_OMIT) == {}
    assert resolve_thumb_action(THUMB_ACTION_OMIT) is None
