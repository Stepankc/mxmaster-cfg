# Thumb wheel

[English](thumbwheel.md) · [Русский](thumbwheel.ru.md)

Фича `ThumbWheel` / HID++ `0x2150` через logiops.

## GUI

- **Divert** / **Invert** — из `ThumbWheel.GetConfig` (`bb`)
- Пресеты **Left/Right**: omit (скролл ОС), Axis `REL_HWHEEL(_HI_RES)`,
  NoPress (выкл.), громкость (`OnInterval` + `KEY_VOLUME*`)
- Пресеты **Tap**: None / Mute / PlayPause / Meta

Для `left` / `right` / `tap` / `touch` / `proxy` нужен **divert=true**.
Поля **haptic** в схеме cfg logiops 0.3.5 **нет**.

Применить пишет блок `thumbwheel { … }` через `CfgWriter`.

## Helper

```bash
pkexec /usr/local/libexec/mxmaster-cfg-helper get-thumbwheel
pkexec /usr/local/libexec/mxmaster-cfg-helper set-thumbwheel \
  --divert true --invert false
```

Live `SetDivert` / `SetInvert` на Bolt могут timeout; для persist лучше
Применить (cfg + restart). Жесты/действия — только через cfg.
