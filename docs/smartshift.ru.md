# SmartShift

[English](smartshift.md) · [Русский](smartshift.ru.md)

MagSpeed / SmartShift доступен через D-Bus `SmartShift` в logiops и блок
`smartshift { … }` в `/etc/logid.cfg`.

## GUI

- Чекбокс: SmartShift **вкл**
- Spinbox: **threshold** (1–50)
- **Torque**: есть в UI, но disabled при `TorqueSupport=false` (MX Master 3S) —
  в cfg torque не пишется

Live `SetActive` / `SetThreshold` на Bolt часто timeout; авторитетны
**readback** и **Применить (cfg + restart)**.

## Tri-state GetConfig (важно)

`SmartShift.GetConfig` возвращает `yyy` = **mode, threshold, torque**.
Первый байт — **tri-state конфиг**, не «сырой» HID++:

| mode | Смысл |
|------|--------|
| **2** | `on: true` |
| **1** | `on: false` |
| **0** | `on` unset (`SetActive` с `clear=true`) |

Нельзя считать `mode != 0` за «вкл» — тогда **выкл (1)** показывается как вкл,
и после Apply→Refresh галочка «не держится».

`SetActive(active, clear)`: `clear=true` **сбрасывает** `on` (mode 0),
а не выключает. Для on/off всегда `clear=false`.

В приложении: галочка ↔ mode 2; снята ↔ mode 1.

Подробные заметки: [smartshift-gestures-notes.md](smartshift-gestures-notes.md).
