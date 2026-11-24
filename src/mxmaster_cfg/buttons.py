# SPDX-License-Identifier: GPL-3.0-or-later
"""Remappable button CIDs, labels (RU/EN), and action presets for MX Master 3S.

Spike (Bolt) remappable CIDs: ``0x52 0x53 0x56 0xc3 0xc4 0xd7``.
Persistence is via logiops cfg (``CfgWriter``) + ``logid`` restart — not live
``Button.SetAction``.

Free-form Keypress and ChangeHost (host index / next / prev) are first-class
picker options; unknown Keypress/ChangeHost from cfg/profile load as custom
and round-trip through apply-cfg.
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
# Free-form Keypress (keys from editor / loaded unknown combo).
ACTION_KEY_CUSTOM = "key_custom"
# ChangeHost with host not covered by fixed channel presets.
ACTION_CHANGE_HOST_CUSTOM = "change_host_custom"

# Easy-Switch style channels (logiops host is 1-based in cfg).
CHANGE_HOST_CHANNELS = (1, 2, 3)

# Common KEY_* names for completer / docs (linux input-event-codes).
COMMON_KEY_NAMES: tuple[str, ...] = (
    "KEY_LEFTCTRL",
    "KEY_LEFTALT",
    "KEY_LEFTSHIFT",
    "KEY_LEFTMETA",
    "KEY_RIGHTCTRL",
    "KEY_RIGHTALT",
    "KEY_RIGHTSHIFT",
    "KEY_RIGHTMETA",
    "KEY_A",
    "KEY_B",
    "KEY_C",
    "KEY_D",
    "KEY_E",
    "KEY_F",
    "KEY_G",
    "KEY_H",
    "KEY_I",
    "KEY_J",
    "KEY_K",
    "KEY_L",
    "KEY_M",
    "KEY_N",
    "KEY_O",
    "KEY_P",
    "KEY_Q",
    "KEY_R",
    "KEY_S",
    "KEY_T",
    "KEY_U",
    "KEY_V",
    "KEY_W",
    "KEY_X",
    "KEY_Y",
    "KEY_Z",
    "KEY_0",
    "KEY_1",
    "KEY_2",
    "KEY_3",
    "KEY_4",
    "KEY_5",
    "KEY_6",
    "KEY_7",
    "KEY_8",
    "KEY_9",
    "KEY_F1",
    "KEY_F2",
    "KEY_F3",
    "KEY_F4",
    "KEY_F5",
    "KEY_F6",
    "KEY_F7",
    "KEY_F8",
    "KEY_F9",
    "KEY_F10",
    "KEY_F11",
    "KEY_F12",
    "KEY_TAB",
    "KEY_ENTER",
    "KEY_ESC",
    "KEY_SPACE",
    "KEY_BACKSPACE",
    "KEY_DELETE",
    "KEY_INSERT",
    "KEY_HOME",
    "KEY_END",
    "KEY_PAGEUP",
    "KEY_PAGEDOWN",
    "KEY_UP",
    "KEY_DOWN",
    "KEY_LEFT",
    "KEY_RIGHT",
    "KEY_BACK",
    "KEY_FORWARD",
    "KEY_MUTE",
    "KEY_VOLUMEUP",
    "KEY_VOLUMEDOWN",
    "KEY_PLAYPAUSE",
    "KEY_NEXTSONG",
    "KEY_PREVIOUSSONG",
    "KEY_STOPCD",
    "KEY_PRINT",
    "KEY_CAPSLOCK",
)


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


def normalize_key_token(token: str) -> str:
    """Normalize a typed key to ``KEY_*`` (uppercase)."""
    text = token.strip().upper().replace("-", "_").replace(" ", "_")
    if not text:
        return ""
    if text.startswith("KEY_"):
        return text
    # Bare letter/name → KEY_*
    return f"KEY_{text}"


def parse_keys_text(text: str) -> list[str]:
    """Parse free-form Keypress text (``+``, comma, whitespace separated)."""
    if not text or not str(text).strip():
        return []
    raw = str(text).replace("+", " ").replace(",", " ").replace(";", " ")
    out: list[str] = []
    for part in raw.split():
        key = normalize_key_token(part)
        if key:
            out.append(key)
    return out


def format_keys_text(keys: list[str] | tuple[str, ...] | None) -> str:
    """Display form for Keypress keys (``KEY_A + KEY_B``)."""
    if not keys:
        return ""
    return " + ".join(str(k) for k in keys)


def normalize_host(host: Any) -> int | str | None:
    """Normalize ChangeHost ``host`` to int (1-based) or next/prev."""
    if host is None:
        return None
    if isinstance(host, bool):
        return None
    if isinstance(host, int):
        return host
    if isinstance(host, float) and host == int(host):
        return int(host)
    if isinstance(host, str):
        text = host.strip().lower()
        if not text:
            return None
        if text in {"next"}:
            return "next"
        if text in {"prev", "previous"}:
            return "prev"
        if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
            return int(text)
        return text
    return None


def change_host_action(host: int | str) -> dict[str, Any]:
    return {"type": "ChangeHost", "host": normalize_host(host) or host}


def custom_keypress_action(keys: list[str] | None) -> dict[str, Any]:
    return {"type": "Keypress", "keys": list(keys or [])}


def change_host_preset_id(host: int | str | None) -> str:
    """Map a normalized host to a preset id."""
    h = normalize_host(host)
    if h in CHANGE_HOST_CHANNELS:
        return f"change_host_{h}"
    if h == "next":
        return "change_host_next"
    if h == "prev":
        return "change_host_prev"
    return ACTION_CHANGE_HOST_CUSTOM


# Preset id → (combo label RU/EN mix, profile action | None for Default).
# None action means omit from cfg (firmware default).
BUTTON_ACTION_PRESETS: list[tuple[str, str, dict[str, Any] | None]] = [
    (ACTION_DEFAULT, "По умолчанию (ОС / firmware)", None),
    ("disable", "Отключить (None)", {"type": "None"}),
    (
        ACTION_KEY_CUSTOM,
        "Keypress (записать… / record)",
        {"type": "Keypress", "keys": []},
    ),
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
        "change_host_1",
        "ChangeHost → канал / host 1",
        {"type": "ChangeHost", "host": 1},
    ),
    (
        "change_host_2",
        "ChangeHost → канал / host 2",
        {"type": "ChangeHost", "host": 2},
    ),
    (
        "change_host_3",
        "ChangeHost → канал / host 3",
        {"type": "ChangeHost", "host": 3},
    ),
    (
        "change_host_next",
        "ChangeHost next",
        {"type": "ChangeHost", "host": "next"},
    ),
    (
        "change_host_prev",
        "ChangeHost prev",
        {"type": "ChangeHost", "host": "prev"},
    ),
    (
        ACTION_CHANGE_HOST_CUSTOM,
        "ChangeHost (свой host…)",
        {"type": "ChangeHost", "host": 1},
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
    host = normalize_host(action.get("host"))
    return (kind, keys, dpis, inc, host)


def match_button_preset(action: dict[str, Any] | None) -> str:
    """Map a profile action to a preset id (best effort)."""
    if action is None:
        return ACTION_DEFAULT
    kind = action.get("type")
    if kind == "Gestures":
        return ACTION_GESTURES
    if kind == "ChangeHost":
        return change_host_preset_id(action.get("host"))
    sig = action_signature(action)
    for pid, _label, preset in BUTTON_ACTION_PRESETS:
        if preset is None:
            continue
        if pid in {ACTION_KEY_CUSTOM, ACTION_CHANGE_HOST_CUSTOM}:
            continue
        if action_signature(preset) == sig:
            return pid
    # Unknown Keypress / custom → free-form editor.
    if kind == "Keypress":
        return ACTION_KEY_CUSTOM
    if kind == "None":
        return "disable"
    return ACTION_DEFAULT


def resolve_button_action(
    preset_id: str,
    *,
    keys_text: str | None = None,
    custom_keys: list[str] | None = None,
    host: int | str | None = None,
    gesture_directions: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Build the profile action for a picker selection (UI model helper).

    Returns ``None`` for Default (omit from cfg). Empty custom Keypress still
    emits ``Keypress`` with ``keys: []`` so the choice round-trips.
    """
    if preset_id == ACTION_DEFAULT:
        return None
    if preset_id == ACTION_GESTURES:
        return default_gesture_button_action(gesture_directions or {})
    if preset_id == ACTION_KEY_CUSTOM:
        if custom_keys is not None:
            keys = list(custom_keys)
        else:
            keys = parse_keys_text(keys_text or "")
        return custom_keypress_action(keys)
    if preset_id == ACTION_CHANGE_HOST_CUSTOM:
        h = normalize_host(host)
        if h is None:
            h = 1
        return change_host_action(h)
    if preset_id.startswith("change_host_"):
        base = preset_action(preset_id)
        if base is not None:
            return base
    action = preset_action(preset_id)
    if action is None:
        return None
    return action


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
