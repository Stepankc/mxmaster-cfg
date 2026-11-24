# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from mxmaster_cfg.adapter.logiops_cfg import CfgWriter
from mxmaster_cfg.buttons import (
    ACTION_CHANGE_HOST_CUSTOM,
    ACTION_DEFAULT,
    ACTION_GESTURES,
    ACTION_KEY_CUSTOM,
    CID_BACK,
    CID_EXTRA,
    CID_FORWARD,
    CID_GESTURE,
    CID_MIDDLE,
    CID_MODE,
    REMAPPABLE_BUTTONS,
    button_label,
    buttons_from_profile,
    change_host_preset_id,
    default_gesture_button_action,
    format_keys_text,
    match_button_preset,
    normalize_host,
    parse_keys_text,
    preset_action,
    resolve_button_action,
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
        == ACTION_KEY_CUSTOM
    )


def test_parse_and_format_keys() -> None:
    assert parse_keys_text("KEY_LEFTCTRL + KEY_X") == [
        "KEY_LEFTCTRL",
        "KEY_X",
    ]
    assert parse_keys_text("ctrl, x") == ["KEY_CTRL", "KEY_X"]
    assert parse_keys_text("  ") == []
    assert format_keys_text(["KEY_LEFTALT", "KEY_TAB"]) == (
        "KEY_LEFTALT + KEY_TAB"
    )


def test_change_host_normalize_and_match() -> None:
    assert normalize_host(2) == 2
    assert normalize_host("previous") == "prev"
    assert normalize_host("NEXT") == "next"
    assert change_host_preset_id(1) == "change_host_1"
    assert change_host_preset_id("next") == "change_host_next"
    assert change_host_preset_id("prev") == "change_host_prev"
    assert change_host_preset_id(4) == ACTION_CHANGE_HOST_CUSTOM
    assert match_button_preset({"type": "ChangeHost", "host": 2}) == (
        "change_host_2"
    )
    assert match_button_preset(
        {"type": "ChangeHost", "host": "previous"}
    ) == "change_host_prev"
    assert match_button_preset({"type": "ChangeHost", "host": 9}) == (
        ACTION_CHANGE_HOST_CUSTOM
    )


def test_resolve_button_action_ui_model() -> None:
    assert resolve_button_action(ACTION_DEFAULT) is None
    custom = resolve_button_action(
        ACTION_KEY_CUSTOM, keys_text="KEY_LEFTCTRL+KEY_X"
    )
    assert custom == {
        "type": "Keypress",
        "keys": ["KEY_LEFTCTRL", "KEY_X"],
    }
    host = resolve_button_action("change_host_next")
    assert host == {"type": "ChangeHost", "host": "next"}
    custom_host = resolve_button_action(
        ACTION_CHANGE_HOST_CUSTOM, host="previous"
    )
    assert custom_host == {"type": "ChangeHost", "host": "prev"}


def test_preset_action_default_is_none() -> None:
    assert preset_action(ACTION_DEFAULT) is None
    assert preset_action("disable") == {"type": "None"}
    assert preset_action("change_host_1") == {
        "type": "ChangeHost",
        "host": 1,
    }


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


def test_render_custom_keypress_and_changehost() -> None:
    profile = {
        "device": {"name": "MX Master 3S"},
        "buttons": [
            {
                "cid": CID_EXTRA,
                "action": {
                    "type": "Keypress",
                    "keys": ["KEY_LEFTCTRL", "KEY_X"],
                },
            },
            {
                "cid": CID_MODE,
                "action": {"type": "ChangeHost", "host": 2},
            },
            {
                "cid": CID_MIDDLE,
                "action": {"type": "ChangeHost", "host": "next"},
            },
        ],
    }
    text = CfgWriter(profile).render()
    assert "cid: 0xd7;" in text
    assert 'type: "Keypress";' in text
    assert '"KEY_LEFTCTRL"' in text
    assert '"KEY_X"' in text
    assert "cid: 0xc4;" in text
    assert 'type: "ChangeHost";' in text
    assert "host: 2;" in text
    assert "cid: 0x52;" in text
    assert 'host: "next";' in text

    # Round-trip: match → resolve → same signature for writer.
    mapped = buttons_from_profile(profile)
    rebuilt: list[dict] = []
    for cid, act in mapped.items():
        preset = match_button_preset(act)
        if preset == ACTION_KEY_CUSTOM:
            out = resolve_button_action(
                preset, custom_keys=list(act.get("keys") or [])
            )
        elif preset == ACTION_CHANGE_HOST_CUSTOM:
            out = resolve_button_action(preset, host=act.get("host"))
        else:
            out = resolve_button_action(preset, host=act.get("host"))
        assert out is not None
        rebuilt.append({"cid": cid, "action": out})
    again = CfgWriter(
        {"device": {"name": "MX Master 3S"}, "buttons": rebuilt}
    ).render()
    assert 'type: "Keypress";' in again
    assert "host: 2;" in again
    assert 'host: "next";' in again


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
