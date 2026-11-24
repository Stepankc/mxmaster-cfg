# Thumb wheel

[English](thumbwheel.md) · [Русский](thumbwheel.ru.md)

Feature `ThumbWheel` / HID++ `0x2150` via logiops.

## GUI

- **Divert** / **Invert** — mirrored from `ThumbWheel.GetConfig` (`bb`)
- **Left/Right** presets: omit (OS scroll), Axis `REL_HWHEEL(_HI_RES)`,
  NoPress (disable), volume (`OnInterval` + `KEY_VOLUME*`)
- **Free-form Axis** — custom axis name + `|axis_multiplier|` (left − / right +)
- **Free-form OnInterval Keypress** — interval + typed `KEY_*` chord
- **Tap / Touch / Proxy** — presets (None / Mute / PlayPause / Meta) plus
  free-form Keypress; unknown values from profile/cfg load as custom

`left` / `right` / `tap` / `touch` / `proxy` need **divert=true**.
There is **no haptic** field in the logiops 0.3.5 cfg schema.

Apply writes the `thumbwheel { … }` block through `CfgWriter`. Round-trip:
profile → writer → apply-cfg. Live `SetDivert` / `SetInvert` may time out on
Bolt; gesture/action bindings are cfg-only.

## Helper

```bash
pkexec /usr/libexec/mxmaster-cfg-helper get-thumbwheel
pkexec /usr/libexec/mxmaster-cfg-helper set-thumbwheel \
  --divert true --invert false
```
