# SPDX-License-Identifier: GPL-3.0-or-later
"""Bolt status flicker helpers: keep last good device, gate auto-wake.

After ``wake-receiver`` / ``logid`` restart the D-Bus device tree can briefly
list MX Master and then go empty for a few seconds. The GUI must not wipe a
fresh good snapshot on a soft miss, and must not hammer USB ``authorized``
(wake-race).
"""

from __future__ import annotations

from typing import Any

# How long to keep showing the last successful status when polls return 0.
LAST_GOOD_HOLD_S = 90.0
# Minimum gap between automatic wake-receiver attempts.
AUTO_WAKE_COOLDOWN_S = 45.0
# Delay before first full status after USB wake (let logid settle).
WAKE_SETTLE_MS = 2_500


def device_dicts(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Full device info dicts only (ignore wake-receiver path-string lists)."""
    if not isinstance(data, dict):
        return []
    out: list[dict[str, Any]] = []
    for item in data.get("devices") or []:
        if isinstance(item, dict) and (item.get("path") or item.get("name")):
            out.append(item)
    return out


def should_hold_last_good(
    *,
    has_devices: bool,
    last_good: dict[str, Any] | None,
    last_good_mono: float,
    now_mono: float,
    hold_s: float = LAST_GOOD_HOLD_S,
) -> bool:
    """True when an empty poll should keep the previous device snapshot."""
    if has_devices:
        return False
    if not isinstance(last_good, dict) or not device_dicts(last_good):
        return False
    if last_good_mono <= 0:
        return False
    return (now_mono - last_good_mono) <= hold_s


def should_auto_wake(
    *,
    has_devices: bool,
    now_mono: float,
    last_wake_mono: float,
    cooldown_s: float = AUTO_WAKE_COOLDOWN_S,
    blocked: bool = False,
) -> bool:
    """True when count=0 and cooldown allows a soft USB wake."""
    if has_devices or blocked:
        return False
    if last_wake_mono <= 0:
        return True
    return (now_mono - last_wake_mono) >= cooldown_s


def soft_miss_quirk(age_s: float) -> str:
    return (
        "Временно нет в D-Bus — держим последний снимок "
        "(~%.0f с назад). Опрос… / пошевелите мышь."
        % max(0.0, age_s)
    )
