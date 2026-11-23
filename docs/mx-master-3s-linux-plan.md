# План: Linux-конфигуратор линейки Logitech MX Master

**Проект:** имя TBD · **Для:** Stepan  
**Статус:** утверждён  
**Дата утверждения:** 2026-11-23 (Stepan)  
**Дата:** 2026-11-23 (обновлено: статус утверждён; scaffold + spike runbook)

---

## Решения

Зафиксировано по ответам Stepan’а (2026-11-23):

| # | Тема | Решение |
|---|------|---------|
| 1 | Платформа | **Dev:** Kubuntu (KDE). **Дистрибуция:** пакеты для семейства **Debian + Ubuntu** (основная аудитория). |
| 2 | Транспорт | **Приоритет: Logi Bolt**; **Bluetooth тоже поддерживается** (обязательный второй путь). |
| 3 | База кода | Было «не уверен» — см. рекомендацию ниже: **обёртка/расширение logiops**, не clean-room с нуля. |
| 4 | App-specific профили | **Не в MVP** (post-MVP). |
| 5 | Имя / лицензия | Имя **TBD**. Любая OSI ок; **рекомендация: GPL-3.0-or-later** при пути через logiops (см. § юридический). |
| 6 | Scope устройств | **Линейка MX Master** (не только 3S): device DB / профили под семейство; 3S — первый референс на стенде. |

### Рекомендация: logiops vs свой стек

**Выбрать: wrap/extend logiops (путь A), не clean-room own stack.**

| | Wrap / extend logiops | Clean-room свой HID++ |
|--|----------------------|------------------------|
| Срок до жестов/SmartShift/ремэпа | Недели (GUI + IPC/cfg) | Месяцы (transport, features, divert, Wayland uinput) |
| MX family | Уже знает много HID++ >2.0 устройств | Нужна своя матрица feature/CID на каждую модель |
| Bolt | Есть с v0.3, quirks — править upstream/форк | Писать detection с нуля |
| Лицензия | GPL-3+ copyleft на derivative / связанный daemon | Можно MIT/Apache, но дороже |

**Как именно:** GUI + адаптер, который говорит с **logid** через **D-Bus IPC** (с v0.3) и/или пишет профильный cfg и перезапускает/reloads сервис. При необходимости — **тонкий форк/патчи** logiops (Bolt detection, MX device quirks) с возвратом upstream. Не форкать чужие GUI без лицензии (см. LogiOpsGui).

**Не выбирать clean-room сейчас:** scope уже MX lineup; дублировать зрелый HID++ daemon бессмысленно, пока logiops закрывает MVP-фичи.

---

## 1. Цель и контекст

Сделать удобное Linux-приложение для кастомизации **мышей линейки MX Master** (ремэп кнопок, жесты, SmartShift / MagSpeed, профили на диске). Официальный **Logi Options+** — только Windows/macOS; на Linux расширенная настройка — community-слой поверх **HID++**.

Первый целевой стенд: **MX Master 3S** на Kubuntu; архитектура и device database сразу рассчитаны на соседние MX Master (3 / Business / 4 и т.д.).

Этот документ: решения, обзор существующих решений, архитектура, MVP, лицензии и шаги после фиксации.

---

## 2. Существующие Linux-решения

| Решение | Стек | USB/Bolt | Bluetooth | Сильные стороны | Слабые стороны для MX |
|--------|------|---------|-----------|-----------------|------------------------|
| **logiops** (`logid`) | C++, systemd, `/etc/logid.cfg`, D-Bus IPC с v0.3 | Bolt с v0.3.0, нестабильное обнаружение | Надёжнее Bolt | Жесты, ремэп, SmartShift, hi-res, thumb, DPI | Нет «родного» GUI; Bolt quirks; system daemon |
| **Solaar** | Python, GTK | Хорошо (pairing Bolt) | Да | Батарея, pairing, HID++ settings | UX не Options+; Wayland rules ограничены |
| **piper + ratbagd** | GTK + libratbag | Bolt часто **игнорируется** | Да | Простой DPI/кнопки | Нет жестов/SmartShift уровня Options+ |
| **OpenLogi** | Rust, user agent, GUI | Bolt / Unifying / BT | Да | Options+-like UX | MX-фичи ещё дырявые / нестабильны |
| **LogiOpsGui** | GUI над logiops | как logiops | как logiops | Профили без ручного cfg | Зрелость ограничена; **лицензия у популярного репо отсутствует** |
| Прочее | hidpp / logiops-rs / logi-mx | разное | разное | Референс | Не готовый продукт |

**Вывод:** для MVP backend — **logiops**; Solaar — референс pairing/батареи; OpenLogi — опциональный spike; piper — не основной путь.

