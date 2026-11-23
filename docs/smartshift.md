# SmartShift

[English](smartshift.md) · [Русский](smartshift.ru.md)

MagSpeed / SmartShift is exposed through logiops `SmartShift` D-Bus and the
`smartshift { … }` block in `/etc/logid.cfg`.

## GUI

- Checkbox: SmartShift **on**
- Spinbox: **threshold** (1–50)
- **Torque**: shown but disabled when `TorqueSupport=false` (MX Master 3S) —
  torque is not written to cfg in that case

Live `SetActive` / `SetThreshold` often time out on Bolt; **readback** and
**Apply (cfg + restart)** are authoritative.

## Tri-state GetConfig (critical)

logiops `SmartShift.GetConfig` returns `yyy` = **mode, threshold, torque**.
The first byte is a **config tri-state**, not raw HID++:

| mode | Meaning |
|------|---------|
| **2** | `on: true` |
| **1** | `on: false` |
| **0** | `on` unset (`SetActive` with `clear=true`) |

Do **not** treat `mode != 0` as “on” — that maps **off (1)** to on and makes the
checkbox appear stuck after Apply→Refresh.

`SetActive(active, clear)`: `clear=true` **clears** the `on` value (mode 0);
it does **not** mean “turn off”. For on/off toggles always use `clear=false`.

This app maps: checkbox checked ↔ mode 2; unchecked ↔ mode 1.

Longer engineering notes (RU): [smartshift-gestures-notes.md](smartshift-gestures-notes.md).
