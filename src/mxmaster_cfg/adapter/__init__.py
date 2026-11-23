# SPDX-License-Identifier: GPL-3.0-or-later
"""Adapters: profile → logiops cfg, D-Bus client, pkexec helper wrapper."""

from __future__ import annotations

from typing import Any

__all__ = [
    "CfgWriter",
    "LogiOpsDBusClient",
    "LogiOpsDBusError",
    "PrivilegedHelperError",
    "apply_cfg_text",
    "load_profile",
    "status",
]


def __getattr__(name: str) -> Any:
    if name in {"CfgWriter", "load_profile"}:
        from mxmaster_cfg.adapter import logiops_cfg as mod

        return getattr(mod, name)
    if name in {"LogiOpsDBusClient", "LogiOpsDBusError"}:
        from mxmaster_cfg.adapter import logiops_dbus as mod

        return getattr(mod, name)
    if name in {"PrivilegedHelperError", "apply_cfg_text", "status"}:
        from mxmaster_cfg.adapter import privileged as mod

        return getattr(mod, name)
    raise AttributeError(name)