---

## 3. Как MX Master управляется на Linux

### 3.1 Транспорт

1. HID → `/dev/hidraw*` (Bolt/Unifying или Bluetooth/`uhid`).
2. Софт ↔ **HID++ 2.0+** short/long reports.
3. Клики/движение — `evdev`/`libinput`; кастом — **divert** + демон.

Ориентиры 3S: BT **`046d:b034`**; Bolt receiver часто **`046d:c548`**.

**Приоритет проекта:** стабилизировать **Bolt** первым; BT — обязательный fallback и часто более предсказуемый для hi-res scroll.

### 3.2 Ключевые HID++ features (семейство MX; 3S как референс)

| Feature ID | Назначение |
|------------|------------|
| `0x0000` Root | Discovery |
| `0x1B04` Reprog Controls V4 | Ремэп / divert / Raw XY |
| `0x2110` / `0x2111` SmartShift (+ Enhanced) | Ratchet ↔ free-spin, torque |
| `0x2121` HiRes Wheel | Hi-res / invert / divert |
| `0x2150` Thumbwheel | Горизонтальное колесо |
| `0x2201` Adjustable DPI | DPI |
| `0x1004` Unified Battery | Батарея |

Типичные CID 3S: `0x52` middle, `0x53` back, `0x56` forward, `0xc3` gesture, `0xc4` mode. Другие MX — через device DB (CID/feature matrix), не хардкод одной модели.

### 3.3 Права и udev

- rw на `/dev/hidraw*`;
- rw на `/dev/uinput` (Wayland-симуляция);
- иногда read `/dev/input/event*`.

Пакет Debian/Ubuntu: udev rules + systemd unit; после установки — переподключить мышь/ресивер.

**Конфликт:** один owner HID++ пайпа (не вместе с Solaar/OpenLogi на том же устройстве) — явная проверка в GUI.

---

## 4. Архитектура (после решений)

### 4.1 daemon + GUI

```
┌──────────────┐   D-Bus / cfg reload   ┌─────────────────────┐
│ GUI (user)   │ ◄────────────────────► │ logid (system)      │
│ Qt / KDE-     │   профили, статус      │ + наш тонкий adapter │
│ friendly     │                         │ HID++ / uinput       │
└──────────────┘                         └──────────┬──────────┘
                                                    │ hidraw
                                         ┌──────────▼──────────┐
                                         │ MX Master (Bolt/BT) │
                                         └─────────────────────┘
```

Фон нужен для divert/жестов; GUI переживает закрытие окна.

### 4.2 Стратегия реализации

**Фаза 1 (утверждено рекомендацией): GUI + обёртка над logiops.**

| Вариант | Статус |
|---------|--------|
| **A. GUI над logiops** (+ патчи при необходимости) | **Выбран для MVP** |
| B. OpenLogi | Опциональный spike сравнения; не база |
| C. Свой HID++ с нуля | Отклонён на текущем этапе |
| D. Только Solaar rules | Не цель |

**GUI toolkit (Kubuntu/KDE):** предпочтительно **Qt 6** (PySide6 или C++/QML) — родной look на KDE; GTK4/libadwaita допустим, но вторичен для основного DE разработчика.

**Упаковка:** `.deb` / PPA или простой apt-совместимый пакет под Debian/Ubuntu; logiops — dependency (`Depends:`) или vendored/forked binary с GPL-обязательствами.

**Конфиг:** TOML/YAML в `~/.config/<project>/` → трансляция в logiops cfg или D-Bus apply; экспорт/импорт профилей.

### 4.3 Позиционирование

Не клон Options+. **Лучший Linux-контроллер линейки MX Master:** понятный GUI, Bolt-first + BT, жесты и MagSpeed без ручного cfg.

---

## 5. MVP vs позже

### MVP

1. Обнаружение устройств линейки MX (Bolt приоритет, BT обязателен), статус, батарея.
2. DPI.
3. SmartShift / MagSpeed: on/off, threshold, torque (если feature есть).
4. Hi-res scroll + invert.
5. Ремэп основных кнопок → клавиши / media / mouse buttons.
6. Базовые жесты на gesture button (↑↓←→ + tap).
7. Профиль на диск, apply без перезагрузки ОС.
8. deb-установка: udev + systemd + зависимость от logiops (или наш форк).
9. Блокировка конфликта с другим HID++ owner.
10. Device DB: минимум 3S полностью; заготовки под соседние MX Master.

### Позже (post-MVP)

- **App-specific профили** (явно отложены).
- Thumb wheel actions, advanced gestures.
- Несколько устройств / Easy-Switch UI.
- Actions Ring (compositor-зависимый).
- Расширение матрицы MX (4 haptics и т.д.), tray, Flatpak (с оговорками hidraw).

