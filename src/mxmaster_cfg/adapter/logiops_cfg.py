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


def _fix_yaml_bool_keys(obj: Any) -> Any:
    """YAML 1.1 turns bare ``on``/``off``/``yes``/``no`` into bool keys.

    Our schema uses the string key ``on`` under ``smartshift``. Normalize after
    ``safe_load`` so quoted and unquoted sources behave the same.
    """
    if isinstance(obj, list):
        return [_fix_yaml_bool_keys(x) for x in obj]
    if not isinstance(obj, dict):
        return obj
    out: dict[str, Any] = {}
    for key, value in obj.items():
        if key is True:
            key = "on"
        elif key is False:
            key = "off"
        out[key] = _fix_yaml_bool_keys(value)
    return out


def load_profile(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        data = _fix_yaml_bool_keys(yaml.safe_load(text))
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


def _render_action(action: dict[str, Any], *, indent: str) -> list[str]:
    """Render a logiops BasicAction (Keypress / None / ToggleSmartShift / …)."""
    kind = action.get("type", "None")
    lines: list[str] = [f"{indent}{{"]
    if kind == "Keypress":
        keys = action.get("keys") or []
        lines.append(f'{indent}  type: "Keypress";')
        lines.append(f"{indent}  keys: {_format_keys(keys)};")
    elif kind == "ToggleSmartShift":
        lines.append(f'{indent}  type: "ToggleSmartShift";')
    elif kind == "ToggleHiresScroll":
        lines.append(f'{indent}  type: "ToggleHiresScroll";')
    elif kind == "CycleDPI":
        dpis = action.get("dpis") or [400, 800, 1200, 1600]
        dpi_list = ", ".join(str(int(x)) for x in dpis)
        lines.append(f'{indent}  type: "CycleDPI";')
        lines.append(f"{indent}  dpis: [{dpi_list}];")
        if action.get("sensor") is not None:
            lines.append(f"{indent}  sensor: {int(action['sensor'])};")
    elif kind == "ChangeDPI":
        inc = action.get("inc", 50)
        lines.append(f'{indent}  type: "ChangeDPI";')
        lines.append(f"{indent}  inc: {int(inc)};")
        if action.get("sensor") is not None:
            lines.append(f"{indent}  sensor: {int(action['sensor'])};")
    elif kind == "ChangeHost":
        lines.append(f'{indent}  type: "ChangeHost";')
        host = action.get("host")
        if host is not None:
            if isinstance(host, int):
                lines.append(f"{indent}  host: {int(host)};")
            else:
                lines.append(f"{indent}  host: {_libconfig_string(str(host))};")
    elif kind in {"None", "none", None}:
        lines.append(f'{indent}  type: "None";')
    else:
        lines.append(f'{indent}  type: "{kind}";')
    lines.append(f"{indent}}}")
    return lines


def _render_gesture(gesture: dict[str, Any], *, indent: str) -> list[str]:
    """Render a thumbwheel left/right Gesture (Axis / NoPress / OnInterval…)."""
    mode = gesture.get("mode", "NoPress")
    lines: list[str] = [f"{indent}{{"]
    lines.append(f'{indent}  mode: "{mode}";')
    if mode == "Axis":
        axis = gesture.get("axis", "REL_HWHEEL")
        lines.append(f'{indent}  axis: {_libconfig_string(str(axis))};')
        if gesture.get("axis_multiplier") is not None:
            lines.append(
                f"{indent}  axis_multiplier: {gesture['axis_multiplier']};"
            )
        if gesture.get("threshold") is not None:
            lines.append(f"{indent}  threshold: {int(gesture['threshold'])};")
    elif mode in {"OnInterval", "OnFewPixels", "OnRelease", "OnThreshold"}:
        if gesture.get("interval") is not None:
            lines.append(f"{indent}  interval: {int(gesture['interval'])};")
        if gesture.get("threshold") is not None:
            lines.append(f"{indent}  threshold: {int(gesture['threshold'])};")
        nested = gesture.get("action")
        if isinstance(nested, dict):
            lines.append(f"{indent}  action =")
            action_lines = _render_action(nested, indent=indent + "  ")
            # Attach semicolon after closing brace of action object.
            action_lines[-1] = action_lines[-1] + ";"
            lines.extend(action_lines)
    elif mode == "NoPress":
        if gesture.get("threshold") is not None:
            lines.append(f"{indent}  threshold: {int(gesture['threshold'])};")
    lines.append(f"{indent}}}")
    return lines


def _hires_axes_from_profile(hiresscroll: dict[str, Any]) -> dict[str, Any]:
    """Resolve ``up``/``down`` gestures for hiresscroll.

    Prefer explicit ``up``/``down`` objects. Else, when ``target`` is true and
    ``scroll_multiplier`` is set, synthesize Axis gestures (PixlOne/logiops
    #116). HID++ HiRes Wheel ``0x2121`` only exposes mode bits (hires/invert/
    target) plus a firmware ``multiplier`` capability used internally by
    logiops — not a user "lines per notch" control.
    """
    out: dict[str, Any] = {}
    for side in ("up", "down"):
        gest = hiresscroll.get(side)
        if isinstance(gest, dict):
            out[side] = gest
    if out:
        return out
    if not hiresscroll.get("target"):
        return out
    mult = hiresscroll.get("scroll_multiplier")
    if mult is None:
        return out
    try:
        magnitude = abs(float(mult))
    except (TypeError, ValueError):
        return out
    if magnitude <= 0:
        return out
    # Prefer REL_WHEEL for notch-sized steps; HI_RES reintroduces micro-scroll
    # between SmartShift ratchet clicks on MX Master 3S.
    hires = bool(hiresscroll.get("hires", False))
    axis = "REL_WHEEL_HI_RES" if hires else "REL_WHEEL"
    # Keep one decimal when possible for libconfig readability.
    if abs(magnitude - round(magnitude)) < 1e-9:
        mag_out: float | int = int(round(magnitude))
    else:
        mag_out = round(magnitude, 3)
    out["up"] = {
        "mode": "Axis",
        "axis": axis,
        "axis_multiplier": mag_out,
    }
    out["down"] = {
        "mode": "Axis",
        "axis": axis,
        "axis_multiplier": -mag_out,
    }
    return out


def _render_thumbwheel(thumb: dict[str, Any]) -> list[str]:
    """Render logiops ``thumbwheel: { … };`` (feature 0x2150).

    Schema fields: divert, invert, left, right, proxy, touch, tap.
    There is **no** haptic key in logiops 0.3.5.
    """
    lines = ["    thumbwheel:", "    {"]
    if "divert" in thumb:
        lines.append(
            f"      divert: {'true' if thumb.get('divert') else 'false'};"
        )
    if "invert" in thumb:
        lines.append(
            f"      invert: {'true' if thumb.get('invert') else 'false'};"
        )
    for side in ("left", "right"):
        gest = thumb.get(side)
        if isinstance(gest, dict):
            lines.append(f"      {side} =")
            g_lines = _render_gesture(gest, indent="      ")
            g_lines[-1] = g_lines[-1] + ";"
            lines.extend(g_lines)
    for act_name in ("tap", "touch", "proxy"):
        act = thumb.get(act_name)
        if isinstance(act, dict):
            lines.append(f"      {act_name} =")
            a_lines = _render_action(act, indent="      ")
            a_lines[-1] = a_lines[-1] + ";"
            lines.extend(a_lines)
    lines.append("    };")
    return lines


def _render_button(button: dict[str, Any]) -> str:
    cid = _format_cid(button["cid"])
    action = button.get("action", {})
    kind = action.get("type", "None")
    lines = [f"        {{ cid: {cid};"]
    if kind == "Gestures":
        lines.append("          action = {")
        lines.append('            type: "Gestures";')
        lines.append("            gestures: (")
        for g in action.get("gestures") or []:
            direction = g.get("direction", "None")
            mode = g.get("mode", "OnRelease")
            g_action = g.get("action") or {"type": "None"}
            lines.append("              {")
            lines.append(f'                direction: "{direction}";')
            lines.append(f'                mode: "{mode}";')
            lines.append("                action =")
            a_lines = _render_action(g_action, indent="                ")
            a_lines[-1] = a_lines[-1] + ";"
            lines.extend(a_lines)
            lines.append("              },")
        lines.append("            );")
        lines.append("          };")
    else:
        lines.append("          action =")
        a_lines = _render_action(action, indent="          ")
        a_lines[-1] = a_lines[-1] + ";"
        lines.extend(a_lines)
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
        thumbwheel = self.profile.get("thumbwheel") or {}
        dpi = self.profile.get("dpi")
        buttons = self.profile.get("buttons") or []

        parts: list[str] = [
            "// Generated by mxmaster_cfg — do not hand-edit without backup.",
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
            # SAFETY: target:true WITHOUT up/down Axis swallows the wheel
            # (no page scroll). Only emit divert when both axes exist.
            # Default hires false: SmartShift ratchet → scroll per notch, not
            # continuous HI_RES micro-steps between clicks.
            hires = "true" if hiresscroll.get("hires", False) else "false"
            invert = "true" if hiresscroll.get("invert", False) else "false"
            axes = _hires_axes_from_profile(hiresscroll)
            want_target = bool(hiresscroll.get("target", False))
            safe_divert = want_target and "up" in axes and "down" in axes
            target = "true" if safe_divert else "false"
            parts.append("    hiresscroll:")
            parts.append("    {")
            parts.append(f"      hires: {hires};")
            parts.append(f"      invert: {invert};")
            parts.append(f"      target: {target};")
            if safe_divert:
                for side in ("up", "down"):
                    gest = axes.get(side)
                    if isinstance(gest, dict):
                        parts.append(f"      {side} =")
                        g_lines = _render_gesture(gest, indent="      ")
                        g_lines[-1] = g_lines[-1] + ";"
                        parts.extend(g_lines)
            parts.append("    };")

        if thumbwheel:
            parts.extend(_render_thumbwheel(thumbwheel))

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
