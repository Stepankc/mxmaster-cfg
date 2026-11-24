# Scroll speed

[English](scroll-speed.md) · [Русский](scroll-speed.ru.md)

How “scroll speed” and ratchet feel map on MX Master 3S under **logiops 0.3.5**
and **Kubuntu / Plasma 6 (Wayland)**.

## Short answer

| Layer | What it controls | In mxmaster-cfg? |
|-------|------------------|------------------|
| HID++ `0x2121` HiRes Wheel | Mode bits: **hires**, **invert**, **target**. **`hires:true` = micro-scroll between ratchet notches**; `hires:false` = scroll on discrete clicks. No Options+ “lines per notch”. | Hi-res checkbox (default **OFF** with SmartShift) |
| Plasma `ScrollFactor` | Lines/distance per wheel step for the libinput pointer (`kcminputrc`). | **Primary** DPI-like slider — live write, no divert |
| logiops divert + Axis | `target:true` + `up`/`down` `axis_multiplier` re-inject `REL_WHEEL` / `REL_WHEEL_HI_RES`. | Optional experimental checkbox (both axes or `target:false`) |
| SmartShift threshold | When free-spin engages — **not** lines per notch. | Threshold slider |

## Ratchet = scroll per notch (not micro-scroll)

With **SmartShift on**, keep **hi-res OFF**.

- `hires: true` reports high-resolution wheel motion → pages move on the
  slightest finger movement even while the ratchet is engaged.
- `hires: false` → one MagSpeed notch ≈ one `REL_WHEEL` step (discrete).

The GUI turns hi-res **off** when you enable SmartShift, and defaults hi-res
unchecked. Apply writes `hires: false; target: false;` unless you opt into
experimental divert.

## Primary GUI: Plasma ScrollFactor

Safe path (default): **no divert**, page scroll always works.

1. Leave **Экспериментально: скорость через divert** unchecked.
2. Keep **Hi-res** unchecked while SmartShift/ratchet is on.
3. Move **Скорость скролла (Plasma)** (0.10× … 2.00×) — same idea as the DPI
   slider. Writes `ScrollFactor` under
   `[Libinput][<vendor>][<product>][<name>]` in `~/.config/kcminputrc` with
   `kwriteconfig6 --notify`.
4. On the Bolt stand the pointer is typically
   `Logitech USB Receiver Mouse` (`1133` / `50504` = `046d:c548`).

Profile field: `plasma_scroll_factor` (also applied on **Применить в cfg**).

You can still tweak the same value in System Settings → **Mouse & Touchpad** →
**Mouse** → **Scroll speed**.

## Safety (divert)

**`target: true` without `up`/`down` Axis swallows the wheel.** Defaults stay
divert **OFF**. CfgWriter refuses orphan divert. Experimental divert forces
**both** axes and turns **hi-res off** (`REL_WHEEL`, not `REL_WHEEL_HI_RES`) so
micro-scroll does not come back through uinput.

If scroll dies after an Apply: set `target: false`, restart `logid`, move the
mouse (Bolt).

## Experimental divert path

Only if Plasma factor is not enough:

```
hiresscroll:
{
  hires: false;
  invert: false;
  target: true;
  up = { mode: "Axis"; axis: "REL_WHEEL"; axis_multiplier: 0.5; };
  down = { mode: "Axis"; axis: "REL_WHEEL"; axis_multiplier: -0.5; };
};
```

Needs **Применить в cfg**. D-Bus cannot set `axis_multiplier`.

## Related

- [hires-scroll.md](hires-scroll.md) — mode bits
- [feature-gap.md](feature-gap.md) — Options+ checklist
- [smartshift.md](smartshift.md) — ratchet / free-spin threshold
