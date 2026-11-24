# SPDX-License-Identifier: GPL-3.0-or-later
"""Plasma scroll speed helpers (Kubuntu / KDE Plasma 6).

HID++ ``0x2121`` has no Options+-style “lines per notch”. On Plasma the
usable control is ``scrollFactor``:

* **Wayland (this stand):** live property
  ``org.kde.KWin.InputDevice.scrollFactor`` on
  ``/org/kde/KWin/InputDevice/<eventN>``. Writing ``kcminputrc`` alone with
  ``kwriteconfig6 --notify`` does **not** update the running compositor —
  the slider must Set the D-Bus property.
* **Persistence:** same value under
  ``[Libinput][<vendor>][<product>][<name>]`` ``ScrollFactor=`` in
  ``~/.config/kcminputrc`` (matches System Settings → Mouse).

Device ids are decimal (``0x046d`` → ``1133``, Bolt ``0xc548`` → ``50504``).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

LOGITECH_VENDOR_DEC = 1133  # 0x046d

# Sensible GUI range (Plasma defaults ~1.0; Stepan’s Bolt stand uses ~0.3).
SCROLL_FACTOR_MIN = 0.10
SCROLL_FACTOR_MAX = 2.00
SCROLL_FACTOR_DEFAULT = 1.00

_KWIN_DEST = "org.kde.KWin"
_KWIN_MANAGER = "/org/kde/KWin/InputDevice"
_KWIN_IFACE = "org.kde.KWin.InputDevice"
_KWIN_MGR_IFACE = "org.kde.KWin.InputDeviceManager"

_SKIP_NAME = re.compile(
    r"(Consumer Control|System Control|Keyboard|Headset|AVRCP)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ScrollTarget:
    """One pointer that can hold a Plasma / KWin scrollFactor."""

    vendor: int  # decimal, e.g. 1133
    product: int  # decimal, e.g. 50504
    name: str
    event_node: str | None = None  # e.g. event8 (KWin sysName)

    @property
    def kconfig_groups(self) -> tuple[str, str, str, str]:
        return ("Libinput", str(self.vendor), str(self.product), self.name)

    def label(self) -> str:
        node = f" · {self.event_node}" if self.event_node else ""
        return f"{self.name} ({self.vendor}:{self.product}{node})"


def xdg_config_home() -> Path:
    raw = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".config"


def kcminputrc_path() -> Path:
    return xdg_config_home() / "kcminputrc"


def _clamp(factor: float) -> float:
    return max(SCROLL_FACTOR_MIN, min(SCROLL_FACTOR_MAX, float(factor)))


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
        uevent = _read_sysfs(device / "uevent") or ""
        udev_mouse = "ID_INPUT_MOUSE=1" in uevent
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


def _gdbus(*args: str, timeout: float = 5.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gdbus", *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _parse_gdbus_string_list(stdout: str) -> list[str]:
    # e.g. (['event4', 'event8'],) or (["event8"],)
    text = (stdout or "").strip()
    if not text.startswith("("):
        return []
    inner = text[1:]
    if inner.endswith(",)"):
        inner = inner[:-2]
    elif inner.endswith(")"):
        inner = inner[:-1]
    inner = inner.strip()
    if not (inner.startswith("[") and inner.endswith("]")):
        return []
    body = inner[1:-1].strip()
    if not body:
        return []
    out: list[str] = []
    for part in body.split(","):
        token = part.strip().strip("'\"")
        if token:
            out.append(token)
    return out


def _parse_gdbus_variant(stdout: str) -> str | None:
    # e.g. (<0.3>,)  (<true>,)  (<'name'>,)  (<uint32 50504>,)
    text = (stdout or "").strip()
    if not text.startswith("(<") or not text.endswith(">,)"):
        # Also accept (<…>,) without trailing comma variants
        if text.startswith("(") and text.endswith(")"):
            text = text[1:-1].strip()
            if text.startswith("<") and text.endswith(">"):
                return text[1:-1].strip()
        return None
    return text[2:-3].strip()


def _gdbus_get(sys_name: str, prop: str) -> str | None:
    path = f"{_KWIN_MANAGER}/{sys_name}"
    proc = _gdbus(
        "call",
        "--session",
        "--dest",
        _KWIN_DEST,
        "--object-path",
        path,
        "--method",
        "org.freedesktop.DBus.Properties.Get",
        _KWIN_IFACE,
        prop,
    )
    if proc.returncode != 0:
        return None
    return _parse_gdbus_variant(proc.stdout or "")


def _gdbus_set_double(sys_name: str, prop: str, value: float) -> bool:
    path = f"{_KWIN_MANAGER}/{sys_name}"
    # GVariant text format for a double inside the Set() variant arg.
    payload = f"<double {float(value):.10g}>"
    proc = _gdbus(
        "call",
        "--session",
        "--dest",
        _KWIN_DEST,
        "--object-path",
        path,
        "--method",
        "org.freedesktop.DBus.Properties.Set",
        _KWIN_IFACE,
        prop,
        payload,
    )
    return proc.returncode == 0


def list_kwin_pointers() -> list[ScrollTarget]:
    """Pointers exposed by KWin InputDeviceManager (Wayland live path)."""
    proc = _gdbus(
        "call",
        "--session",
        "--dest",
        _KWIN_DEST,
        "--object-path",
        _KWIN_MANAGER,
        "--method",
        f"{_KWIN_MGR_IFACE}.ListPointers",
    )
    if proc.returncode != 0:
        return []
    out: list[ScrollTarget] = []
    for sys_name in _parse_gdbus_string_list(proc.stdout or ""):
        name_raw = _gdbus_get(sys_name, "name")
        if not name_raw:
            continue
        name = name_raw.strip().strip("'\"")
        if not name or _SKIP_NAME.search(name):
            continue
        vend_raw = _gdbus_get(sys_name, "vendor")
        prod_raw = _gdbus_get(sys_name, "product")
        if not vend_raw or not prod_raw:
            continue
        try:
            # May be "1133" or "uint32 1133"
            vend_s = vend_raw.replace("uint32", "").replace("uint64", "").strip()
            prod_s = prod_raw.replace("uint32", "").replace("uint64", "").strip()
            vendor = int(vend_s)
            product = int(prod_s)
        except ValueError:
            continue
        out.append(
            ScrollTarget(
                vendor=vendor,
                product=product,
                name=name,
                event_node=sys_name,
            )
        )
    return out


def list_logitech_scroll_targets() -> list[ScrollTarget]:
    """Logitech pointers for ScrollFactor (prefer KWin nodes on Wayland)."""
    seen: set[tuple[int, int, str]] = set()
    out: list[ScrollTarget] = []

    def _add(target: ScrollTarget) -> None:
        if target.vendor != LOGITECH_VENDOR_DEC:
            return
        key = (target.vendor, target.product, target.name)
        if key in seen:
            # Prefer entry that has a KWin event node.
            if target.event_node:
                for idx, existing in enumerate(out):
                    if (
                        existing.vendor,
                        existing.product,
                        existing.name,
                    ) == key and not existing.event_node:
                        out[idx] = target
                        return
            return
        seen.add(key)
        out.append(target)

    for target in list_kwin_pointers():
        _add(target)
    for target in iter_sysfs_pointers():
        _add(target)
    return out


def read_kwin_scroll_factor(target: ScrollTarget) -> float | None:
    """Live KWin scrollFactor for ``target.event_node``, if available."""
    if not target.event_node:
        return None
    raw = _gdbus_get(target.event_node, "scrollFactor")
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def write_kwin_scroll_factor(target: ScrollTarget, factor: float) -> bool:
    """Set live Wayland scrollFactor. Returns True on success."""
    if not target.event_node:
        return False
    return _gdbus_set_double(target.event_node, "scrollFactor", _clamp(factor))


def _kreadconfig_bin() -> str | None:
    return shutil.which("kreadconfig6") or shutil.which("kreadconfig5")


def _kwriteconfig_bin() -> str | None:
    return shutil.which("kwriteconfig6") or shutil.which("kwriteconfig5")


def read_scroll_factor_file(target: ScrollTarget) -> float | None:
    """Read persisted ScrollFactor from kcminputrc."""
    binary = _kreadconfig_bin()
    if binary:
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
        if raw:
            try:
                return float(raw)
            except ValueError:
                pass
    return _read_scroll_factor_file(kcminputrc_path(), target)


# Back-compat alias used by tests / callers.
def read_scroll_factor(target: ScrollTarget) -> float | None:
    """Prefer live KWin value; fall back to kcminputrc."""
    live = read_kwin_scroll_factor(target)
    if live is not None:
        return live
    return read_scroll_factor_file(target)


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


def write_scroll_factor_file(
    target: ScrollTarget,
    factor: float,
    *,
    notify: bool = True,
) -> None:
    """Persist ScrollFactor to kcminputrc (does not update Wayland live)."""
    value = _clamp(factor)
    text = "%g" % round(value, 3)
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


def write_scroll_factor(
    target: ScrollTarget,
    factor: float,
    *,
    notify: bool = True,
) -> dict[str, bool]:
    """Persist + apply live KWin scrollFactor. Returns what succeeded."""
    value = _clamp(factor)
    file_ok = False
    live_ok = False
    try:
        write_scroll_factor_file(target, value, notify=notify)
        file_ok = True
    except (OSError, subprocess.SubprocessError):
        file_ok = False
    live_ok = write_kwin_scroll_factor(target, value)
    return {"file": file_ok, "kwin_live": live_ok}


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
    """Best Logitech mouse target + its factor (live KWin preferred)."""
    items = targets if targets is not None else list_logitech_scroll_targets()
    if not items:
        return None, None
    items_sorted = sorted(
        items,
        key=lambda t: (
            0 if t.event_node else 1,
            0 if "Mouse" in t.name else 1,
            t.name,
        ),
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
    """Write ScrollFactor to file + live KWin for all Logitech pointers.

    Raises ``RuntimeError`` if no target got a live KWin apply (Wayland
    session) and at least one target had an event node — so the GUI can
    surface a real failure instead of a silent no-op.
    """
    items = targets if targets is not None else list_logitech_scroll_targets()
    written: list[ScrollTarget] = []
    live_hits = 0
    live_attempts = 0
    for target in items:
        result = write_scroll_factor(target, factor, notify=notify)
        if result.get("file") or result.get("kwin_live"):
            written.append(target)
        if target.event_node:
            live_attempts += 1
            if result.get("kwin_live"):
                live_hits += 1
    if live_attempts and live_hits == 0:
        raise RuntimeError(
            "KWin scrollFactor D-Bus Set failed for all pointers "
            "(kcminputrc alone does not change Wayland scroll speed)"
        )
    return written
