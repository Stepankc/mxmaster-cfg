# Gestures

[English](gestures.md) · [Русский](gestures.ru.md)

The MX Master gesture button (CID **`0xc3`**) is configured as a logiops
`Gestures` action with directions **Up / Down / Left / Right / None** (tap).

## GUI presets

- None
- Meta + arrow keys
- Meta tap
- **CycleDPI** (400…1600)
- **ToggleSmartShift**

Forward / Back remaps use CIDs `0x56` / `0x53`.

## Persistence

Gestures and remaps are applied **only** via **cfg + `logid` restart**.
Live `Button.SetAction` on logiops 0.3.5 is not reliable for this GUI.

Example profile: `examples/profiles/mx-master-3s-default.yaml`.

Screenshot: `media/smartshift-gestures/main-window.png`

Engineering notes (RU): [smartshift-gestures-notes.md](smartshift-gestures-notes.md).
