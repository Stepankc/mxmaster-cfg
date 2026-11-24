# Батарея

[English](battery.md) · [Русский](battery.ru.md)

HID++ **Unified Battery** (`0x1004`) — только статус (не настройка cfg).

## Что отдаёт logiops 0.3.5

В пакете **logiops 0.3.5 нет** интерфейса `pizza.pixl.LogiOps.Battery` на
MX Master 3S (Bolt). В introspect устройства — DPI / SmartShift /
HiresScroll / ThumbWheel / Buttons.

Helper всё равно **пробивает**:

1. методы Get* на `pizza.pixl.LogiOps.Battery` (на будущее)
2. свойства Device вроде `BatteryPercentage` / `BatteryLevel`

Если ничего нет, в статусе GUI — **н/д** с короткой причиной.
«Обновить» повторяет probe.

## Helper

```bash
pkexec /usr/local/libexec/mxmaster-cfg-helper get-battery
pkexec /usr/local/libexec/mxmaster-cfg-helper status   # батарея в каждом device
```

`get-battery` возвращает `ok: true` даже при недоступности
(`battery_available: false`), чтобы GUI показал «н/д» без ошибки.
