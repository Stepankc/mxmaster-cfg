# Thumb wheel

[English](thumbwheel.md) · [Русский](thumbwheel.ru.md)

Feature `ThumbWheel` / HID++ `0x2150` via logiops.

## GUI

- **Divert** / **Invert** — mirrored from `ThumbWheel.GetConfig` (`bb`)
- **Left/Right** presets: omit (OS scroll), Axis `REL_HWHEEL(_HI_RES)`,
  NoPress (disable), volume (`OnInterval` + `KEY_VOLUME*`)
- **Tap** presets: None / Mute / PlayPause / Meta

`left` / `right` / `tap` / `touch` / `proxy` need **divert=true**.
There is **no haptic** field in the logiops 0.3.5 cfg schema.

Apply writes the `thumbwheel { … }` block through `CfgWriter`.

## Helper

```bash
pkexec /usr/local/libexec/mxmaster-cfg-helper get-thumbwheel
pkexec /usr/local/libexec/mxmaster-cfg-helper set-thumbwheel \
  --divert true --invert false
```

Live `SetDivert` / `SetInvert` may time out on Bolt; prefer Apply
(cfg + restart) for persistence. Gesture/action bindings are cfg-only.
