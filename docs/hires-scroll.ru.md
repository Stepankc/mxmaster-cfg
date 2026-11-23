# Hi-res scroll

[English](hires-scroll.md) · [Русский](hires-scroll.ru.md)

Фича `HiresScroll` / HID++ `0x2121` через logiops.

## GUI

Чекбоксы: **hires**, **invert**, **target / divert**.

Обновить читает `HiresScroll.GetConfig` → `bbb` (hires, invert, target).
Применить пишет блок `hiresscroll { … }` через `CfgWriter`.

В cfg logiops 0.3.5 **нет** отдельного `divert`: HID++ `Mode::Target` =
libconfig **`target`**.

В отличие от SmartShift, unset `getConfig` отдаёт дефолты
`{true, false, false}` (не tri-state).

## Helper

```bash
pkexec /usr/local/libexec/mxmaster-cfg-helper get-hiresscroll
pkexec /usr/local/libexec/mxmaster-cfg-helper set-hiresscroll \
  --hires true --invert false --target false
```

Live `SetHires` / `SetInvert` / `SetTarget` на Bolt часто timeout; для
persist лучше Применить (cfg + restart).

Скриншот: `media/hires-scroll/main-window.png`

Заметки: [hires-scroll-notes.md](hires-scroll-notes.md).
