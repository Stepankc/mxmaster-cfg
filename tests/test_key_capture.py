# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from mxmaster_cfg.adapter.logiops_cfg import CfgWriter
from mxmaster_cfg.buttons import (
    ACTION_KEY_CUSTOM,
    match_button_preset,
    resolve_button_action,
)
from mxmaster_cfg.key_capture import (
    chord_from_key_names,
    chord_from_qt_key,
    is_escape_key,
    is_modifier_key,
    modifiers_to_linux_keys,
    qt_key_to_linux_name,
)

# Qt.Key / KeyboardModifier integer values (no QApplication required).
_KEY_X = 0x58
_KEY_TAB = 0x01000001
_KEY_ESC = 0x01000000
_KEY_CONTROL = 0x01000021
_KEY_F5 = 0x01000034
_MOD_CTRL = 0x04000000
_MOD_ALT = 0x08000000
_MOD_SHIFT = 0x02000000
_MOD_META = 0x10000000


def test_qt_key_letters_and_specials() -> None:
    assert qt_key_to_linux_name(_KEY_X) == "KEY_X"
    assert qt_key_to_linux_name(_KEY_TAB) == "KEY_TAB"
    assert qt_key_to_linux_name(_KEY_F5) == "KEY_F5"
    assert is_escape_key(_KEY_ESC)
    assert is_modifier_key(_KEY_CONTROL)
    assert not is_modifier_key(_KEY_X)


def test_modifiers_to_linux_keys_order() -> None:
    assert modifiers_to_linux_keys(_MOD_CTRL | _MOD_SHIFT) == [
        "KEY_LEFTCTRL",
        "KEY_LEFTSHIFT",
    ]
    assert modifiers_to_linux_keys(_MOD_META | _MOD_ALT) == [
        "KEY_LEFTALT",
        "KEY_LEFTMETA",
    ]


def test_chord_from_qt_key_capture_model() -> None:
    assert chord_from_qt_key(_KEY_ESC) is None
    assert chord_from_qt_key(_KEY_CONTROL, _MOD_CTRL) is None
    assert chord_from_qt_key(_KEY_X, _MOD_CTRL) == [
        "KEY_LEFTCTRL",
        "KEY_X",
    ]
    assert chord_from_qt_key(_KEY_TAB, _MOD_ALT) == [
        "KEY_LEFTALT",
        "KEY_TAB",
    ]
    assert chord_from_qt_key(_KEY_X, 0) == ["KEY_X"]


def test_capture_chord_round_trips_cfg() -> None:
    chord = chord_from_qt_key(_KEY_X, _MOD_CTRL)
    assert chord is not None
    action = resolve_button_action(ACTION_KEY_CUSTOM, custom_keys=chord)
    assert action == {"type": "Keypress", "keys": chord}
    assert match_button_preset(action) == ACTION_KEY_CUSTOM
    text = CfgWriter(
        {
            "device": {"name": "MX Master 3S"},
            "buttons": [{"cid": 0xD7, "action": action}],
        }
    ).render()
    assert 'type: "Keypress";' in text
    assert '"KEY_LEFTCTRL"' in text
    assert '"KEY_X"' in text


def test_chord_from_key_names_normalizes() -> None:
    assert chord_from_key_names(["leftctrl", "x"]) == [
        "KEY_LEFTCTRL",
        "KEY_X",
    ]
