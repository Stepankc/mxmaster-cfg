# Скорость скролла

[English](scroll-speed.md) · [Русский](scroll-speed.ru.md)

Как устроены «скорость скролла» и ощущение трещотки у MX Master 3S при
**logiops 0.3.5** и **Kubuntu / Plasma 6 (Wayland)**.

## Кратко

| Слой | Что даёт | В mxmaster-cfg? |
|------|----------|-----------------|
| HID++ `0x2121` HiRes Wheel | Биты: **hires**, **invert**, **target**. **`hires:true` = микроскролл между щелчками трещотки**; `hires:false` = скролл на дискретный щелчок. Поля Options+ «строк на щелчок» нет. | Чекбокс hi-res (по умолчанию **ВЫКЛ** с SmartShift) |
| Plasma `ScrollFactor` | Масштаб прокрутки для указателя libinput (`kcminputrc`). | **Основной** слайдер как DPI — live, без divert |
| logiops divert + Axis | `target:true` + `up`/`down` `axis_multiplier` снова шлёт `REL_WHEEL` / `REL_WHEEL_HI_RES`. | Опциональный экспериментальный чекбокс (обе оси или `target:false`) |
| SmartShift threshold | Когда включается free-spin — **не** строки на щелчок. | Слайдер threshold |

## Трещотка = скролл по щелчку (не микроскролл)

При **включённом SmartShift** держите **hi-res ВЫКЛ**.

- `hires: true` отдаёт hi-res движение → страница едет от малейшего движения
  пальца, даже когда трещотка включена.
- `hires: false` → один щелчок MagSpeed ≈ один шаг `REL_WHEEL`.

GUI сбрасывает hi-res при включении SmartShift и по умолчанию держит его
выключенным. Apply пишет `hires: false; target: false;`, пока не включён
экспериментальный divert.

## Основной GUI: Plasma ScrollFactor

Безопасный путь (по умолчанию): **без divert**, страница всегда скроллится.

1. **Экспериментально: скорость через divert** — снят.
2. **Hi-res** — снят, пока включён SmartShift/ratchet.
3. Слайдер **Скорость скролла (Plasma)** (0.10× … 2.00×) — как DPI. Пишет
   `ScrollFactor` в `~/.config/kcminputrc` через `kwriteconfig6 --notify`.
4. На стенде Bolt указатель обычно
   `Logitech USB Receiver Mouse` (`1133` / `50504` = `046d:c548`).

Поле профиля: `plasma_scroll_factor` (также при **Применить в cfg**).

Тот же параметр: Параметры системы → **Мышь и тачпад** → **Мышь** →
**Скорость прокрутки**.

## Безопасность (divert)

**`target: true` без `up`/`down` Axis глотает колесо.** Divert по умолчанию
**ВЫКЛ**. CfgWriter не пишет orphan divert. Экспериментальный divert всегда
ставит **обе** оси и **гасит hi-res** (`REL_WHEEL`, не `HI_RES`).

Если скролл пропал: `target: false`, restart `logid`, пошевелите мышь (Bolt).

## Экспериментальный divert

Только если Plasma-фактора мало:

```
hiresscroll:
{
  hires: false;
  invert: false;
  target: true;
  up = { mode: "Axis"; axis: "REL_WHEEL"; axis_multiplier: 0.5; };
  down = { mode: "Axis"; axis: "REL_WHEEL"; axis_multiplier: -0.5; };
};
```

Нужен **Применить в cfg**. D-Bus не задаёт `axis_multiplier`.

## Связанное

- [hires-scroll.ru.md](hires-scroll.ru.md) — биты режима
- [feature-gap.ru.md](feature-gap.ru.md) — чеклист Options+
- [smartshift.ru.md](smartshift.ru.md) — порог ratchet / free-spin
