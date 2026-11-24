# SPDX-License-Identifier: GPL-3.0-or-later
"""User-session wrapper around the pkexec helper (root → logid D-Bus / cfg).

Stock ``pizza.pixl.LogiOps`` D-Bus policy allows only root. The GUI therefore
never calls busctl itself for device ops; it goes through
``mxmaster-cfg-helper`` via ``pkexec`` (polkit action ``org.mxmaster.cfg.helper``).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

HELPER_INSTALLED = Path("/usr/local/libexec/mxmaster-cfg-helper")

# Dev fallback: scaffold tree next to this package (…/scaffold/helper/…)
_HELPER_DEV = (
    Path(__file__).resolve().parents[3] / "helper" / "mxmaster-cfg-helper"
)


class PrivilegedHelperError(RuntimeError):
    """Raised when pkexec/helper fails or returns ok:false."""


@dataclass(frozen=True)
class HelperResult:
    ok: bool
    data: dict[str, Any]
    raw: str


def resolve_helper() -> Path:
    if HELPER_INSTALLED.is_file() and os.access(HELPER_INSTALLED, os.X_OK):
        return HELPER_INSTALLED
    if _HELPER_DEV.is_file():
        return _HELPER_DEV
    raise PrivilegedHelperError(
        "mxmaster-cfg-helper not found. Run: "
        "scaffold/scripts/install-helper.sh"
    )


def run_helper(
    argv: Sequence[str],
    *,
    stdin_text: str | None = None,
    timeout: float = 60.0,
) -> HelperResult:
    """Invoke helper via pkexec (GUI auth dialog on Kubuntu)."""
    helper = resolve_helper()
    if shutil.which("pkexec") is None:
        raise PrivilegedHelperError("pkexec not found (install policykit-1)")

    # When already root (rare), call directly — avoids nested pkexec.
    if os.geteuid() == 0:
        cmd = [str(helper), *argv]
    else:
        # Pass display env so polkit agent can show the dialog on Wayland/X11.
        cmd = [
            "pkexec",
            str(helper),
            *argv,
        ]

    try:
        proc = subprocess.run(
            cmd,
            input=stdin_text,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
            env=_pkexec_env(),
        )
    except subprocess.TimeoutExpired as exc:
        raise PrivilegedHelperError(f"helper timed out: {exc}") from exc

    raw = (proc.stdout or "").strip()
    if proc.returncode == 126 or proc.returncode == 127:
        raise PrivilegedHelperError(
            "pkexec refused to run helper (missing polkit policy or path). "
            f"stderr: {(proc.stderr or '').strip()}"
        )
    if not raw:
        err = (proc.stderr or "").strip() or f"exit {proc.returncode}"
        if proc.returncode != 0:
            raise PrivilegedHelperError(f"helper failed: {err}")
        raise PrivilegedHelperError(f"empty helper output: {err}")

    # Last JSON line wins (ignore any pkexec noise).
    line = raw.splitlines()[-1]
    try:
        data = json.loads(line)
    except json.JSONDecodeError as exc:
        raise PrivilegedHelperError(
            f"helper returned non-JSON: {line[:200]}"
        ) from exc

    if not isinstance(data, dict):
        raise PrivilegedHelperError("helper JSON root must be object")
    if not data.get("ok", False):
        raise PrivilegedHelperError(
            str(data.get("error") or "helper reported failure"),
        )
    return HelperResult(ok=True, data=data, raw=raw)


def _pkexec_env() -> dict[str, str]:
    env = os.environ.copy()
    # pkexec clears env; annotate allow_gui + these help the agent.
    for key in ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "XDG_RUNTIME_DIR"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def status() -> dict[str, Any]:
    return run_helper(["status"]).data


def get_dpi(device: int = 0, sensor: int = 0) -> int:
    data = run_helper(
        ["get-dpi", "--device", str(device), "--sensor", str(sensor)]
    ).data
    dpi = data.get("dpi")
    if not isinstance(dpi, int):
        raise PrivilegedHelperError(f"unexpected dpi value: {dpi!r}")
    return dpi


def set_dpi(dpi: int, device: int = 0, sensor: int = 0) -> dict[str, Any]:
    return run_helper(
        [
            "set-dpi",
            "--device",
            str(device),
            "--sensor",
            str(sensor),
            "--dpi",
            str(dpi),
        ]
    ).data


def set_button_preset(
    cid: int | str,
    preset: str,
    *,
    device: int = 0,
) -> dict[str, Any]:
    cid_s = hex(cid) if isinstance(cid, int) else str(cid)
    return run_helper(
        [
            "set-button-action",
            "--device",
            str(device),
            "--cid",
            cid_s,
            "--preset",
            preset,
        ]
    ).data


def apply_cfg_text(cfg_text: str, *, dest: str = "/etc/logid.cfg") -> dict[str, Any]:
    return run_helper(
        ["apply-cfg", "--dest", dest],
        stdin_text=cfg_text,
        timeout=120.0,
    ).data


def get_smartshift(device: int = 0) -> dict[str, Any]:
    return run_helper(["get-smartshift", "--device", str(device)]).data


def set_smartshift(
    *,
    on: bool | None = None,
    threshold: int | None = None,
    torque: int | None = None,
    device: int = 0,
) -> dict[str, Any]:
    argv: list[str] = ["set-smartshift", "--device", str(device)]
    if on is not None:
        argv.extend(["--on", "true" if on else "false"])
    if threshold is not None:
        argv.extend(["--threshold", str(threshold)])
    if torque is not None:
        argv.extend(["--torque", str(torque)])
    return run_helper(argv).data


def get_hiresscroll(device: int = 0) -> dict[str, Any]:
    return run_helper(["get-hiresscroll", "--device", str(device)]).data


def set_hiresscroll(
    *,
    hires: bool | None = None,
    invert: bool | None = None,
    target: bool | None = None,
    device: int = 0,
) -> dict[str, Any]:
    """Live HiresScroll. ``target`` is logiops divert (HID++ Mode::Target)."""
    argv: list[str] = ["set-hiresscroll", "--device", str(device)]
    if hires is not None:
        argv.extend(["--hires", "true" if hires else "false"])
    if invert is not None:
        argv.extend(["--invert", "true" if invert else "false"])
    if target is not None:
        argv.extend(["--target", "true" if target else "false"])
    return run_helper(argv).data


def get_thumbwheel(device: int = 0) -> dict[str, Any]:
    return run_helper(["get-thumbwheel", "--device", str(device)]).data


def set_thumbwheel(
    *,
    divert: bool | None = None,
    invert: bool | None = None,
    device: int = 0,
) -> dict[str, Any]:
    """Live ThumbWheel divert/invert (feature 0x2150). Prefer apply-cfg."""
    argv: list[str] = ["set-thumbwheel", "--device", str(device)]
    if divert is not None:
        argv.extend(["--divert", "true" if divert else "false"])
    if invert is not None:
        argv.extend(["--invert", "true" if invert else "false"])
    return run_helper(argv).data


def get_battery(device: int = 0, *, allow_stop_logid: bool = True) -> dict[str, Any]:
    """Battery % via D-Bus / UPower / HID++ 0x1004 (helper; may pause logid)."""
    argv = ["get-battery", "--device", str(device)]
    if not allow_stop_logid:
        argv.append("--no-hidpp-stop")
    return run_helper(argv, timeout=90.0).data
