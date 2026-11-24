# SPDX-License-Identifier: GPL-3.0-or-later
"""Bolt status flicker helpers: keep last good device, gate auto-wake.

After ``wake-receiver`` / ``logid`` restart the D-Bus device tree can briefly
list MX Master and then go empty for a few seconds. The GUI must not wipe a
fresh good snapshot on a soft miss, and must not hammer USB ``authorized``
(wake-race).

Hardening: while ``logid`` is still active, soft empty polls never clear the
last-good labels — only refresh the quirk / reconnect / auto-wake path.
"""

from __future__ import annotations

from typing import Any

# How long the soft-miss quirk shows a short “~N s ago” hold window.
LAST_GOOD_HOLD_S = 180.0
# Minimum gap between automatic wake-receiver attempts.
AUTO_WAKE_COOLDOWN_S = 45.0
# Delay before first full status after USB wake (let logid settle).
WAKE_SETTLE_MS = 3_000


def device_dicts(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Full device info dicts only (ignore wake-receiver path-string lists)."""
    if not isinstance(data, dict):
        return []
    out: list[dict[str, Any]] = []
    for item in data.get("devices") or []:
        if isinstance(item, dict) and (item.get("path") or item.get("name")):
            out.append(item)
    return out


def _logid_active(data: dict[str, Any] | None) -> bool | None:
    if not isinstance(data, dict):
        return None
    if "logid_active" not in data:
        return None
    return bool(data.get("logid_active"))


def should_hold_last_good(
    *,
    has_devices: bool,
    last_good: dict[str, Any] | None,
    last_good_mono: float,
    now_mono: float,
    hold_s: float = LAST_GOOD_HOLD_S,
    logid_active: bool | None = None,
    empty_poll: dict[str, Any] | None = None,
) -> bool:
    """True when an empty poll should keep the previous device snapshot.

    Soft empty while logid is (or was) active always holds when we have a
    last-good snapshot — do not clear labels just because the timed window
    expired.
    """
    if has_devices:
        return False
    if not isinstance(last_good, dict) or not device_dicts(last_good):
        return False
    if last_good_mono <= 0:
        return False

    active = logid_active
    if active is None and empty_poll is not None:
        active = _logid_active(empty_poll)
    # Soft empty + daemon up → keep forever (until a real device returns or
    # logid itself goes down).
    if active is True:
        return True
    # Unknown / inactive: still keep within the timed window.
    return (now_mono - last_good_mono) <= hold_s


def should_clear_device_labels(
    *,
    has_devices: bool,
    last_good: dict[str, Any] | None,
    last_good_mono: float,
    now_mono: float,
    hold_s: float = LAST_GOOD_HOLD_S,
    logid_active: bool | None = None,
    empty_poll: dict[str, Any] | None = None,
) -> bool:
    """True only when UI may wipe name/path/battery after an empty poll."""
    if has_devices:
        return False
    return not should_hold_last_good(
        has_devices=False,
        last_good=last_good,
        last_good_mono=last_good_mono,
        now_mono=now_mono,
        hold_s=hold_s,
        logid_active=logid_active,
        empty_poll=empty_poll,
    )


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
