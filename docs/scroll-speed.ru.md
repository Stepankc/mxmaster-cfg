# Скорость скролла

[English](scroll-speed.md) · [Русский](scroll-speed.ru.md)

Как устроена «скорость скролла» у MX Master 3S при **logiops 0.3.5** и Linux.

## Кратко

| Слой | Что даёт | В mxmaster-cfg? |
|------|----------|-----------------|
| HID++ `0x2121` HiRes Wheel | Только биты режима: **hires**, **invert**, **target** (divert). В capabilities есть **multiplier** прошивки (его использует logiops для Axis). Поля «строк на щелчок» / Options+ scroll speed **нет**. | Чекбоксы hires / invert / target |
| logiops divert + Axis | При `target: true` жесты `up`/`down` с `axis_multiplier` снова шлют `REL_WHEEL` или `REL_WHEEL_HI_RES` (PixlOne/logiops [#116](https://github.com/PixlOne/logiops/issues/116)). | Чекбокс **скорости** + слайдер множителя → cfg |
| Ядро / libinput / DE | Как события колеса становятся пикселями/строками (hwdb, quirks, Scroll speed в KDE). | Только документация — приложение это не пишет |

**Не** делаем «пустой» слайдер, который ничего не меняет в прошивке. Без divert — путь ОС ниже.

## GUI (путь divert)

1. Включите **Скорость через divert (Axis multiplier)** — принудительно `target: true`.
2. Задайте **Множитель** (0.25× … 4.00×). `1.00×` — базовая шкала divert.
3. Нажмите **Применить в cfg** (restart `logid`). D-Bus `SetHires` / `SetInvert` / `SetTarget` не задают `axis_multiplier`; `SetUp`/`SetDown` выбирают только *тип* жеста.

Пример cfg (hires вкл.):

```
hiresscroll:
{
  hires: true;
  invert: false;
  target: true;
  up = { mode: "Axis"; axis: "REL_WHEEL_HI_RES"; axis_multiplier: 1.5; };
  down = { mode: "Axis"; axis: "REL_WHEEL_HI_RES"; axis_multiplier: -1.5; };
};
```

При `hires: false` ось — `REL_WHEEL`.

Поле профиля: `hiresscroll.scroll_multiplier` (или явные `up`/`down`).

## Путь ОС (без divert)

При `target: false` logiops не масштабирует величину скролла.

**Kubuntu / KDE Plasma 6:**

1. Параметры системы → **Мышь и тачпад** → **Мышь**
2. Ползунок **Скорость прокрутки** (формулировка может чуть отличаться)

Это зона композитора/libinput, не HID++.

**libinput / udev (для продвинутых):**

- Через Bolt часто только low-res шаги; Bluetooth чаще отдаёт hi-res (ArchWiki *Logitech MX Master*).
- Опционально hwdb (`MOUSE_WHEEL_CLICK_*`) или `local-overrides.quirks` — см. [hires-scroll.ru.md](hires-scroll.ru.md).

## Аналоги Solaar / ratbag

| Инструмент | Примерно |
|------------|----------|
| Solaar «Scroll Wheel Resolution» | ≈ `hires` (драйвер ядра может конфликтовать — часто лучше Ignore) |
| Solaar invert / divert | ≈ `invert` / `target` |
| Options+ «Scroll speed» | **ОС + софт** на Windows/macOS; на Linux **нет** переносимого HID++ setpoint |
| piper / libratbag | DPI/кнопки; не UX скорости MagSpeed |

## Связанное

- [hires-scroll.ru.md](hires-scroll.ru.md) — биты режима
- [feature-gap.ru.md](feature-gap.ru.md) — полный чеклист Options+
- [smartshift.ru.md](smartshift.ru.md) — порог ratchet / free-spin (не скорость строк)
