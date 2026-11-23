# SPDX-License-Identifier: GPL-3.0-or-later
"""Translate our profile schema → logiops libconfig (``logid.cfg``).

This is a *stub* writer covering MVP fields (SmartShift, hi-res, remaps,
basic gestures). Real devices may need CID/feature tweaks from the device DB
after the hardware spike.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

# Default path used by packaged logiops on Debian/Ubuntu (verify on spike).
DEFAULT_LOGID_CFG = Path("/etc/logid.cfg")


def load_profile(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        data = yaml.safe_load(text)
    elif path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        raise ValueError(f"Unsupported profile format: {path.suffix}")
    if not isinstance(data, dict):
        raise ValueError("Profile root must be a mapping")
    return data


def _libconfig_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _format_keys(keys: list[str]) -> str:
    return "[" + ", ".join(_libconfig_string(k) for k in keys) + "]"


def _format_cid(cid: Any) -> str:
    """Emit libconfig CID; keep hex form when provided as 0x… string."""
    if isinstance(cid, str) and cid.lower().startswith("0x"):
        return cid.lower()
    if isinstance(cid, int):
        return hex(cid)
    return str(cid)


def _render_button(button: dict[str, Any]) -> str:
    cid = _format_cid(button["cid"])
    action = button.get("action", {})
    kind = action.get("type", "None")
    lines = [f"        {{ cid: {cid};"]
    if kind == "Keypress":
        keys = action.get("keys") or []
        lines.append("          action = {")
        lines.append('            type: "Keypress";')
        lines.append(f"            keys: {_format_keys(keys)};")
        lines.append("          };")
    elif kind == "ToggleSmartShift":
        lines.append("          action = {")
        lines.append('            type: "ToggleSmartShift";')
        lines.append("          };")
    elif kind == "Gestures":
        lines.append("          action = {")
        lines.append('            type: "Gestures";')
        lines.append(f'            gestures: (')
        for g in action.get("gestures") or []:
            direction = g.get("direction", "None")
            mode = g.get("mode", "OnRelease")
            g_action = g.get("action") or {"type": "None"}
            lines.append("              {")
            lines.append(f'                direction: "{direction}";')
            lines.append(f'                mode: "{mode}";')
            g_type = g_action.get("type", "None")
            if g_type == "Keypress":
                keys = g_action.get("keys") or []
                lines.append("                action = {")
                lines.append('                  type: "Keypress";')
                lines.append(f"                  keys: {_format_keys(keys)};")
                lines.append("                };")
            elif g_type == "CycleDPI":
                dpis = g_action.get("dpis") or [400, 800, 1200, 1600]
                dpi_list = ", ".join(str(int(x)) for x in dpis)
                lines.append("                action = {")
                lines.append('                  type: "CycleDPI";')
                lines.append(f"                  dpis: [{dpi_list}];")
                lines.append("                };")
            elif g_type == "ToggleSmartShift":
                lines.append("                action = {")
                lines.append('                  type: "ToggleSmartShift";')
                lines.append("                };")
            elif g_type in {"None", "none", None}:
                lines.append("                action = {")
                lines.append('                  type: "None";')
                lines.append("                };")
            else:
                lines.append("                action = {")
                lines.append(f'                  type: "{g_type}";')
                lines.append("                };")
            lines.append("              },")
        lines.append("            );")
        lines.append("          };")
    elif kind == "CycleDPI":
        dpis = action.get("dpis") or [400, 800, 1200, 1600]
        dpi_list = ", ".join(str(int(x)) for x in dpis)
        lines.append("          action = {")
        lines.append('            type: "CycleDPI";')
        lines.append(f"            dpis: [{dpi_list}];")
        lines.append("          };")
    else:
        lines.append("          action = {")
        lines.append(f'            type: "{kind}";')
        lines.append("          };")
    lines.append("        }")
    return "\n".join(lines)


class CfgWriter:
    """Build a logiops ``devices: (...)`` snippet from our profile dict."""

    def __init__(self, profile: dict[str, Any]) -> None:
        self.profile = profile

    def render(self) -> str:
        device = self.profile.get("device") or {}
        name = device.get("name") or "MX Master 3S"
        smartshift = self.profile.get("smartshift") or {}
        hiresscroll = self.profile.get("hiresscroll") or {}
        dpi = self.profile.get("dpi")
        buttons = self.profile.get("buttons") or []

        parts: list[str] = [
            "// Generated by mxmaster_cfg (scaffold) — do not hand-edit without backup.",
            "// SPDX-License-Identifier: GPL-3.0-or-later",
            "devices: (",
            "  {",
            f"    name: {_libconfig_string(name)};",
        ]

        if smartshift:
            on = "true" if smartshift.get("on", True) else "false"
            threshold = int(smartshift.get("threshold", 30))
            torque = smartshift.get("torque")
            parts.append("    smartshift:")
            parts.append("    {")
            parts.append(f"      on: {on};")
            parts.append(f"      threshold: {threshold};")
            if torque is not None:
                parts.append(f"      torque: {int(torque)};")
            parts.append("    };")

        if hiresscroll:
            # logiops 0.3.5: hires / invert / target (target = HID++ divert).
            # No separate ``divert`` key in cfg.
            hires = "true" if hiresscroll.get("hires", True) else "false"
            invert = "true" if hiresscroll.get("invert", False) else "false"
            target = "true" if hiresscroll.get("target", False) else "false"
            parts.append("    hiresscroll:")
            parts.append("    {")
            parts.append(f"      hires: {hires};")
            parts.append(f"      invert: {invert};")
            parts.append(f"      target: {target};")
            parts.append("    };")

        if dpi is not None:
            parts.append(f"    dpi: {int(dpi)};")

        if buttons:
            parts.append("    buttons: (")
            rendered = [",\n".join(_render_button(b) for b in buttons)]
            parts.extend(rendered)
            parts.append("    );")

        parts.append("  }")
        parts.append(");")
        parts.append("")
        return "\n".join(parts)

    def write(self, path: Path, *, backup: bool = True) -> Path:
        path = Path(path)
        text = self.render()
        if backup and path.exists():
            bak = path.with_suffix(path.suffix + ".bak")
            bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render profile → logid.cfg")
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("/tmp/logid.cfg"))
    parser.add_argument("--stdout", action="store_true")
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    writer = CfgWriter(profile)
    if args.stdout:
        sys.stdout.write(writer.render())
        return 0
    out = writer.write(args.out, backup=False)
    print(f"Wrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