### Вне scope

- Logitech Flow / облако Options+.
- Полный клон UI Options+.
- Firmware OTA.
- Gaming RGB / не-MX линейки.

---

## 6. Лицензии: факты и обязательства

*Не юридическая консультация; факты по публичным LICENSE/заголовкам на 2026-11-23.*

### logiops (PixlOne/logiops)

- SPDX по GitHub: **GPL-3.0**; в исходниках: **GPL-3.0-or-later** («v3 or any later version»).
- Debian copyright: **GPL-3+**.
- **Можно** форкать, модифицировать, распространять — легально и ожидаемо.
- **Обязательства copyleft (кратко):**
  - при распространении бинарников — **соответствующий исходный код**;
  - сохранять copyright / LICENSE notices;
  - **модифицированные версии и производные работы** — под **GPL-3+**;
  - нельзя добавить проприетарные ограничения на весь «covered work».
- **Обёртка отдельным процессом (D-Bus / cfg):** GUI как отдельная программа обычно может быть под другой OSI-лицензией; сам **logid**/форк остаётся GPL-3+. При сомнении (общий процесс, статическая линковка, сильное слияние) — лицензировать **весь продукт GPL-3.0-or-later**.

### LogiOpsGui

| Репозиторий | Лицензия | Вывод |
|-------------|----------|--------|
| **matthewmoonen/LogiOpsGui** | **Нет LICENSE** (`license: null` на GitHub) | **Не форкать и не копировать код** без явного разрешения автора |
| **Eko450-eng/LogiOpsGui** | **MIT** | Форк/заимствование кода ок по MIT; проект WIP — лучше идеи/референс, не база |

### Рекомендация по лицензии проекта

- **Путь A (выбран):** основной репозиторий / daemon-форк — **GPL-3.0-or-later** (согласовано с logiops). GUI-клиент: либо тоже **GPL-3.0-or-later** (проще одна схема), либо MIT/Apache **только** если строго отдельный IPC-клиент без линковки GPL-кода.
- Clean-room путь (отклонён): имел бы смысл MIT/Apache-2.0 — сейчас не актуален.

Товарные знаки: не называть продукт «Logitech»/«Logi Options»; «для MX Master» в описании — ок (уточнить при релизе).

---

## 7. Шаги дальше

1. ~~Решения Stepan’а~~ — зафиксированы в § Решения; **план утверждён 2026-11-23**.
2. ~~Скелет репо~~ — scaffold в `scaffold/` (PySide6 + logiops adapter + deb/udev/systemd sketch).
3. **Стенд Kubuntu (Stepan):** MX Master 3S на **Bolt и BT**; см. `docs/hardware-spike-runbook.md`.
4. **Spike:** стабильный apply через logiops на Bolt (приоритет) и BT; SmartShift/жесты → заполнить `docs/spike-findings.md`.
5. **Имя проекта** (осталось TBD) → репо + SPDX в LICENSE.
6. MVP vertical slice: батарея + DPI + один remap на Wayland/KDE.
7. Добить MVP §5; тест-лист Bolt/BT/suspend/reconnect; матрица MX.
8. (Опционально) PR upstream logiops по Bolt detection.

Критерий MVP: без ручного cfg настроить кнопки, жесты и SmartShift на Bolt (и BT) и сохранить после перезагрузки.

---

## 8. Открытые вопросы (остаток)

| # | Вопрос | Статус |
|---|--------|--------|
| 1 | Имя проекта | **TBD** (блокер только для брендинга/репо-имени, не для spike) |
| 2 | GUI: PySide6 vs C++/QML | **Выбрано PySide6** для MVP (быстрее итерации; см. `scaffold/README.md`) |
| 3 | logiops: system package Depends vs vendor/fork в дереве | Решить после spike Bolt |
| 4 | Юр. review перед широким релизом | По желанию |

---

## 9. Краткий вердикт

- **Решения:** Kubuntu + deb для Debian/Ubuntu; Bolt-first + BT; MX lineup; app-profiles не в MVP; имя TBD.
- **База:** **wrap/extend logiops** (GPL-3+); не писать HID++ с нуля.
- **Лицензия продукта:** **GPL-3.0-or-later** (согласовано с зависимостью).
- **GUI:** Qt 6 / **PySide6** под KDE; не Electron.
- **Дальше:** spike на железе Stepan’а (`docs/hardware-spike-runbook.md`); каркас уже в `scaffold/`.

Сырые заметки: `internal/mx-master-3s-research-notes.md`.  
Лицензионная выжимка: `internal/logiops-license-decision.md`.
