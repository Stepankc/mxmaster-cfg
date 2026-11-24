# SPDX-License-Identifier: GPL-3.0-or-later
"""Thumb wheel (0x2150) scroll / tap / touch / proxy model helpers.

Left/right gestures and tap/touch/proxy BasicActions round-trip through
profiles → ``CfgWriter`` → apply-cfg. Unknown Axis / OnInterval / Keypress
values load as custom editors (same idea as free-form button Keypress).
"""

from __future__ import annotations

from typing import Any

from mxmaster_cfg.buttons import (
    ACTION_KEY_CUSTOM,
    action_signature,
    custom_keypress_action,
    format_keys_text,
    parse_keys_text,
)

# Left/right scroll presets (shared combo; left mirrored for Axis / volume).
SCROLL_OMIT = "omit"
SCROLL_AXIS_HIRES = "axis_hires"
SCROLL_AXIS_HWHEEL = "axis_hwheel"
SCROLL_NOPRESS = "nopress"
SCROLL_VOLUME = "volume"
SCROLL_AXIS_CUSTOM = "axis_custom"
SCROLL_INTERVAL_KEY_CUSTOM = "interval_key_custom"

# tap / touch / proxy action presets.
THUMB_ACTION_OMIT = "omit"
THUMB_ACTION_NONE = "none"

COMMON_AXIS_NAMES: tuple[str, ...] = (
    "REL_HWHEEL",
    "REL_HWHEEL_HI_RES",
    "REL_WHEEL",
    "REL_WHEEL_HI_RES",
)

DEFAULT_CUSTOM_AXIS = "REL_HWHEEL_HI_RES"
DEFAULT_CUSTOM_MULTIPLIER = 1.0
DEFAULT_CUSTOM_INTERVAL = 2

_THUMB_VOL_KEYS = {
    "left": ["KEY_VOLUMEDOWN"],
    "right": ["KEY_VOLUMEUP"],
}

# (id, label, base gesture | None). None = omit sides (OS scroll).
THUMB_SCROLL_PRESETS: list[tuple[str, str, dict[str, Any] | None]] = [
    (SCROLL_OMIT, "ОС / не divert (omit)", None),
    (
        SCROLL_AXIS_HIRES,
        "Axis REL_HWHEEL_HI_RES",
        {
            "mode": "Axis",
            "axis": "REL_HWHEEL_HI_RES",
            "axis_multiplier": 1,
        },
    ),
    (
        SCROLL_AXIS_HWHEEL,
        "Axis REL_HWHEEL",
        {"mode": "Axis", "axis": "REL_HWHEEL", "axis_multiplier": 1},
    ),
    (SCROLL_NOPRESS, "Отключить (NoPress)", {"mode": "NoPress"}),
    (
        SCROLL_VOLUME,
        "Громкость (OnInterval)",
        {
            "mode": "OnInterval",
            "interval": 2,
            "action": {"type": "Keypress", "keys": ["KEY_VOLUMEUP"]},
        },
    ),
    (
        SCROLL_AXIS_CUSTOM,
        "Axis (свой… / custom)",
        {
            "mode": "Axis",
            "axis": DEFAULT_CUSTOM_AXIS,
            "axis_multiplier": DEFAULT_CUSTOM_MULTIPLIER,
        },
    ),
    (
        SCROLL_INTERVAL_KEY_CUSTOM,
        "OnInterval Keypress (свой…)",
        {
            "mode": "OnInterval",
            "interval": DEFAULT_CUSTOM_INTERVAL,
            "action": {"type": "Keypress", "keys": []},
        },
    ),
]

# (id, label, action | None). None = omit field from cfg.
THUMB_ACTION_PRESETS: list[tuple[str, str, dict[str, Any] | None]] = [
    (THUMB_ACTION_OMIT, "Нет (omit)", None),
    (THUMB_ACTION_NONE, "None (явный)", {"type": "None"}),
    (
        "key_mute",
        "KEY_MUTE",
        {"type": "Keypress", "keys": ["KEY_MUTE"]},
    ),
    (
        "key_playpause",
        "KEY_PLAYPAUSE",
        {"type": "Keypress", "keys": ["KEY_PLAYPAUSE"]},
    ),
    (
        "key_meta",
        "KEY_LEFTMETA",
        {"type": "Keypress", "keys": ["KEY_LEFTMETA"]},
    ),
    (
        ACTION_KEY_CUSTOM,
        "Keypress (свой… / custom)",
        {"type": "Keypress", "keys": []},
    ),
]


def _copy_gesture(gest: dict[str, Any]) -> dict[str, Any]:
    out = dict(gest)
    if "action" in out and isinstance(out["action"], dict):
        nested = dict(out["action"])
        if "keys" in nested:
            nested["keys"] = list(nested["keys"])
        out["action"] = nested
    return out


def _copy_action(action: dict[str, Any]) -> dict[str, Any]:
    out = dict(action)
    if "keys" in out:
        out["keys"] = list(out["keys"])
    return out


