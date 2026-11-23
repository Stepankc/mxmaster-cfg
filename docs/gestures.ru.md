# Жесты

[English](gestures.md) · [Русский](gestures.ru.md)

Кнопка жестов MX Master (CID **`0xc3`**) настраивается как действие logiops
`Gestures` с направлениями **Up / Down / Left / Right / None** (tap).

## Пресеты в GUI

- Нет (None)
- Meta + стрелки
- Meta tap
- **CycleDPI** (400…1600)
- **ToggleSmartShift**

Remap Forward / Back — CID `0x56` / `0x53`.

## Persist

Жесты и remap уходят **только** через **cfg + restart `logid`**.
Live `Button.SetAction` на logiops 0.3.5 для GUI ненадёжен.

Пример профиля: `examples/profiles/mx-master-3s-default.yaml`.

Скриншот: `media/smartshift-gestures/main-window.png`

Заметки: [smartshift-gestures-notes.md](smartshift-gestures-notes.md).
