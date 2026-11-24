# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from mxmaster_cfg.adapter.logiops_cfg import CfgWriter
from mxmaster_cfg.buttons import (
    ACTION_DEFAULT,
    ACTION_GESTURES,
    CID_BACK,
    CID_EXTRA,
    CID_FORWARD,
    CID_GESTURE,
    CID_MIDDLE,
    CID_MODE,
    REMAPPABLE_BUTTONS,
    button_label,
    buttons_from_profile,
    default_gesture_button_action,
    match_button_preset,
    preset_action,
)


def test_remappable_cids_cover_spike() -> None:
    cids = {b.cid for b in REMAPPABLE_BUTTONS}
    assert cids == {
        CID_MIDDLE,
        CID_BACK,
        CID_FORWARD,
        CID_GESTURE,
        CID_MODE,
        CID_EXTRA,
    }
    assert cids == {0x52, 0x53, 0x56, 0xC3, 0xC4, 0xD7}


def test_button_labels_bilingual() -> None:
    back = next(b for b in REMAPPABLE_BUTTONS if b.cid == CID_BACK)
    ru = button_label(back, lang="ru")
    en = button_label(back, lang="en")
    assert "0x53" in ru and "Назад" in ru and "Back" in ru
    assert "Back" in en and "0x53" in en


def test_match_presets() -> None:
    assert match_button_preset(None) == ACTION_DEFAULT
    assert match_button_preset({"type": "None"}) == "disable"
    assert (
        match_button_preset({"type": "Keypress", "keys": ["KEY_BACK"]})
        == "key_back"
    )
    assert match_button_preset({"type": "ToggleSmartShift"}) == "toggle_smartshift"
    assert match_button_preset({"type": "ChangeDPI", "inc": 50}) == "change_dpi_up"
    assert (
        match_button_preset({"type": "Gestures", "gestures": []})
        == ACTION_GESTURES
    )
    assert (
        match_button_preset(
            {"type": "Keypress", "keys": ["KEY_LEFTCTRL", "KEY_X"]}
        )
        == "key_custom"
    )


def test_preset_action_default_is_none() -> None:
    assert preset_action(ACTION_DEFAULT) is None
    assert preset_action("disable") == {"type": "None"}


def test_render_full_button_remap() -> None:
    gestures = default_gesture_button_action(
        {
            "Up": {"type": "Keypress", "keys": ["KEY_LEFTMETA", "KEY_UP"]},
            "Down": {"type": "None"},
            "Left": {
                "type": "CycleDPI",
                "dpis": [400, 800, 1200],
            },
            "Right": {"type": "ToggleSmartShift"},
            "None": {"type": "Keypress", "keys": ["KEY_LEFTMETA"]},
        }
    )
    profile = {
        "device": {"name": "MX Master 3S"},
        "dpi": 1000,
        "buttons": [
            {"cid": CID_GESTURE, "label": "gesture", "action": gestures},
            {
                "cid": CID_MODE,
                "label": "mode",
                "action": {"type": "ToggleSmartShift"},
            },
            {
                "cid": CID_FORWARD,
                "label": "forward",
                "action": {"type": "Keypress", "keys": ["KEY_FORWARD"]},
            },
            {
                "cid": CID_BACK,
                "label": "back",
                "action": {"type": "Keypress", "keys": ["KEY_BACK"]},
            },
            {
                "cid": CID_MIDDLE,
                "label": "middle",
                "action": {"type": "ChangeDPI", "inc": 50},
            },
            {
                "cid": CID_EXTRA,
                "label": "extra",
                "action": {"type": "None"},
            },
        ],
    }
    text = CfgWriter(profile).render()
    assert "cid: 0xc3;" in text
    assert 'type: "Gestures";' in text
    assert "cid: 0xc4;" in text
    assert 'type: "ToggleSmartShift";' in text
    assert "cid: 0x56;" in text
    assert "cid: 0x53;" in text
    assert "cid: 0x52;" in text
    assert 'type: "ChangeDPI";' in text
    assert "inc: 50;" in text
    assert "cid: 0xd7;" in text
    assert 'type: "None";' in text


def test_buttons_from_profile() -> None:
    profile = {
        "buttons": [
            {"cid": "0x53", "action": {"type": "Keypress", "keys": ["KEY_BACK"]}},
            {"cid": 0xC4, "action": {"type": "ToggleSmartShift"}},
        ]
    }
    mapped = buttons_from_profile(profile)
    assert CID_BACK in mapped
    assert CID_MODE in mapped
    assert match_button_preset(mapped[CID_BACK]) == "key_back"
