# SPDX-License-Identifier: GPL-3.0-or-later
"""Map Qt key events → logiops ``KEY_*`` chord lists (no widgets).

Used by the Keypress capture UI. Esc is handled by the widget (cancel);
this module only converts a finished press into linux input-event names.
"""

from __future__ import annotations

from typing import Iterable

# Qt.Key_* integer values (stable across PySide6 versions we care about).
# Kept as plain ints so unit tests need no QApplication / display.
_QT_KEY = {
    "Escape": 0x01000000,
    "Tab": 0x01000001,
    "Backspace": 0x01000003,
    "Return": 0x01000004,
    "Enter": 0x01000005,
    "Insert": 0x01000006,
    "Delete": 0x01000007,
    "Pause": 0x01000008,
    "Print": 0x01000009,
    "Home": 0x01000010,
    "End": 0x01000011,
    "Left": 0x01000012,
    "Up": 0x01000013,
    "Right": 0x01000014,
    "Down": 0x01000015,
    "PageUp": 0x01000016,
    "PageDown": 0x01000017,
    "Shift": 0x01000020,
    "Control": 0x01000021,
    "Meta": 0x01000022,
    "Alt": 0x01000023,
    "CapsLock": 0x01000024,
    "NumLock": 0x01000025,
    "ScrollLock": 0x01000026,
    "F1": 0x01000030,
    "F2": 0x01000031,
    "F3": 0x01000032,
    "F4": 0x01000033,
    "F5": 0x01000034,
    "F6": 0x01000035,
    "F7": 0x01000036,
    "F8": 0x01000037,
    "F9": 0x01000038,
    "F10": 0x01000039,
    "F11": 0x0100003A,
    "F12": 0x0100003B,
    "Super_L": 0x01000053,
    "Super_R": 0x01000054,
    "Menu": 0x01000055,
    "Space": 0x20,
}

# Qt.KeyboardModifier bit flags (Qt::KeyboardModifier).
_MOD_SHIFT = 0x02000000
_MOD_CTRL = 0x04000000
_MOD_ALT = 0x08000000
_MOD_META = 0x10000000

_MODIFIER_KEYS = {
    _QT_KEY["Shift"],
    _QT_KEY["Control"],
    _QT_KEY["Meta"],
    _QT_KEY["Alt"],
    _QT_KEY["Super_L"],
    _QT_KEY["Super_R"],
    _QT_KEY["CapsLock"],
    _QT_KEY["NumLock"],
    _QT_KEY["ScrollLock"],
}

