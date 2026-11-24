# Remap кнопок (все CID)

[English](buttons.md) · [Русский](buttons.ru.md)

На MX Master 3S (Bolt spike / logiops) remappable:

| CID | Роль |
|-----|------|
| `0x52` | Средняя / Middle |
| `0x53` | Назад / Back |
| `0x56` | Вперёд / Forward |
| `0xc3` | Жесты / Gesture |
| `0xc4` | Режим / SmartShift |
| `0xd7` | Доп. / Extra |

## GUI

У каждой кнопки — **выбор действия**:

| Пресет | logiops |
|--------|---------|
| По умолчанию (ОС / firmware) | не писать в `buttons:` |
| Отключить | `type: "None"` |
| **Keypress (записать)** | Кнопка **Записать**, затем chord на клавиатуре. Модификаторы + клавиша через Qt → `Keypress` `KEY_*`. Неизвестный Keypress из cfg/профиля загружается сюда; перезапись — снова «Записать». |
| Keypress (ярлыки) | F/B, Super, Alt+Tab, Ctrl+C/V/Z, media… |
| CycleDPI | 400…1600 |
| ChangeDPI ±50 | `inc` |
| ToggleSmartShift | как в примерах logiops |
| ToggleHiresScroll | переключить hi-res |
| **ChangeHost** | Канал Easy-Switch: host `1` / `2` / `3`, или `next` / `prev`. Свой host — отдельное поле. |
| Режим жестов | `Gestures` — **только `0xc3`**; направления ниже |

Кнопка жестов (`0xc3`): при «Gesture mode» остаются пресеты
Вверх / Вниз / Влево / Вправо / Tap. Кнопка режима (`0xc4`) по умолчанию —
**ToggleSmartShift**.

### Захват Keypress

1. Выберите **Keypress (записать… / record)**.
2. Нажмите **Записать** — строка «Нажмите клавиши…».
3. Зажмите модификаторы и нажмите основную клавишу (например Ctrl+X).
   Аккорд показывается как `KEY_LEFTCTRL + KEY_X` и уходит в cfg при Apply.
4. **Esc** (или **Отмена**) — выход из режима записи **без** смены аккорда.
5. **Очистить** — сброс. Снова **Записать** — перезапись.

Ручной ввод имён `KEY_*` — не основной путь.

### ChangeHost

В cfg `host` — **1-based** индекс канала или строки `next` / `prev`
(`previous` при загрузке → `prev`). Нужна фича HID++ ChangeHost. Смена
хоста может убрать мышь из D-Bus на этой машине, пока не переключите
обратно.

## Persist

Только через **«Применить в cfg»** → `/etc/logid.cfg` + restart `logid`.
Профили на диске сохраняют полный список `buttons:`.

Код: `src/mxmaster_cfg/buttons.py`, захват
`src/mxmaster_cfg/key_capture.py`. Пример:
`examples/profiles/mx-master-3s-default.yaml`.
