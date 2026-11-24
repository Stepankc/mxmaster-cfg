# Thumb wheel

[English](thumbwheel.md) · [Русский](thumbwheel.ru.md)

Фича `ThumbWheel` / HID++ `0x2150` через logiops.

## GUI

- **Divert** / **Invert** — из `ThumbWheel.GetConfig` (`bb`)
- Пресеты **Left/Right**: omit (скролл ОС), Axis `REL_HWHEEL(_HI_RES)`,
  NoPress (выкл.), громкость (`OnInterval` + `KEY_VOLUME*`)
- **Свободный Axis** — имя оси + `|axis_multiplier|` (left − / right +)
- **Свободный OnInterval Keypress** — interval + chord `KEY_*`
- **Tap / Touch / Proxy** — пресеты (None / Mute / PlayPause / Meta) и
  свободный Keypress; неизвестные значения из профиля/cfg → «свой»

Для `left` / `right` / `tap` / `touch` / `proxy` нужен **divert=true**.
Поля **haptic** в схеме cfg logiops 0.3.5 **нет**.

Применить пишет блок `thumbwheel { … }` через `CfgWriter`. Round-trip:
профиль → writer → apply-cfg. Live `SetDivert` / `SetInvert` на Bolt могут
timeout; жесты/действия — только через cfg.

## Helper

```bash
pkexec /usr/libexec/mxmaster-cfg-helper get-thumbwheel
pkexec /usr/libexec/mxmaster-cfg-helper set-thumbwheel \
  --divert true --invert false
```
