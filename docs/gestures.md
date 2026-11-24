# Gestures

[English](gestures.md) · [Русский](gestures.ru.md)

The MX Master gesture button (CID **`0xc3`**) is configured as a logiops
`Gestures` action with directions **Up / Down / Left / Right / None** (tap).

In the GUI, pick **Gesture mode** for CID `0xc3` in the button remap list;
direction presets appear below.

## Direction presets

- None
- Meta + arrow keys
- Meta tap
- **CycleDPI** (400…1600)
- **ToggleSmartShift**

You can also assign a non-gesture action to `0xc3` (Keypress, CycleDPI, …)
via the same remap picker — the direction grid then disables.

Other remappable CIDs (`0x52`, `0x53`, `0x56`, `0xc4`, `0xd7`) use the same
action list — see [buttons.md](buttons.md).

## Persistence

Gestures and remaps are applied **only** via **cfg + `logid` restart**.
Live `Button.SetAction` on logiops 0.3.5 is not reliable for this GUI.

Example profile: `examples/profiles/mx-master-3s-default.yaml`.

Screenshot: `media/smartshift-gestures/main-window.png`

Engineering notes (RU): [smartshift-gestures-notes.md](smartshift-gestures-notes.md).
