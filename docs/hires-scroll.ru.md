# Hi-res scroll

[English](hires-scroll.md) · [Русский](hires-scroll.ru.md)

Фича `HiresScroll` / HID++ `0x2121` через logiops.

## GUI

Чекбоксы: **hires**, **invert**, **target / divert**, плюс опционально
множитель divert Axis. По умолчанию **hi-res ВЫКЛ** при SmartShift — режим
трещотки скроллит **по щелчку**, а не от микродвижений между щелчками.

Обновить читает `HiresScroll.GetConfig` → `bbb` (hires, invert, target).
Применить пишет блок `hiresscroll { … }` через `CfgWriter`.

В cfg logiops 0.3.5 **нет** отдельного `divert`: HID++ `Mode::Target` =
libconfig **`target`**.

Unset `getConfig` в logiops отдаёт `{true, false, false}`, но mxmaster-cfg
по умолчанию ставит **`hires: false`** для дискретных щелчков MagSpeed.

**Скорость скролла** (строк на щелчок) — не бит `0x2121`: слайдер Plasma
ScrollFactor; см. [scroll-speed.ru.md](scroll-speed.ru.md).

## Helper

```bash
pkexec /usr/libexec/mxmaster-cfg-helper get-hiresscroll
pkexec /usr/libexec/mxmaster-cfg-helper set-hiresscroll \
  --hires true --invert false --target false
```

Live `SetHires` / `SetInvert` / `SetTarget` на Bolt часто timeout; для
persist лучше Применить (cfg + restart).

Скриншот: `media/hires-scroll/main-window.png`

Заметки: [hires-scroll-notes.md](hires-scroll-notes.md).
