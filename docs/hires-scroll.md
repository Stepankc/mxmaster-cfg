# Hi-res scroll

[English](hires-scroll.md) · [Русский](hires-scroll.ru.md)

Feature `HiresScroll` / HID++ `0x2121` via logiops.

## GUI

Checkboxes: **hires**, **invert**, **target / divert**, plus optional
**divert Axis** multiplier. Default **hires OFF** with SmartShift so ratchet
mode scrolls **per notch**, not on micro-movements between clicks.

Refresh reads `HiresScroll.GetConfig` → `bbb` (hires, invert, target).
Apply writes the `hiresscroll { … }` block through `CfgWriter`.

There is **no** separate `divert` key in logiops 0.3.5 cfg: HID++
`Mode::Target` maps to libconfig **`target`**.

Unset `getConfig` in logiops returns `{true, false, false}`, but mxmaster-cfg
defaults profiles/GUI to **`hires: false`** for discrete MagSpeed notches.

**Scroll speed** (lines per notch) is not a `0x2121` mode bit — use the Plasma
ScrollFactor slider; see [scroll-speed.md](scroll-speed.md).

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
