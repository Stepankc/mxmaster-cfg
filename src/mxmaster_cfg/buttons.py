# SPDX-License-Identifier: GPL-3.0-or-later
"""Remappable button CIDs, labels (RU/EN), and action presets for MX Master 3S.

Spike (Bolt) remappable CIDs: ``0x52 0x53 0x56 0xc3 0xc4 0xd7``.
Persistence is via logiops cfg (``CfgWriter``) + ``logid`` restart — not live
``Button.SetAction``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Observed on MX Master 3S (Bolt) — remappable via HID++ ReprogControls.
CID_MIDDLE = 0x52
CID_BACK = 0x53
CID_FORWARD = 0x56
CID_GESTURE = 0xC3
CID_MODE = 0xC4
CID_EXTRA = 0xD7

CYCLE_DPI_LIST = [400, 600, 800, 1000, 1200, 1400, 1600]
CHANGE_DPI_STEP = 50

# Sentinel: omit button from cfg → firmware / OS default (not diverted).
ACTION_DEFAULT = "__default__"
# Sentinel: keep Gestures action; directions edited separately.
ACTION_GESTURES = "__gestures__"


@dataclass(frozen=True)
class ButtonInfo:
    cid: int
    key: str
    label_en: str
    label_ru: str
    # Default GUI preset id when starting fresh / missing from profile.
    default_preset: str
    # Whether this CID typically uses Gestures (direction grid).
    supports_gestures: bool = False


# Order matches typical MX Master 3S layout / spike listing.
REMAPPABLE_BUTTONS: tuple[ButtonInfo, ...] = (
    ButtonInfo(
        CID_MIDDLE,
        "middle",
        "Middle",
        "Средняя",
        ACTION_DEFAULT,
    ),
    ButtonInfo(
        CID_BACK,
        "back",
        "Back",
        "Назад",
        "key_back",
    ),
    ButtonInfo(
        CID_FORWARD,
        "forward",
        "Forward",
        "Вперёд",
        "key_forward",
    ),
    ButtonInfo(
        CID_GESTURE,
        "gesture",
        "Gesture",
        "Жесты",
        ACTION_GESTURES,
        supports_gestures=True,
    ),
    ButtonInfo(
        CID_MODE,
        "mode",
        "Mode / SmartShift",
        "Режим / SmartShift",
        "toggle_smartshift",
    ),
    ButtonInfo(
        CID_EXTRA,
        "extra",
        "Extra",
        "Доп.",
        ACTION_DEFAULT,
    ),
)


def button_by_cid(cid: int) -> ButtonInfo | None:
    for info in REMAPPABLE_BUTTONS:
        if info.cid == cid:
            return info
    return None


def button_label(info: ButtonInfo, *, lang: str = "ru") -> str:
    """Human label with hex CID, e.g. ``Назад / Back (0x53)``."""
    if lang == "en":
        return f"{info.label_en} ({hex(info.cid)})"
    return f"{info.label_ru} / {info.label_en} ({hex(info.cid)})"


def _copy_action(action: dict[str, Any]) -> dict[str, Any]:
    out = dict(action)
    if "keys" in out:
        out["keys"] = list(out["keys"])
    if "dpis" in out:
        out["dpis"] = list(out["dpis"])
    return out


# Preset id → (combo label RU, profile action | None for Default).
# None action means omit from cfg (firmware default).
BUTTON_ACTION_PRESETS: list[tuple[str, str, dict[str, Any] | None]] = [
    (ACTION_DEFAULT, "По умолчанию (ОС / firmware)", None),
    ("disable", "Отключить (None)", {"type": "None"}),
    (
        "key_forward",
        "Keypress KEY_FORWARD",
        {"type": "Keypress", "keys": ["KEY_FORWARD"]},
    ),
    (
        "key_back",
        "Keypress KEY_BACK",
        {"type": "Keypress", "keys": ["KEY_BACK"]},
    ),
    (
        "key_meta",
        "Keypress Super (Meta)",
        {"type": "Keypress", "keys": ["KEY_LEFTMETA"]},
    ),
    (
        "key_alt_tab",
        "Keypress Alt+Tab",
        {"type": "Keypress", "keys": ["KEY_LEFTALT", "KEY_TAB"]},
    ),
    (
        "key_meta_tab",
        "Keypress Super+Tab",
        {"type": "Keypress", "keys": ["KEY_LEFTMETA", "KEY_TAB"]},
    ),
    (
        "key_ctrl_c",
        "Keypress Ctrl+C",
        {"type": "Keypress", "keys": ["KEY_LEFTCTRL", "KEY_C"]},
    ),
    (
        "key_ctrl_v",
        "Keypress Ctrl+V",
        {"type": "Keypress", "keys": ["KEY_LEFTCTRL", "KEY_V"]},
    ),
    (
        "key_ctrl_z",
        "Keypress Ctrl+Z",
        {"type": "Keypress", "keys": ["KEY_LEFTCTRL", "KEY_Z"]},
    ),
    (
        "key_mute",
        "Keypress KEY_MUTE",
        {"type": "Keypress", "keys": ["KEY_MUTE"]},
    ),
    (
        "key_playpause",
        "Keypress KEY_PLAYPAUSE",
        {"type": "Keypress", "keys": ["KEY_PLAYPAUSE"]},
    ),
    (
        "key_volup",
        "Keypress KEY_VOLUMEUP",
        {"type": "Keypress", "keys": ["KEY_VOLUMEUP"]},
    ),
    (
        "key_voldown",
        "Keypress KEY_VOLUMEDOWN",
        {"type": "Keypress", "keys": ["KEY_VOLUMEDOWN"]},
    ),
    (
        "key_pageup",
        "Keypress KEY_PAGEUP",
        {"type": "Keypress", "keys": ["KEY_PAGEUP"]},
    ),
    (
        "key_pagedown",
        "Keypress KEY_PAGEDOWN",
        {"type": "Keypress", "keys": ["KEY_PAGEDOWN"]},
    ),
    (
        "key_esc",
        "Keypress KEY_ESC",
        {"type": "Keypress", "keys": ["KEY_ESC"]},
    ),
    (
        "key_enter",
        "Keypress KEY_ENTER",
        {"type": "Keypress", "keys": ["KEY_ENTER"]},
    ),
    (
        "cycle_dpi",
        "CycleDPI 400…1600",
        {"type": "CycleDPI", "dpis": list(CYCLE_DPI_LIST)},
    ),
    (
        "change_dpi_up",
        f"ChangeDPI +{CHANGE_DPI_STEP}",
        {"type": "ChangeDPI", "inc": CHANGE_DPI_STEP},
    ),
    (
        "change_dpi_down",
        f"ChangeDPI -{CHANGE_DPI_STEP}",
        {"type": "ChangeDPI", "inc": -CHANGE_DPI_STEP},
    ),
    (
        "toggle_smartshift",
        "ToggleSmartShift",
        {"type": "ToggleSmartShift"},
    ),
    (
        "toggle_hires",
        "ToggleHiresScroll",
        {"type": "ToggleHiresScroll"},
    ),
    (
        ACTION_GESTURES,
        "Gesture mode (направления ниже)",
        {"type": "Gestures", "gestures": []},
    ),
]


def preset_ids() -> list[str]:
    return [pid for pid, _label, _act in BUTTON_ACTION_PRESETS]


def preset_label(preset_id: str) -> str:
    for pid, label, _act in BUTTON_ACTION_PRESETS:
        if pid == preset_id:
            return label
    return preset_id


def preset_action(preset_id: str) -> dict[str, Any] | None:
    """Return a fresh action dict, or ``None`` for Default (omit from cfg)."""
    for pid, _label, action in BUTTON_ACTION_PRESETS:
        if pid == preset_id:
            if action is None:
                return None
            return _copy_action(action)
    return None


def action_signature(action: dict[str, Any] | None) -> tuple[Any, ...]:
    if action is None:
        return ("__default__",)
    if not isinstance(action, dict):
        return ("None",)
    kind = action.get("type", "None")
    keys = tuple(action.get("keys") or [])
    dpis = tuple(action.get("dpis") or [])
    inc = action.get("inc")
    host = action.get("host")
    return (kind, keys, dpis, inc, host)


def match_button_preset(action: dict[str, Any] | None) -> str:
    """Map a profile action to a preset id (best effort)."""
    if action is None:
        return ACTION_DEFAULT
    kind = action.get("type")
    if kind == "Gestures":
        return ACTION_GESTURES
    sig = action_signature(action)
    for pid, _label, preset in BUTTON_ACTION_PRESETS:
        if preset is None:
            continue
        if action_signature(preset) == sig:
            return pid
    # Unknown Keypress / custom → closest Keypress display via synthetic id.
    if kind == "Keypress":
        return "key_custom"
    if kind == "None":
        return "disable"
    return ACTION_DEFAULT


def buttons_from_profile(profile: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """cid → action dict for each configured button."""
    out: dict[int, dict[str, Any]] = {}
    for button in profile.get("buttons") or []:
        if not isinstance(button, dict):
            continue
        cid = _norm_cid(button.get("cid"))
        if cid is None:
            continue
        action = button.get("action")
        if isinstance(action, dict):
            out[cid] = action
    return out


def _norm_cid(cid: Any) -> int | None:
    if isinstance(cid, int):
        return cid
    if isinstance(cid, str):
        text = cid.strip().lower()
        if text.startswith("0x"):
            return int(text, 16)
        if text.isdigit():
            return int(text)
    return None


def default_gesture_button_action(
    direction_actions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build Gestures action from direction → nested BasicAction map."""
    gestures: list[dict[str, Any]] = []
    for direction in ("Up", "Down", "Left", "Right", "None"):
        nested = direction_actions.get(direction) or {"type": "None"}
        gestures.append(
            {
                "direction": direction,
                "mode": "OnRelease",
                "action": _copy_action(nested),
            }
        )
    return {"type": "Gestures", "gestures": gestures}
