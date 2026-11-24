# Scroll speed

[English](scroll-speed.md) · [Русский](scroll-speed.ru.md)

How “scroll speed” maps on MX Master 3S under **logiops 0.3.5** and Linux.

## Short answer

| Layer | What it controls | In mxmaster-cfg? |
|-------|------------------|------------------|
| HID++ `0x2121` HiRes Wheel | Mode bits only: **hires**, **invert**, **target** (divert). Firmware also reports a **capability multiplier** (used internally by logiops Axis gestures). **No** “lines per notch” / Options+ scroll-speed field. | hires / invert / target checkboxes |
| logiops divert + Axis | When `target: true`, `up`/`down` gestures with `axis_multiplier` re-inject `REL_WHEEL` or `REL_WHEEL_HI_RES` (PixlOne/logiops [#116](https://github.com/PixlOne/logiops/issues/116)). | **Scroll speed** checkbox + multiplier slider → cfg |
| Kernel / libinput / DE | How wheel events become pixel/line scroll (hwdb click angle, quirks, KDE scroll speed). | Documented only — not written by this app |

**Do not** expect a no-op slider that pretends to change firmware line speed. Without divert, use the OS path below.

## GUI (divert path)

1. Enable **Скорость через divert (Axis multiplier)** — forces `target: true`.
2. Set **Множитель** (0.25× … 4.00×). `1.00×` is the baseline divert scale.
3. Click **Применить в cfg** (restarts `logid`). D-Bus `SetHires` / `SetInvert` / `SetTarget` cannot set `axis_multiplier`; `SetUp`/`SetDown` only select gesture *type*.

Rendered cfg shape (hires on):

```
hiresscroll:
{
  hires: true;
  invert: false;
  target: true;
  up = { mode: "Axis"; axis: "REL_WHEEL_HI_RES"; axis_multiplier: 1.5; };
  down = { mode: "Axis"; axis: "REL_WHEEL_HI_RES"; axis_multiplier: -1.5; };
};
```

With `hires: false`, axes use `REL_WHEEL` instead.

Profile field: `hiresscroll.scroll_multiplier` (or explicit `up`/`down`).

## OS path (no divert)

When `target: false`, logiops does not scale scroll magnitude.

**Kubuntu / KDE Plasma 6:**

1. System Settings → **Mouse & Touchpad** → **Mouse**
2. Adjust **Scroll speed** (wording may vary slightly by Plasma version)

That setting is compositor/libinput territory, not HID++.

**libinput / udev (advanced):**

- Bolt often exposes only low-res wheel steps; Bluetooth is more likely to expose hi-res events (see ArchWiki *Logitech MX Master*).
- Optional hwdb (`MOUSE_WHEEL_CLICK_ANGLE` / `MOUSE_WHEEL_CLICK_COUNT`) or `local-overrides.quirks` (`AttrEventCode=-REL_WHEEL_HI_RES;…`) change feel — see [hires-scroll.md](hires-scroll.md) and ArchWiki.

## Solaar / ratbag equivalents

| Tool | Rough equivalent |
|------|------------------|
| Solaar “Scroll Wheel Resolution” | ≈ logiops `hires` (kernel HID++ driver may fight this — “Ignore” is often safest) |
| Solaar invert / divert | ≈ `invert` / `target` |
| Options+ “Scroll speed” | **OS + software** on Windows/macOS; **not** a portable HID++ setpoint on Linux |
| piper / libratbag | DPI/buttons; not MagSpeed scroll-speed UX |

## Related

- [hires-scroll.md](hires-scroll.md) — mode bits
- [feature-gap.md](feature-gap.md) — full Options+ checklist
- [smartshift.md](smartshift.md) — ratchet / free-spin threshold (not line speed)