_SPECIAL: dict[int, str] = {
    _QT_KEY["Escape"]: "KEY_ESC",
    _QT_KEY["Tab"]: "KEY_TAB",
    _QT_KEY["Backspace"]: "KEY_BACKSPACE",
    _QT_KEY["Return"]: "KEY_ENTER",
    _QT_KEY["Enter"]: "KEY_ENTER",
    _QT_KEY["Insert"]: "KEY_INSERT",
    _QT_KEY["Delete"]: "KEY_DELETE",
    _QT_KEY["Pause"]: "KEY_PAUSE",
    _QT_KEY["Print"]: "KEY_PRINT",
    _QT_KEY["Home"]: "KEY_HOME",
    _QT_KEY["End"]: "KEY_END",
    _QT_KEY["Left"]: "KEY_LEFT",
    _QT_KEY["Up"]: "KEY_UP",
    _QT_KEY["Right"]: "KEY_RIGHT",
    _QT_KEY["Down"]: "KEY_DOWN",
    _QT_KEY["PageUp"]: "KEY_PAGEUP",
    _QT_KEY["PageDown"]: "KEY_PAGEDOWN",
    _QT_KEY["CapsLock"]: "KEY_CAPSLOCK",
    _QT_KEY["NumLock"]: "KEY_NUMLOCK",
    _QT_KEY["ScrollLock"]: "KEY_SCROLLLOCK",
    _QT_KEY["Space"]: "KEY_SPACE",
    _QT_KEY["Menu"]: "KEY_MENU",
    _QT_KEY["F1"]: "KEY_F1",
    _QT_KEY["F2"]: "KEY_F2",
    _QT_KEY["F3"]: "KEY_F3",
    _QT_KEY["F4"]: "KEY_F4",
    _QT_KEY["F5"]: "KEY_F5",
    _QT_KEY["F6"]: "KEY_F6",
    _QT_KEY["F7"]: "KEY_F7",
    _QT_KEY["F8"]: "KEY_F8",
    _QT_KEY["F9"]: "KEY_F9",
    _QT_KEY["F10"]: "KEY_F10",
    _QT_KEY["F11"]: "KEY_F11",
    _QT_KEY["F12"]: "KEY_F12",
    # Digits / ASCII punctuation that logiops commonly accepts.
    ord("0"): "KEY_0",
    ord("1"): "KEY_1",
    ord("2"): "KEY_2",
    ord("3"): "KEY_3",
    ord("4"): "KEY_4",
    ord("5"): "KEY_5",
    ord("6"): "KEY_6",
    ord("7"): "KEY_7",
    ord("8"): "KEY_8",
    ord("9"): "KEY_9",
    ord("-"): "KEY_MINUS",
    ord("="): "KEY_EQUAL",
    ord("["): "KEY_LEFTBRACE",
    ord("]"): "KEY_RIGHTBRACE",
    ord("\\"): "KEY_BACKSLASH",
    ord(";"): "KEY_SEMICOLON",
    ord("'"): "KEY_APOSTROPHE",
    ord("`"): "KEY_GRAVE",
    ord(","): "KEY_COMMA",
    ord("."): "KEY_DOT",
    ord("/"): "KEY_SLASH",
}


def is_modifier_key(qt_key: int) -> bool:
    return int(qt_key) in _MODIFIER_KEYS


def is_escape_key(qt_key: int) -> bool:
    return int(qt_key) == _QT_KEY["Escape"]


def qt_key_to_linux_name(qt_key: int) -> str | None:
    """Map a Qt key code to a single ``KEY_*`` name (no modifiers)."""
    key = int(qt_key)
    if key in _SPECIAL:
        return _SPECIAL[key]
    # Qt uses Unicode for letters (A–Z = 0x41–0x5A).
    if ord("A") <= key <= ord("Z"):
        return f"KEY_{chr(key)}"
    if ord("a") <= key <= ord("z"):
        return f"KEY_{chr(key).upper()}"
    return None


def modifiers_to_linux_keys(modifiers: int) -> list[str]:
    """Held modifiers → left-side ``KEY_*`` list (logiops chord order)."""
    mods = int(modifiers)
    out: list[str] = []
    # Prefer LEFT* names — same as preset shortcuts in buttons.py.
    if mods & _MOD_CTRL:
        out.append("KEY_LEFTCTRL")
    if mods & _MOD_ALT:
        out.append("KEY_LEFTALT")
    if mods & _MOD_SHIFT:
        out.append("KEY_LEFTSHIFT")
    if mods & _MOD_META:
        out.append("KEY_LEFTMETA")
    return out


def chord_from_qt_key(
    qt_key: int,
    modifiers: int = 0,
) -> list[str] | None:
    """Build a Keypress ``keys`` list from one non-modifier key press.

    Returns ``None`` for Escape, pure modifiers, or unmapped keys.
    Modifier bits that duplicate the main key are stripped.
    """
    key = int(qt_key)
    if is_escape_key(key) or is_modifier_key(key):
        return None
    main = qt_key_to_linux_name(key)
    if main is None:
        return None
    mods = modifiers_to_linux_keys(modifiers)
    # Drop modifier entries that match the main key (rare).
    chord = [m for m in mods if m != main]
    chord.append(main)
    return chord


def chord_from_key_names(names: Iterable[str]) -> list[str]:
    """Normalize an already-known ``KEY_*`` list (load from profile)."""
    out: list[str] = []
    for name in names:
        text = str(name).strip().upper()
        if not text:
            continue
        if not text.startswith("KEY_"):
            text = f"KEY_{text}"
        out.append(text)
    return out
