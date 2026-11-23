# Project preferences — MX Master Linux configurator

Reusable decisions for workers (Stepan / Project «logitech mx Master 3s»).

## Platform

- **Dev machine:** Kubuntu (KDE Plasma).
- **Target packages:** Debian + Ubuntu family (`.deb` / apt-compatible). Majority users assumed on this family.
- **GUI toolkit preference:** Qt 6 (PySide6 or C++/QML) — matches KDE. Avoid Electron/Tauri for MVP.

## Product scope

- **Devices:** MX Master lineup (not 3S-only). First hardware reference: MX Master 3S.
- **Transport:** Logi Bolt first priority; Bluetooth also required.
- **App-specific profiles:** out of MVP (post-MVP only).
- **Project name:** `mxmaster-cfg` — display title **MX Master Config (Linux)**.
- **GitHub:** https://github.com/Stepankc/mxmaster-cfg

## Architecture / licensing

- **Backend path:** wrap/extend **logiops** (`logid`) via D-Bus IPC and/or cfg apply; thin fork/patches OK; no clean-room HID++ stack for now.
- **Do not copy** matthewmoonen/LogiOpsGui code (no LICENSE). Eko450-eng/LogiOpsGui is MIT but WIP — reference only unless explicitly adopted.
- **Recommended project license:** **GPL-3.0-or-later** (aligned with logiops GPL-3+).
- One HID++ owner at a time; detect conflict with Solaar/OpenLogi.

## Out of MVP / out of scope

- App-aware profiles (later).
- Flow, Options+ clone UI, firmware OTA, non-MX lines.