def normalize_axis_name(axis: str | None) -> str:
    text = (axis or "").strip()
    if not text:
        return DEFAULT_CUSTOM_AXIS
    return text


def normalize_multiplier(raw: Any, *, default: float = DEFAULT_CUSTOM_MULTIPLIER) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    if value == 0:
        return default
    return value


def normalize_interval(raw: Any, *, default: int = DEFAULT_CUSTOM_INTERVAL) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(1, value)


def scroll_preset_ids() -> list[str]:
    return [pid for pid, _label, _g in THUMB_SCROLL_PRESETS]


def thumb_action_preset_ids() -> list[str]:
    return [pid for pid, _label, _a in THUMB_ACTION_PRESETS]


def match_scroll_preset(thumb: dict[str, Any] | None) -> str:
    """Map profile thumbwheel left (preferred) to a scroll preset id."""
    if not isinstance(thumb, dict):
        return SCROLL_OMIT
    left = thumb.get("left")
    if not isinstance(left, dict):
        return SCROLL_OMIT
    mode = left.get("mode")
    axis = left.get("axis")
    for pid, _label, preset in THUMB_SCROLL_PRESETS:
        if preset is None or pid in {SCROLL_AXIS_CUSTOM, SCROLL_INTERVAL_KEY_CUSTOM}:
            continue
        if preset.get("mode") != mode:
            continue
        if mode == "Axis":
            if preset.get("axis") != axis:
                continue
            # Stock Axis presets use |multiplier| == 1; anything else → custom.
            left_mag = abs(normalize_multiplier(left.get("axis_multiplier"), default=1.0))
            preset_mag = abs(
                normalize_multiplier(preset.get("axis_multiplier"), default=1.0)
            )
            if abs(left_mag - preset_mag) > 1e-6:
                continue
            return pid
        if mode == "OnInterval":
            # Fixed volume preset only when keys are the stock volume pair
            # and interval matches.
            action = left.get("action") if isinstance(left.get("action"), dict) else {}
            keys = list((action or {}).get("keys") or [])
            iv = normalize_interval(left.get("interval"))
            preset_iv = normalize_interval(preset.get("interval"))
            if iv != preset_iv:
                continue
            if keys == _THUMB_VOL_KEYS["left"] or keys == ["KEY_VOLUMEUP"]:
                return SCROLL_VOLUME
            continue
        if mode == "NoPress":
            return pid
    if mode == "Axis":
        return SCROLL_AXIS_CUSTOM
    if mode == "OnInterval":
        return SCROLL_INTERVAL_KEY_CUSTOM
    # Unknown modes still surface as custom Axis so the user can re-save.
    return SCROLL_AXIS_CUSTOM


def match_thumb_action(action: Any) -> str:
    """Map tap/touch/proxy action to a preset id (unknown Keypress → custom)."""
    if not isinstance(action, dict):
        return THUMB_ACTION_OMIT
    sig = action_signature(action)
    for pid, _label, preset in THUMB_ACTION_PRESETS:
        if preset is None or pid == ACTION_KEY_CUSTOM:
            continue
        if action_signature(preset) == sig:
            return pid
    if action.get("type") == "Keypress":
        return ACTION_KEY_CUSTOM
    if action.get("type") in {"None", "none", None}:
        return THUMB_ACTION_NONE
    return ACTION_KEY_CUSTOM


def extract_custom_axis_fields(thumb: dict[str, Any] | None) -> tuple[str, float]:
    """Axis name + absolute multiplier from left (or right) gesture."""
    if not isinstance(thumb, dict):
        return DEFAULT_CUSTOM_AXIS, DEFAULT_CUSTOM_MULTIPLIER
    for side in ("left", "right"):
        gest = thumb.get(side)
        if not isinstance(gest, dict) or gest.get("mode") != "Axis":
            continue
        axis = normalize_axis_name(str(gest.get("axis") or DEFAULT_CUSTOM_AXIS))
        mult = abs(normalize_multiplier(gest.get("axis_multiplier")))
        return axis, mult
    return DEFAULT_CUSTOM_AXIS, DEFAULT_CUSTOM_MULTIPLIER


def extract_custom_interval_fields(
    thumb: dict[str, Any] | None,
) -> tuple[int, str]:
    """Interval + keys display text from left (or right) OnInterval gesture."""
    if not isinstance(thumb, dict):
        return DEFAULT_CUSTOM_INTERVAL, ""
    for side in ("left", "right"):
        gest = thumb.get(side)
        if not isinstance(gest, dict) or gest.get("mode") != "OnInterval":
            continue
        interval = normalize_interval(gest.get("interval"))
        action = gest.get("action") if isinstance(gest.get("action"), dict) else {}
        keys = list((action or {}).get("keys") or [])
        return interval, format_keys_text(keys)
    return DEFAULT_CUSTOM_INTERVAL, ""


