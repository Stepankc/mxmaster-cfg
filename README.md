# MX Master Config (Linux)

[English](README.md) · [Русский](README.ru.md)

Linux GUI for **Logitech MX Master** mice via **[logiops](https://github.com/PixlOne/logiops)** (`logid`):
DPI, SmartShift, hi-res scroll, thumb wheel, real battery %,
button remap, and gesture button (CID `0xc3`).

| | |
|---|---|
| **License** | GPL-3.0-or-later |
| **GUI** | Qt 6 / PySide6 (fits KDE / Kubuntu) |
| **Packages** | Debian / Ubuntu family (buildable `.deb`) |
| **Transport** | Logi Bolt (priority) + Bluetooth |
| **Requires** | **logiops ≥ 0.3** (tested on 0.3.5) |

> Display name: **MX Master Config** · project / package: `mxmaster-cfg`  
> Not an official Logitech product.

![Main window](media/hires-scroll/main-window.png)

## Features

- Device status via privileged helper (`pkexec` + polkit)
- **DPI** get/set (live D-Bus + persist through cfg)
- **SmartShift** on/off + threshold (correct logiops **tri-state** `GetConfig`)
- **Hi-res scroll** (`HiresScroll` / `0x2121`): hires, invert, target/divert
  (default **hires off** with SmartShift → scroll per ratchet notch)
- **Scroll speed**: Plasma `ScrollFactor` slider (safe, no divert); optional
  divert Axis — see [docs/scroll-speed.md](docs/scroll-speed.md)
- **Thumb wheel** (`ThumbWheel` / `0x2150`): divert, invert, left/right/tap presets
- **Battery** % + charging (Unified Battery `0x1004` via short hidraw probe;
  UPower/sysfs when the kernel exposes it; logiops 0.3.5 D-Bus has no Battery)
- **Full button remap** for all remappable CIDs (`0x52`…`0xd7`) + **gesture**
  directions on `0xc3` (persist via `/etc/logid.cfg` + `logid` restart) —
  [docs/buttons.md](docs/buttons.md)
- **Named on-disk profiles** (YAML/JSON) under `~/.config/mxmaster-cfg/profiles/` —
  list / Save as / Load / Apply to device / Delete (not app-specific)
- **Desktop launcher** — Application Menu entry (`.deb` or
  `scripts/install-desktop.sh` → absolute `./run.sh`)
- **Sliders** for DPI / SmartShift (live D-Bus apply, debounced); status poll ~15 s
- After apply with `device_count: 0` — soft USB wake + GUI poll; **Wake receiver**
  button
- Bolt quirk hint (“wiggle the mouse”) when devices disappear after restart
- HID++ conflict check (Solaar / OpenLogi / ratbagd)

## Quick start (Debian / Ubuntu / Kubuntu)

```bash
# 1) Dependencies (apt PySide6 preferred on Kubuntu)
sudo apt install -y \
  python3-pyside6.qtwidgets python3-pyside6.qtcore python3-pyside6.qtgui \
  logiops policykit-1

# 2) Install helper + polkit policy (asks for password once)
cd /path/to/mxmaster-cfg
bash scripts/install-helper.sh

# 3) Ensure logid is running
systemctl status logid --no-pager

# 4) Launch GUI (sets PYTHONPATH)
./run.sh

# 5) Optional: Application Menu → «MX Master Config»
bash scripts/install-desktop.sh
```

If you see `No module named mxmaster_cfg`, you started without `PYTHONPATH=src`.
Use `./run.sh`, or install editable: `python3 -m pip install --user -e .`

More detail: [docs/install.md](docs/install.md) · [docs/run.md](docs/run.md) ·
[docs/desktop.md](docs/desktop.md)

### Helper CLI smoke

```bash
pkexec /usr/libexec/mxmaster-cfg-helper status
pkexec /usr/libexec/mxmaster-cfg-helper get-dpi
pkexec /usr/libexec/mxmaster-cfg-helper set-dpi --dpi 1200
pkexec /usr/libexec/mxmaster-cfg-helper get-smartshift
pkexec /usr/libexec/mxmaster-cfg-helper get-hiresscroll
pkexec /usr/libexec/mxmaster-cfg-helper get-thumbwheel
pkexec /usr/libexec/mxmaster-cfg-helper get-battery
pkexec /usr/libexec/mxmaster-cfg-helper wake-receiver
```

**Apply** in the GUI writes `/etc/logid.cfg` (backup `*.bak.mxmaster`) and restarts `logid`.
Gestures and remap go through **cfg + restart** (live `Button.SetAction` is unreliable on 0.3.5).
See [docs/reconnect.md](docs/reconnect.md) for post-apply Bolt poll / wake.

## Bolt / Bluetooth notes

- After `systemctl restart logid`, Bolt devices may show `device_count: 0` until you
  **move the mouse** (Easy-Switch channel on the Bolt receiver). Soft USB wake of
  `046d:c548` helps, but motion may still be required. The GUI polls and offers
  **Wake receiver**.
- Bluetooth is supported by logiops; primary smoke tests used **Logi Bolt**.
- Only one HID++ owner at a time — quit Solaar/OpenLogi while using this app.

## SmartShift tri-state (important)

logiops `SmartShift.GetConfig` returns mode **2 = on**, **1 = off**, **0 = unset** —
not “any nonzero = on”. See [docs/smartshift.md](docs/smartshift.md).

## Docs

| Topic | English | Russian |
|-------|---------|---------|
| Install helper | [docs/install.md](docs/install.md) | [docs/install.ru.md](docs/install.ru.md) |
| Run / launch | [docs/run.md](docs/run.md) | [docs/run.ru.md](docs/run.ru.md) |
| Desktop launcher | [docs/desktop.md](docs/desktop.md) | [docs/desktop.ru.md](docs/desktop.ru.md) |
| Reconnect / wake | [docs/reconnect.md](docs/reconnect.md) | [docs/reconnect.ru.md](docs/reconnect.ru.md) |
| SmartShift | [docs/smartshift.md](docs/smartshift.md) | [docs/smartshift.ru.md](docs/smartshift.ru.md) |
| Hi-res scroll | [docs/hires-scroll.md](docs/hires-scroll.md) | [docs/hires-scroll.ru.md](docs/hires-scroll.ru.md) |
| Scroll speed | [docs/scroll-speed.md](docs/scroll-speed.md) | [docs/scroll-speed.ru.md](docs/scroll-speed.ru.md) |
| Feature gap | [docs/feature-gap.md](docs/feature-gap.md) | [docs/feature-gap.ru.md](docs/feature-gap.ru.md) |
| Thumb wheel | [docs/thumbwheel.md](docs/thumbwheel.md) | [docs/thumbwheel.ru.md](docs/thumbwheel.ru.md) |
| Battery | [docs/battery.md](docs/battery.md) | [docs/battery.ru.md](docs/battery.ru.md) |
| Button remap | [docs/buttons.md](docs/buttons.md) | [docs/buttons.ru.md](docs/buttons.ru.md) |
| Gestures | [docs/gestures.md](docs/gestures.md) | [docs/gestures.ru.md](docs/gestures.ru.md) |
| Contributing | [CONTRIBUTING.md](CONTRIBUTING.md) | [CONTRIBUTING.ru.md](CONTRIBUTING.ru.md) |

Engineering notes (mostly Russian): `docs/*-notes.md`, plan, spike, runbook.

## Layout

```
.
├── helper/mxmaster-cfg-helper   # root CLI → busctl / cfg+restart
├── polkit/org.mxmaster.cfg.policy
├── src/mxmaster_cfg/            # PySide6 GUI + adapters
├── scripts/install-helper.sh
├── scripts/install-desktop.sh   # user Application Menu → ./run.sh
├── run.sh
├── examples/profiles/
├── packaging/debian/            # buildable .deb (debian → packaging/debian)
├── packaging/icons/             # mxmaster-cfg.svg
└── docs/
```

Profiles are stored per user in `~/.config/mxmaster-cfg/profiles/*.yaml`
(or `.json`). The GUI can save the current settings, reload them later, and
apply a selected profile to the device.

## Packaging (`.deb`)

See [packaging/README.md](packaging/README.md). Depends: `logiops (>= 0.3)`,
`policykit-1`, PySide6 packages, `python3-yaml`, `python3-jsonschema`.

```bash
sudo apt install -y debhelper dh-python pybuild-plugin-pyproject \
  python3-setuptools python3-all python3-yaml python3-jsonschema \
  python3-pyside6.qtwidgets dpkg-dev
./packaging/build-deb.sh
sudo apt install ../mxmaster-cfg_*.deb
```

## License

[GPL-3.0-or-later](LICENSE) — aligned with logiops.
