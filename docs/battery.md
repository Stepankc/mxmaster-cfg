# Battery

[English](battery.md) · [Русский](battery.ru.md)

HID++ **Unified Battery** (`0x1004`) — status only (not a cfg setting).

## Why logiops D-Bus is not enough

Packaged **logiops 0.3.5 has no** `pizza.pixl.LogiOps.Battery` D-Bus
interface on MX Master 3S (Bolt). Device introspect shows DPI / SmartShift /
HiresScroll / ThumbWheel / Buttons only.

## How mxmaster-cfg reads the real %

The helper tries, in order:

1. **logiops D-Bus** `pizza.pixl.LogiOps.Battery` / Device battery props
   (future-proof; empty on 0.3.5)
2. **UPower / sysfs** `power_supply` — often works for **Bluetooth** when the
   kernel exports a HID++ battery; on Bolt + `hid-generic` this is usually empty
3. **Short HID++ probe** on the Bolt/Unifying (or BT) **hidraw** node:
   Root `GetFeature(0x1004)` → `GetStatus` — returns percent + charging status

### Coexistence with logid (preferred)

On Stepan’s MX Master 3S **Logi Bolt** smoke, the hidraw probe **coexists** with
a running `logid` (no service stop). `GetDPI` still works after the probe.

If open/xfer fails (device busy), the helper may **briefly stop and restart**
`logid` for one read, then soft-wake the Bolt receiver if needed. Pass
`--no-hidpp-stop` to forbid that fallback.

Solaar is **not** used for polling (it would compete for HID++ ownership).

## Helper

```bash
pkexec /usr/local/libexec/mxmaster-cfg-helper get-battery
pkexec /usr/local/libexec/mxmaster-cfg-helper get-battery --no-hidpp-stop
pkexec /usr/local/libexec/mxmaster-cfg-helper status   # includes battery per device
```

Example success payload (Bolt):

```json
{
  "ok": true,
  "battery_available": true,
  "battery": {
    "percent": 30,
    "charging": false,
    "status": "discharging",
    "feature": "0x1004",
    "source": "hidpp:/dev/hidraw4",
    "logid_stopped": false
  }
}
```

`get-battery` returns `ok: true` even when unavailable (`battery_available:
false`) so the GUI can render “n/a” without a hard error.

## GUI

Status row shows **percent**, charging/discharge/full, and the source
(`HID++ 0x1004`, `UPower`, `sysfs`, or a D-Bus iface). Refresh re-runs the
cascade.
