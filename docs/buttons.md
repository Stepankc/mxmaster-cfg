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
| **Keypress (record)** | Press **Record / Записать**, then play the chord on the keyboard. Modifiers + key are captured via Qt and stored as `Keypress` `KEY_*`. Unknown Keypress from cfg/profile loads here; re-record to replace. |
| Keypress shortcuts | Common presets (F/B, Super, Alt+Tab, Ctrl+C/V/Z, media…) |
| CycleDPI | `CycleDPI` with 400…1600 |
| ChangeDPI ±50 | `ChangeDPI` + `inc` |
| ToggleSmartShift | `ToggleSmartShift` |
| ToggleHiresScroll | `ToggleHiresScroll` |
| **ChangeHost** | Easy-Switch channel: host `1` / `2` / `3`, or `next` / `prev`. Custom host field for other values. |
| Gesture mode | `Gestures` — **only CID `0xc3`**; directions below |

Gesture button (`0xc3`): when set to **Gesture mode**, Up / Down / Left / Right / Tap
presets stay editable (same as before). Mode button (`0xc4`) defaults to
**ToggleSmartShift**.

### Keypress capture

1. Choose **Keypress (записать… / record)**.
2. Click **Записать** — the row shows “press keys…”.
3. Hold modifiers and press the main key (e.g. Ctrl+X). The chord appears as
   `KEY_LEFTCTRL + KEY_X` and is written on Apply as a normal Keypress action.
4. **Esc** (or **Отмена**) cancels listening and keeps the previous chord.
5. **Очистить** clears the chord. Click **Записать** again to re-capture.

Typing `KEY_*` names by hand is not the primary path.

### ChangeHost

logiops `ChangeHost.host` is **1-based** channel index, or the strings
`next` / `prev` (`previous` accepted on load → `prev`). Requires HID++
ChangeHost on the device (Easy-Switch). Switching host may drop the mouse
from this PC’s D-Bus tree until you switch back.

## Persistence

Remaps are written only via **Apply → `/etc/logid.cfg` + `logid` restart**
(same path as gestures / hi-res / thumb). Live `Button.SetAction` is not used.

Named on-disk profiles store the full `buttons:` list.

Catalogue: `src/mxmaster_cfg/buttons.py`, capture map
`src/mxmaster_cfg/key_capture.py`. Example:
`examples/profiles/mx-master-3s-default.yaml`.