def resolve_scroll_sides(
    preset_id: str,
    *,
    axis: str | None = None,
    multiplier: float | None = None,
    interval: int | None = None,
    keys_text: str | None = None,
    custom_keys: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build ``left`` / ``right`` gestures for the selected scroll preset.

    Returns an empty dict for omit. Axis custom mirrors multiplier sign
    (left negative, right positive). Volume / interval Keypress uses the
    same keys on both sides except the stock volume preset.
    """
    if preset_id == SCROLL_OMIT:
        return {}

    if preset_id == SCROLL_AXIS_CUSTOM:
        axis_name = normalize_axis_name(axis)
        mag = abs(normalize_multiplier(multiplier))
        mag_out: float | int
        if abs(mag - round(mag)) < 1e-9:
            mag_out = int(round(mag))
        else:
            mag_out = mag
        return {
            "left": {
                "mode": "Axis",
                "axis": axis_name,
                "axis_multiplier": -mag_out,
            },
            "right": {
                "mode": "Axis",
                "axis": axis_name,
                "axis_multiplier": mag_out,
            },
        }

    if preset_id == SCROLL_INTERVAL_KEY_CUSTOM:
        if custom_keys is not None:
            keys = list(custom_keys)
        else:
            keys = parse_keys_text(keys_text or "")
        iv = normalize_interval(interval)
        gest = {
            "mode": "OnInterval",
            "interval": iv,
            "action": custom_keypress_action(keys),
        }
        return {"left": _copy_gesture(gest), "right": _copy_gesture(gest)}

    base: dict[str, Any] | None = None
    for pid, _label, preset in THUMB_SCROLL_PRESETS:
        if pid == preset_id:
            base = None if preset is None else _copy_gesture(preset)
            break
    if base is None:
        return {}

    out: dict[str, dict[str, Any]] = {}
    for side in ("left", "right"):
        gest = _copy_gesture(base)
        if gest.get("mode") == "OnInterval":
            action = dict(gest.get("action") or {})
            if action.get("type") == "Keypress":
                action["keys"] = list(_THUMB_VOL_KEYS[side])
                gest["action"] = action
        elif gest.get("mode") == "Axis":
            mult = abs(normalize_multiplier(gest.get("axis_multiplier"), default=1.0))
            # Prefer ints when whole numbers (libconfig readability).
            if abs(mult - round(mult)) < 1e-9:
                mult_out: float | int = int(round(mult))
            else:
                mult_out = mult
            gest["axis_multiplier"] = -mult_out if side == "left" else mult_out
        out[side] = gest
    return out


def resolve_thumb_action(
    preset_id: str,
    *,
    keys_text: str | None = None,
    custom_keys: list[str] | None = None,
) -> dict[str, Any] | None:
    """Build tap/touch/proxy action; ``None`` means omit from cfg."""
    if preset_id == THUMB_ACTION_OMIT:
        return None
    if preset_id == ACTION_KEY_CUSTOM:
        if custom_keys is not None:
            keys = list(custom_keys)
        else:
            keys = parse_keys_text(keys_text or "")
        return custom_keypress_action(keys)
    for pid, _label, action in THUMB_ACTION_PRESETS:
        if pid == preset_id:
            if action is None:
                return None
            return _copy_action(action)
    return None


def build_thumbwheel(
    *,
    divert: bool,
    invert: bool,
    scroll_preset: str,
    tap_preset: str = THUMB_ACTION_OMIT,
    touch_preset: str = THUMB_ACTION_OMIT,
    proxy_preset: str = THUMB_ACTION_OMIT,
    axis: str | None = None,
    multiplier: float | None = None,
    interval: int | None = None,
    scroll_keys_text: str | None = None,
    scroll_keys: list[str] | None = None,
    tap_keys_text: str | None = None,
    tap_keys: list[str] | None = None,
    touch_keys_text: str | None = None,
    touch_keys: list[str] | None = None,
    proxy_keys_text: str | None = None,
    proxy_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Assemble a profile ``thumbwheel`` object from GUI / test inputs."""
    tw: dict[str, Any] = {"divert": divert, "invert": invert}
    if not divert:
        return tw

    sides = resolve_scroll_sides(
        scroll_preset,
        axis=axis,
        multiplier=multiplier,
        interval=interval,
        keys_text=scroll_keys_text,
        custom_keys=scroll_keys,
    )
    tw.update(sides)

    for field, preset, keys_text, keys in (
        ("tap", tap_preset, tap_keys_text, tap_keys),
        ("touch", touch_preset, touch_keys_text, touch_keys),
        ("proxy", proxy_preset, proxy_keys_text, proxy_keys),
    ):
        action = resolve_thumb_action(
            preset, keys_text=keys_text, custom_keys=keys
        )
        if action is None:
            continue
        # Empty custom Keypress is useless — skip rather than keys:[].
        if preset == ACTION_KEY_CUSTOM and not (action.get("keys") or []):
            continue
        tw[field] = action
    return tw
