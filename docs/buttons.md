# Button remap (all CIDs)

[English](buttons.md) · [Русский](buttons.ru.md)

MX Master 3S exposes these **remappable** control IDs (Bolt spike / logiops):

| CID | Role (EN) | Role (RU) |
|-----|-----------|-----------|
| `0x52` | Middle | Средняя |
| `0x53` | Back | Назад |
| `0x56` | Forward | Вперёд |
| `0xc3` | Gesture | Жесты |
| `0xc4` | Mode / SmartShift | Режим / SmartShift |
| `0xd7` | Extra | Доп. |

## GUI

Each CID has an **action picker**:

| Preset | logiops |
|--------|---------|
| Default (OS / firmware) | omit from `buttons:` |
| Disable | `type: "None"` |
| Keypress shortcuts | `Keypress` + common keys (F/B, Super, Alt+Tab, Ctrl+C/V/Z, media…) |
| CycleDPI | `CycleDPI` with 400…1600 |
| ChangeDPI ±50 | `ChangeDPI` + `inc` |
| ToggleSmartShift | `ToggleSmartShift` |
| ToggleHiresScroll | `ToggleHiresScroll` |
| Gesture mode | `Gestures` — **only CID `0xc3`**; directions below |

Gesture button (`0xc3`): when set to **Gesture mode**, Up / Down / Left / Right / Tap
presets stay editable (same as before). Mode button (`0xc4`) defaults to
**ToggleSmartShift**.

## Persistence

Remaps are written only via **Apply → `/etc/logid.cfg` + `logid` restart**
(same path as gestures / hi-res / thumb). Live `Button.SetAction` is not used.

Named on-disk profiles store the full `buttons:` list.

Catalogue: `src/mxmaster_cfg/buttons.py`. Example:
`examples/profiles/mx-master-3s-default.yaml`.
