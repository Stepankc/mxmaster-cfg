# Battery

[English](battery.md) · [Русский](battery.ru.md)

HID++ **Unified Battery** (`0x1004`) — status only (not a cfg setting).

## What logiops 0.3.5 exposes

Packaged **logiops 0.3.5 has no** `pizza.pixl.LogiOps.Battery` D-Bus
interface on MX Master 3S (Bolt). Device introspect shows DPI / SmartShift /
HiresScroll / ThumbWheel / Buttons only.

The helper still **probes** for:

1. `pizza.pixl.LogiOps.Battery` Get* methods (future-proof)
2. Device properties like `BatteryPercentage` / `BatteryLevel`

When nothing is available, GUI status shows **н/д** with a short reason.
Refresh re-runs the probe.

## Helper

```bash
pkexec /usr/local/libexec/mxmaster-cfg-helper get-battery
pkexec /usr/local/libexec/mxmaster-cfg-helper status   # includes battery per device
```

`get-battery` returns `ok: true` even when unavailable (`battery_available:
false`) so the GUI can render “n/a” without a hard error.
