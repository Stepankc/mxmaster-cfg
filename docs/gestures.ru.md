# Жесты

[English](gestures.md) · [Русский](gestures.ru.md)

Кнопка жестов MX Master (CID **`0xc3`**) настраивается как действие logiops
`Gestures` с направлениями **Up / Down / Left / Right / None** (tap).

В GUI для `0xc3` выберите **«Gesture mode (направления ниже)»** в списке remap;
пресеты направлений появятся под ним.

## Пресеты направлений

- Нет (None)
- Meta + стрелки
- Meta tap
- **CycleDPI** (400…1600)
- **ToggleSmartShift**

Можно назначить `0xc3` и без жестов (Keypress, CycleDPI…) — сетка направлений
тогда отключается.

Остальные remappable CID (`0x52`, `0x53`, `0x56`, `0xc4`, `0xd7`) — тот же
список действий: [buttons.ru.md](buttons.ru.md).

## Persist

Жесты и remap уходят **только** через **cfg + restart `logid`**.

Пример: `examples/profiles/mx-master-3s-default.yaml`.

Скриншот: `media/smartshift-gestures/main-window.png`

Заметки: [smartshift-gestures-notes.md](smartshift-gestures-notes.md).
