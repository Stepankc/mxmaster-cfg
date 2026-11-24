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
| **Keypress (свой)** | Свободный ввод `KEY_*` + модификаторы (`Ctrl+X`, …). Неизвестный Keypress из cfg/профиля загружается сюда и round-trip’ится. |
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

### Свободный Keypress

Ключи через `+`, запятую или пробел. Имена без префикса нормализуются в
`KEY_*`. Модификаторы — обычные коды в списке (chord logiops).

### ChangeHost

В cfg `host` — **1-based** индекс канала или строки `next` / `prev`
(`previous` при загрузке → `prev`). Нужна фича HID++ ChangeHost. Смена
хоста может убрать мышь из D-Bus на этой машине, пока не переключите
обратно.

## Persist

Только через **«Применить в cfg»** → `/etc/logid.cfg` + restart `logid`.
Профили на диске сохраняют полный список `buttons:`.

Код: `src/mxmaster_cfg/buttons.py`. Пример:
`examples/profiles/mx-master-3s-default.yaml`.
