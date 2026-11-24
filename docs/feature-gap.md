# Feature gap: Options+ / MX Master vs mxmaster-cfg

[English](feature-gap.md) · [Русский](feature-gap.ru.md)

Checklist of Logitech Options+ / MX Master capabilities versus what
**mxmaster-cfg** exposes on Linux (logiops **0.3.5** + helper). Status:

| Status | Meaning |
|--------|---------|
| **done** | Usable in GUI (live D-Bus and/or Apply → cfg) |
| **partial** | Some of the Options+ behavior; caveats |
| **missing** | Not in the app yet; often still possible via logiops/Solaar/manual |
| **impossible** | Not available or not meaningful on Linux with current stack |

Reference hardware: **MX Master 3S** on **Logi Bolt** (Kubuntu). Other family
members noted where they differ.

---

## Pointer / sensor

| Feature | Status | Notes |
|---------|--------|-------|
| DPI get/set | **done** | Live `SetDPI` + cfg `dpi:` |
| DPI steps / range | **partial** | Slider 200–8000 / 50; device may clamp |
| DPI Shift / dual DPI | **missing** | No dedicated “DPI shift while held” UI |
| CycleDPI on button/gesture | **done** | Per-CID picker + gesture Left preset |
| Sensor surface tuning | **impossible** | Not exposed usefully via logiops IPC |

## MagSpeed / SmartShift

| Feature | Status | Notes |
|---------|--------|-------|
| SmartShift on/off | **done** | Tri-state aware (`mode` 2/1/0) |
| SmartShift threshold | **done** | Live + cfg |
| MagSpeed torque / ratchet force | **partial** | GUI torque slider; **TorqueSupport=false** on 3S → not written |
| Always ratchet / always free-spin | **partial** | Approx. via on/off + extreme threshold; not Options+ labels |
| SmartShift Enhanced `0x2111` | **missing** | Newer devices; not wired |

## Main scroll wheel

| Feature | Status | Notes |
|---------|--------|-------|
| Hi-res mode (`0x2121` hires) | **done** | Checkbox → cfg / SetHires |
| Invert vertical scroll | **done** | `invert` |
| Divert wheel to daemon | **done** | `target` (= HID++ Target) |
| Options+-like **scroll speed** | **partial** | **No** HID++ line-speed. GUI writes Plasma `ScrollFactor` (primary). Divert + `axis_multiplier` remains optional/OFF ([scroll-speed.md](scroll-speed.md)) |
| Smooth / ratchet feel | **partial** | SmartShift on + **`hires:false`** = scroll per notch; `hires:true` = micro-scroll between clicks |
| Wheel mode LED / ratchet state UI | **missing** | `GetRatchetState` exists in HID++ backend; not in GUI |
| Divert up/down custom actions | **partial** | Speed path uses Axis; arbitrary Keypress up/down not in GUI |

## Thumb wheel (`0x2150`)

| Feature | Status | Notes |
|---------|--------|-------|
| Divert / invert | **done** | |
| Horizontal scroll (OS) | **done** | Default when divert off |
| Left/right Axis / volume presets | **done** | Presets + free-form Axis / OnInterval Keypress ([thumbwheel.md](thumbwheel.md)) |
| Tap action | **done** | Presets + free-form Keypress; unknown → custom |
| Touch / proxy | **done** | Same picker as tap; round-trip via CfgWriter |
| Haptic | **impossible** | Not in logiops 0.3.5 schema |

## Buttons / remap

| CID (3S spike) | Role | Status |
|----------------|------|--------|
| `0x50` | Left (primary) | **impossible** / N/A | Not in remappable spike list; OS left |
| `0x52` | Middle | **done** | Per-CID action picker ([buttons.md](buttons.md)) |
| `0x53` | Back | **done** | Same picker (default KEY_BACK) |
| `0x56` | Forward | **done** | Same (default KEY_FORWARD) |
| `0xc3` | Gesture button | **done** | Gestures mode + direction presets; or any BasicAction |
| `0xc4` | Mode / SmartShift | **done** | Default ToggleSmartShift; full picker |
| `0xd7` | Extra | **done** | Per-CID picker (default = omit / firmware) |
| Gesture OnInterval / Axis / RawXY | **missing** | Only OnRelease Keypress/CycleDPI/ToggleSS presets |
| Gesture sensitivity / pixels | **missing** | |
| Free-form custom Keypress editor | **done** | Per-CID editor + presets; unknown Keypress loads as custom and round-trips ([buttons.md](buttons.md)) |

## Battery / power

| Feature | Status | Notes |
|---------|--------|-------|
| Battery % | **done** | HID++ Unified Battery `0x1004` probe (+ UPower/sysfs fallback) |
| Charging state | **partial** | Shown when probe reports it |
| Low-battery notification | **missing** | Poll only in GUI |
| Power insights / auto-sleep UI | **impossible** / **missing** | Options+ cloud features N/A |

## Connectivity

| Feature | Status | Notes |
|---------|--------|-------|
| Logi Bolt | **partial** | Works; post-restart often needs motion / soft USB wake |
| Bluetooth | **partial** | logiops supports; less smoke-tested here |
| Easy-Switch channel UI | **missing** | Physical switch only |
| Pairing / unpairing Bolt | **missing** | Use Solaar / logitechctl; out of MVP |
| Multi-host ChangeHost action | **done** | Per-CID picker: hosts 1–3, next/prev, custom host → cfg ([buttons.md](buttons.md)) |

## Flow / desktop integration

| Feature | Status | Notes |
|---------|--------|-------|
| Logitech Flow (multi-PC cursor/clipboard) | **impossible** | Proprietary; no Linux Options+ Flow |
| Actions Ring (MX Master 4) | **impossible** / **missing** | Hardware + Options+; Linux experiments are compositor-specific (out of scope) |
| App-specific profiles | **missing** | Explicitly **out of MVP** (on-disk named profiles only) |
| Cloud sync / Logi account | **impossible** | |

## Firmware / extras

| Feature | Status | Notes |
|---------|--------|-------|
| Firmware update / OTA | **impossible** | Not via logiops; use Windows/macOS or vendor tools |
| Onboard profiles storage UI | **missing** | Device may keep some settings; app uses `/etc/logid.cfg` |
| Conflicts with Solaar/OpenLogi | **done** | Conflict check button |

## Family differences (3 / 3S / 4)

| Topic | MX Master 3 | MX Master 3S | MX Master 4 |
|-------|-------------|--------------|-------------|
| Quiet clicks / sensor | — | 3S quieter / Darkfield updates | Further revisions + Ring |
| Product id (BT example) | `b023` class | `b034` | Newer PIDs — verify |
| SmartShift torque | Often unsupported in logiops IPC | TorqueSupport=false on spike | Check device |
| Actions Ring | No | No | Yes (Options+); Linux gap |
| logiops name match | `"MX Master 3"` | `"MX Master 3S"` | Needs profile `device.name` |
| Bolt hi-res scroll | Kernel/Bolt limits apply | Same (BT better for hi-res) | Verify per kernel |

Device name in cfg must match logiops discovery string.

## Top missing gaps (priority for later)

1. **App-aware profiles** (post-MVP by design)
2. **Bluetooth first-class smoke + Easy-Switch physical-channel discovery UI**
3. **SmartShift Enhanced / torque** on devices that support it
4. **Flow / Actions Ring / firmware** — largely **impossible** on this stack

## Implemented closest to Options+ scroll speed

Plasma **ScrollFactor** slider (live `kcminputrc`) + ratchet-safe **`hires:false`**.
Optional divert Axis — see [scroll-speed.md](scroll-speed.md).
