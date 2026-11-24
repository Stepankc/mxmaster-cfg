# Hi-res scroll

[English](hires-scroll.md) · [Русский](hires-scroll.ru.md)

Feature `HiresScroll` / HID++ `0x2121` via logiops.

## GUI

Checkboxes: **hires**, **invert**, **target / divert**.

Refresh reads `HiresScroll.GetConfig` → `bbb` (hires, invert, target).
Apply writes the `hiresscroll { … }` block through `CfgWriter`.

There is **no** separate `divert` key in logiops 0.3.5 cfg: HID++
`Mode::Target` maps to libconfig **`target`**.

Unlike SmartShift, unset `getConfig` returns defaults `{true, false, false}`
(not a tri-state).

## Helper

```bash
pkexec /usr/libexec/mxmaster-cfg-helper get-hiresscroll
pkexec /usr/libexec/mxmaster-cfg-helper set-hiresscroll \
  --hires true --invert false --target false
```

Live `SetHires` / `SetInvert` / `SetTarget` often time out on Bolt; prefer
Apply (cfg + restart) for persistence.

Screenshot: `media/hires-scroll/main-window.png`

Engineering notes (RU): [hires-scroll-notes.md](hires-scroll-notes.md).
