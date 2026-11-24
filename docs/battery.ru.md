# Батарея

[English](battery.md) · [Русский](battery.ru.md)

HID++ **Unified Battery** (`0x1004`) — только статус (не настройка cfg).

## Почему D-Bus logiops недостаточно

В пакете **logiops 0.3.5 нет** интерфейса `pizza.pixl.LogiOps.Battery` на
MX Master 3S (Bolt). В introspect устройства — DPI / SmartShift /
HiresScroll / ThumbWheel / Buttons.

## Как mxmaster-cfg читает реальный %

Helper пробует по очереди:

1. **logiops D-Bus** `pizza.pixl.LogiOps.Battery` / свойства Device
   (на будущее; на 0.3.5 пусто)
2. **UPower / sysfs** `power_supply` — часто есть на **Bluetooth**, когда
   ядро отдаёт HID++-батарею; на Bolt + `hid-generic` обычно пусто
3. **Короткий HID++ probe** на **hidraw** ресивера Bolt/Unifying (или BT):
   Root `GetFeature(0x1004)` → `GetStatus` — процент и статус зарядки

### Совместимость с logid (предпочтительно)

На дымовом тесте MX Master 3S **Logi Bolt** у Степана hidraw-probe
**уживается** с запущенным `logid` (сервис не останавливаем). После probe
`GetDPI` продолжает работать.

Если open/xfer не удался (устройство занято), helper может **кратко
остановить и снова запустить** `logid` для одного чтения, затем при
необходимости soft-wake ресивера Bolt. Флаг `--no-hidpp-stop` запрещает
этот fallback.

Solaar для опроса **не** используем (конфликт владельца HID++).

## Helper

```bash
pkexec /usr/libexec/mxmaster-cfg-helper get-battery
pkexec /usr/libexec/mxmaster-cfg-helper get-battery --no-hidpp-stop
pkexec /usr/libexec/mxmaster-cfg-helper status   # батарея в каждом device
```

Пример успешного ответа (Bolt):

```json
{
  "ok": true,
  "battery_available": true,
  "battery": {
    "percent": 30,
    "charging": false,
    "status": "discharging",
    "feature": "0x1004",
    "source": "hidpp:/dev/hidraw4",
    "logid_stopped": false
  }
}
```

`get-battery` возвращает `ok: true` даже при недоступности
(`battery_available: false`), чтобы GUI показал «н/д» без ошибки.

## GUI

В статусе — **процент**, зарядка/разряд/полный и источник
(`HID++ 0x1004`, `UPower`, `sysfs` или D-Bus). «Обновить» повторяет cascade.
