# SPDX-License-Identifier: GPL-3.0-or-later
"""D-Bus client for logiops ≥ 0.3 (ipcgull / GDBus) — verified on 0.3.5.

Constants match ``src/logid/ipc_defs.h`` in PixlOne/logiops:

* service: ``pizza.pixl.LogiOps``
* root node: ``/pizza/pixl/logiops``

On Ubuntu 26.04 packaged logid, stock D-Bus policy is **root-only**.
User-session code should use :mod:`mxmaster_cfg.adapter.privileged` (pkexec
helper). This module still supports direct ``busctl`` calls when already root
(spike / helper internals / tests).

Real paths (0.3.5): ``/pizza/pixl/logiops/devices/N`` (plural ``devices``).
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Sequence

SERVICE = "pizza.pixl.LogiOps"
ROOT_PATH = "/pizza/pixl/logiops"

IFACE_CONFIG = "pizza.pixl.LogiOps.Config"
IFACE_DEVICES = "pizza.pixl.LogiOps.Devices"
IFACE_DEVICE = "pizza.pixl.LogiOps.Device"
IFACE_SMARTSHIFT = "pizza.pixl.LogiOps.SmartShift"
IFACE_DPI = "pizza.pixl.LogiOps.DPI"
IFACE_HIRESSCROLL = "pizza.pixl.LogiOps.HiresScroll"
IFACE_BUTTON = "pizza.pixl.LogiOps.Button"
IFACE_BUTTONS = "pizza.pixl.LogiOps.Buttons"
IFACE_RECEIVERS = "pizza.pixl.LogiOps.Receivers"

# Observed on MX Master 3S (Bolt) spike — remappable CIDs.
CID_BACK = 0x53
CID_FORWARD = 0x56
CID_GESTURE = 0xC3
CID_MODE = 0xC4


class LogiOpsDBusError(RuntimeError):
    """Raised when logid IPC is unavailable or a call fails."""


@dataclass(frozen=True)
class BusTarget:
    bus: str = "system"  # "system" | "session"


@dataclass(frozen=True)
class DeviceInfo:
    path: str
    name: str | None = None
    product_id: int | None = None
    active: bool | None = None
    dpi: int | None = None
    dpi_error: str | None = None


class LogiOpsDBusClient:
    """Direct busctl client (expects permission — typically root)."""

    def __init__(self, target: BusTarget | None = None) -> None:
        self.target = target or BusTarget()

    def probe(self) -> str:
        out = self._busctl(["status", SERVICE])
        if out.returncode != 0:
            raise LogiOpsDBusError(
                f"Service {SERVICE} not found on {self.target.bus} bus. "
                "Is logid ≥ 0.3 running? Try: systemctl status logid"
            )
        return f"OK: {SERVICE} present on {self.target.bus} bus"

    def list_device_paths(self) -> list[str]:
        tree = self._busctl(["tree", SERVICE])
        if tree.returncode != 0:
            # Access denied for non-root is expected with stock policy.
            err = tree.stderr.strip() or tree.stdout.strip()
            if "Access denied" in err or "access denied" in err.lower():
                raise LogiOpsDBusError(
                    "D-Bus Access denied for non-root (stock logiops policy). "
                    "Use mxmaster-cfg-helper via pkexec."
                )
            return []
        paths: list[str] = []
        for line in tree.stdout.splitlines():
            for token in line.split():
                if re.fullmatch(r"/pizza/pixl/logiops/devices/\d+", token):
                    paths.append(token)
        return sorted(set(paths))

    def list_devices(self) -> list[str]:
        """Backward-compatible alias → device object paths."""
        return self.list_device_paths()

    def describe_devices(self) -> list[DeviceInfo]:
        infos: list[DeviceInfo] = []
        for path in self.list_device_paths():
            name = product_id = active = None
            dpi = None
            dpi_error = None
            try:
                name = self.get_property(path, IFACE_DEVICE, "Name")
                product_id = self.get_property(path, IFACE_DEVICE, "ProductID")
                active = self.get_property(path, IFACE_DEVICE, "Active")
            except LogiOpsDBusError:
                pass
            try:
                dpi = self.get_dpi(path)
            except LogiOpsDBusError as exc:
                dpi_error = str(exc)
            infos.append(
                DeviceInfo(
                    path=path,
                    name=str(name) if name is not None else None,
                    product_id=int(product_id) if product_id is not None else None,
                    active=bool(active) if active is not None else None,
                    dpi=int(dpi) if isinstance(dpi, int) else None,
                    dpi_error=dpi_error,
                )
            )
        return infos

    def device_path(self, index: int | str = 0) -> str:
        return f"{ROOT_PATH}/devices/{index}"

    def get_dpi(self, path: str | None = None, *, sensor: int = 0) -> int:
        path = path or self.device_path(0)
        out = self._call(path, IFACE_DPI, "GetDPI", "y", str(sensor))
        val = self._parse_variant(out)
        if not isinstance(val, int):
            raise LogiOpsDBusError(f"unexpected GetDPI result: {out}")
        return val

    def set_dpi(self, dpi: int, path: str | None = None, *, sensor: int = 0) -> None:
        path = path or self.device_path(0)
        self._call(path, IFACE_DPI, "SetDPI", "qy", str(dpi), str(sensor))

    def get_property(self, path: str, interface: str, prop: str) -> Any:
        r = self._busctl(["get-property", SERVICE, path, interface, prop])
        if r.returncode != 0:
            raise LogiOpsDBusError(
                r.stderr.strip() or r.stdout.strip() or f"get-property {prop}"
            )
        return self._parse_variant(r.stdout.strip())

    def save_config(self) -> None:
        """``Config.Save`` on root (persists runtime state if supported)."""
        self._call(ROOT_PATH, IFACE_CONFIG, "Save")

    def _call(self, path: str, interface: str, method: str, *args: str) -> str:
        result = self._busctl(["call", SERVICE, path, interface, method, *args])
        if result.returncode != 0:
            raise LogiOpsDBusError(
                result.stderr.strip()
                or result.stdout.strip()
                or f"busctl call failed: {method}"
            )
        return result.stdout.strip()

    def _busctl(self, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        if shutil.which("busctl") is None:
            raise LogiOpsDBusError("busctl not found (install systemd)")
        bus_flag = f"--{self.target.bus}"
        return subprocess.run(
            ["busctl", bus_flag, *args],
            text=True,
            capture_output=True,
            check=False,
            timeout=25,
        )

    @staticmethod
    def _parse_variant(text: str) -> Any:
        text = text.strip()
        if not text:
            return None
        m = re.match(r"^([a-zA-Z0-9\{\}]+)(?:\s+(.*))?$", text, re.DOTALL)
        if not m:
            return text
        sig, rest = m.group(1), (m.group(2) or "").strip()
        if sig == "s":
            qm = re.match(r'^"(.*)"$', rest)
            return qm.group(1) if qm else rest
        if sig in {"q", "u", "i", "n", "t", "x", "y"}:
            return int(rest.split()[0])
        if sig == "b":
            return rest.split()[0] == "true"
        return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe logiops D-Bus IPC")
    parser.add_argument("--session", action="store_true", help="Use session bus")
    parser.add_argument("--tree", action="store_true", help="Print busctl tree")
    args = parser.parse_args(argv)

    client = LogiOpsDBusClient(BusTarget(bus="session" if args.session else "system"))
    try:
        print(client.probe())
        devices = client.list_device_paths()
        print("devices:")
        for d in devices or ["(none)"]:
            print(f"  {d}")
        if args.tree:
            r = client._busctl(["tree", SERVICE])
            print(r.stdout or r.stderr)
    except LogiOpsDBusError as exc:
        print(f"ERROR: {exc}", file=__import__("sys").stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
