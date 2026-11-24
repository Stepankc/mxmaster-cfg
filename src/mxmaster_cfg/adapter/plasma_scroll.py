# SPDX-License-Identifier: GPL-3.0-or-later
"""Plasma / libinput ScrollFactor helpers (Kubuntu / KDE).

HID++ ``0x2121`` has no Options+-style “lines per notch”. On Plasma 6 the
usable control is ``ScrollFactor`` in ``kcminputrc`` under nested
``Libinput/<vendor>/<product>/<name>`` groups (same as System Settings →
Mouse → Scroll speed). Writing it needs no divert and cannot orphan
``hiresscroll.target``.

Device ids are decimal (``0x046d`` → ``1133``, Bolt receiver ``0xc548`` →
``50504``) — matching KConfig keys Stepan already uses on the stand.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

LOGITECH_VENDOR_HEX = 0x046D
LOGITECH_VENDOR_DEC = 1133  # 0x046d

# Sensible GUI range (Plasma defaults ~1.0; Stepan’s Bolt stand uses 0.3).
SCROLL_FACTOR_MIN = 0.10
SCROLL_FACTOR_MAX = 2.00
SCROLL_FACTOR_DEFAULT = 1.00

_SKIP_NAME = re.compile(
    r"(Consumer Control|System Control|Keyboard|Headset|AVRCP)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ScrollTarget:
    """One libinput pointer that can hold a Plasma ScrollFactor."""

    vendor: int  # decimal, e.g. 1133
    product: int  # decimal, e.g. 50504
    name: str
    event_node: str | None = None

    @property
    def kconfig_groups(self) -> tuple[str, str, str, str]:
        return ("Libinput", str(self.vendor), str(self.product), self.name)

    def label(self) -> str:
        return f"{self.name} ({self.vendor}:{self.product})"


def xdg_config_home() -> Path:
    raw = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".config"


def kcminputrc_path() -> Path:
    return xdg_config_home() / "kcminputrc"


def _read_sysfs(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _find_id_file(device: Path, name: str) -> Path | None:
    for candidate in (
        device / "id" / name,
        device / name,
        device.parent / "id" / name,
    ):
        if candidate.is_file():
            return candidate
    # Walk up a few levels (input event → inputN → hid/usb).
    cur = device
    for _ in range(4):
        cur = cur.parent
        candidate = cur / "id" / name
        if candidate.is_file():
            return candidate
    return None


def _parse_hex_id(raw: str | None) -> int | None:
    if not raw:
        return None
    text = raw.strip().lower()
    try:
        if text.startswith("0x"):
            return int(text, 16)
        return int(text, 16)
    except ValueError:
        return None


def iter_sysfs_pointers() -> Iterable[ScrollTarget]:
    """Yield pointer-like input devices from ``/sys/class/input``."""
    root = Path("/sys/class/input")
    if not root.is_dir():
        return
    for event_link in sorted(root.glob("event*")):
        device = event_link / "device"
        if not device.exists():
            continue
        name = _read_sysfs(device / "name")
        if not name or _SKIP_NAME.search(name):
            continue
        # Prefer explicit mouse naming; also accept Logitech receivers that
        # expose a Mouse node (Bolt shows as "Logitech USB Receiver Mouse").
        udev_mouse = False
        # Some kernels expose capabilities/ids via uevent:
        uevent = _read_sysfs(device / "uevent") or ""
        if "ID_INPUT_MOUSE=1" in uevent:
            udev_mouse = True
        if not udev_mouse and "Mouse" not in name and "MX Master" not in name:
            continue
        vend_path = _find_id_file(device, "vendor")
        prod_path = _find_id_file(device, "product")
        vendor = _parse_hex_id(_read_sysfs(vend_path) if vend_path else None)
        product = _parse_hex_id(_read_sysfs(prod_path) if prod_path else None)
        if vendor is None or product is None:
            continue
        yield ScrollTarget(
            vendor=vendor,
            product=product,
            name=name,
            event_node=event_link.name,
        )


def list_logitech_scroll_targets() -> list[ScrollTarget]:
    """Logitech pointers suitable for Plasma ScrollFactor writes."""
    seen: set[tuple[int, int, str]] = set()
    out: list[ScrollTarget] = []
    for target in iter_sysfs_pointers():
        # sysfs id/vendor is hex without 0x → int(..., 16) == 1133 for Logitech.
        if target.vendor != LOGITECH_VENDOR_DEC:
            continue
        key = (target.vendor, target.product, target.name)
        if key in seen:
            continue
        seen.add(key)
        out.append(target)
    return out


def _kreadconfig_bin() -> str | None:
    return shutil.which("kreadconfig6") or shutil.which("kreadconfig5")


def _kwriteconfig_bin() -> str | None:
    return shutil.which("kwriteconfig6") or shutil.which("kwriteconfig5")


def read_scroll_factor(target: ScrollTarget) -> float | None:
    """Read ScrollFactor for ``target``; ``None`` if unset / tools missing."""
    binary = _kreadconfig_bin()
    if not binary:
        return _read_scroll_factor_file(kcminputrc_path(), target)
    cmd = [binary, "--file", "kcminputrc"]
    for group in target.kconfig_groups:
        cmd.extend(["--group", group])
    cmd.extend(["--key", "ScrollFactor"])
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return _read_scroll_factor_file(kcminputrc_path(), target)
    raw = (proc.stdout or "").strip()
    if not raw:
        return _read_scroll_factor_file(kcminputrc_path(), target)
    try:
        return float(raw)
    except ValueError:
        return None


def _group_header(target: ScrollTarget) -> str:
    return "[%s]" % "][".join(target.kconfig_groups)


def _read_scroll_factor_file(path: Path, target: ScrollTarget) -> float | None:
    if not path.is_file():
        return None
    header = _group_header(target)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    in_group = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_group = stripped == header
            continue
        if not in_group or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        if key.strip() == "ScrollFactor":
            try:
                return float(value.strip())
            except ValueError:
                return None
    return None


def write_scroll_factor(
    target: ScrollTarget,
    factor: float,
    *,
    notify: bool = True,
) -> None:
    """Write ScrollFactor for one device (clamped). Prefer kwriteconfig --notify."""
    value = max(SCROLL_FACTOR_MIN, min(SCROLL_FACTOR_MAX, float(factor)))
    # Keep a short decimal string (Plasma uses e.g. 0.3).
    text = ("%g" % round(value, 3))
    binary = _kwriteconfig_bin()
    if binary:
        cmd = [binary, "--file", "kcminputrc"]
        for group in target.kconfig_groups:
            cmd.extend(["--group", group])
        cmd.extend(["--key", "ScrollFactor"])
        if notify:
            cmd.append("--notify")
        cmd.append(text)
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=5)
        return
    _write_scroll_factor_file(kcminputrc_path(), target, value)


def _write_scroll_factor_file(
    path: Path, target: ScrollTarget, factor: float
) -> None:
    header = _group_header(target)
    text_value = "%g" % round(float(factor), 3)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        lines = path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []
    out: list[str] = []
    in_group = False
    group_found = False
    key_written = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_group and not key_written:
                out.append(f"ScrollFactor={text_value}")
                key_written = True
            in_group = stripped == header
            if in_group:
                group_found = True
            out.append(line)
            continue
        if in_group and stripped.startswith("ScrollFactor="):
            out.append(f"ScrollFactor={text_value}")
            key_written = True
            continue
        out.append(line)
    if in_group and not key_written:
        out.append(f"ScrollFactor={text_value}")
        key_written = True
    if not group_found:
        if out and out[-1].strip():
            out.append("")
        out.append(header)
        out.append(f"ScrollFactor={text_value}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def primary_scroll_factor(
    targets: list[ScrollTarget] | None = None,
) -> tuple[ScrollTarget | None, float | None]:
    """Best Logitech mouse target + its factor (unset → default 1.0)."""
    items = targets if targets is not None else list_logitech_scroll_targets()
    if not items:
        return None, None
    # Prefer an explicit Mouse node over generic names.
    items_sorted = sorted(
        items,
        key=lambda t: (0 if "Mouse" in t.name else 1, t.name),
    )
    target = items_sorted[0]
    factor = read_scroll_factor(target)
    if factor is None:
        factor = SCROLL_FACTOR_DEFAULT
    return target, factor


def apply_scroll_factor(
    factor: float,
    *,
    targets: list[ScrollTarget] | None = None,
    notify: bool = True,
) -> list[ScrollTarget]:
    """Write the same ScrollFactor to all discovered Logitech pointers."""
    items = targets if targets is not None else list_logitech_scroll_targets()
    written: list[ScrollTarget] = []
    for target in items:
        write_scroll_factor(target, factor, notify=notify)
        written.append(target)
    return written
