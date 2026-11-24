# Hi-res scroll

[English](hires-scroll.md) · [Русский](hires-scroll.ru.md)

Фича `HiresScroll` / HID++ `0x2121` через logiops.

## GUI

Чекбоксы: **hires**, **invert**, **target / divert**, плюс опционально
**скорость через divert** (слайдер Axis `axis_multiplier`).

Обновить читает `HiresScroll.GetConfig` → `bbb` (hires, invert, target).
Применить пишет блок `hiresscroll { … }` через `CfgWriter`.

В cfg logiops 0.3.5 **нет** отдельного `divert`: HID++ `Mode::Target` =
libconfig **`target`**.

В отличие от SmartShift, unset `getConfig` отдаёт дефолты
`{true, false, false}` (не tri-state).

**Скорость скролла** — не бит режима `0x2121`: см. [scroll-speed.ru.md](scroll-speed.ru.md).

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
