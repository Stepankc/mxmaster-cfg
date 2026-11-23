# SmartShift + gestures UI — заметки (LMMS-7)

**Стенд:** Kubuntu · logiops **0.3.5** · MX Master 3S Bolt  
**Дата:** 2026-11-23  
**База:** MVP slice (LMMS-5) в `scaffold/`

Связано: [`mvp-slice-notes.md`](./mvp-slice-notes.md), [`spike-findings.md`](./spike-findings.md).

---

## Что добавлено

1. **SmartShift / MagSpeed в GUI**
   - Чекбокс on, spinbox threshold (1–50)
   - Torque: UI есть, но **disabled** при `TorqueSupport=false` (3S) — в cfg не пишется
   - Refresh читает `SmartShift.GetConfig` → `yyy mode threshold torque` (на 3S: `2 30 0`, mode≠0 ⇒ on)

2. **Жесты CID `0xc3`**
   - Направления Up / Down / Left / Right / Tap(`None`)
   - Пресеты: None, Meta+стрелки, Meta tap, **CycleDPI**, ToggleSmartShift
   - Persist только через **cfg + restart** (как remap)

3. **Helper**
   - `get-smartshift` / `set-smartshift` (live; Set* часто `Device timed out`, но readback OK)
   - `status` включает `smartshift` + `smartshift_torque_support`
   - `apply-cfg`: soft USB wake Bolt, если device не появился

4. **CfgWriter**
   - `CycleDPI` с `dpis: […]` внутри Gestures

---

## Smoke (железо)

| Проверка | Результат |
|----------|-----------|
| `get-smartshift` | OK `threshold: 30`, `TorqueSupport: false` |
| `set-smartshift --threshold 33` | OK (readback 33; warning timeout на SetThreshold) |
| `apply-cfg` с Gestures + threshold 30 | OK → `/etc/logid.cfg`; после wake GetConfig `yyy 2 30 0` |
| DPI после apply | 1000 |
| Remap Forward/Back | сохранены в том же cfg |
| Live `Button.SetAction` | по-прежнему не используем для жестов |

Скриншот: `media/smartshift-gestures/main-window.png`  
(копия: `media/mvp-slice/smartshift-gestures.png`)

---

## Запуск

Абсолютный путь scaffold:

`/run/user/1000/cursor_agent_stores/bc-84f7f75d-7458-47cf-ad36-c6841e5ec89b/files/scaffold`

```bash
bash /run/user/1000/cursor_agent_stores/bc-84f7f75d-7458-47cf-ad36-c6841e5ec89b/files/scaffold/scripts/install-helper.sh
/run/user/1000/cursor_agent_stores/bc-84f7f75d-7458-47cf-ad36-c6841e5ec89b/files/scaffold/run.sh
```

```bash
pkexec /usr/local/libexec/mxmaster-cfg-helper get-smartshift
pkexec /usr/local/libexec/mxmaster-cfg-helper set-smartshift --threshold 30
```

---

## Bugfix: toggle SmartShift только «в одну сторону»

**Симптом:** галочка on/off в GUI вела себя односторонне после Refresh.

**Корень:** `SmartShift.GetConfig` в logiops 0.3.x возвращает **tri-state конфиг**, не «сырой» HID++:

| mode (1-й `y`) | значение |
|----------------|----------|
| 0 | `on` unset (SetActive clear=true) |
| 1 | `on: false` |
| 2 | `on: true` |

Источник: `PixlOne/logiops` `SmartShift::IPC::getConfig()` —
`on.has_value() ? (on ? 2 : 1) : 0`.

Мы ошибочно мапили `on = (mode != 0)`, поэтому **mode 1 (выкл)** показывался как **вкл**. После Apply off Refresh снова ставил галочку — казалось, что выключение «не держится».

`SetActive(active, clear)`: второй аргумент **clear** — при `true` сбрасывает `on` (mode 0), а не выключает. Для on/off всегда `clear=false`.

**Фикс:** helper `on`/`on_state` по mode 1/2; GUI checkbox только при mode==2; match set-smartshift: off→mode1, on→mode2. Проверено cfg+live в обе стороны.

---

## Gaps

- End-to-end проверка жестов пальцем (Meta+Up и т.д.) — не автоматизировалась; cfg принят logid.
- Torque UI на устройствах с `TorqueSupport=true` не гоняли (нет такого стенда).
- BT по-прежнему вне smoke.
- Hi-res scroll UI — см. [`hires-scroll-notes.md`](./hires-scroll-notes.md) (LMMS-9).
