# Hi-res scroll UI — заметки (LMMS-9)

**Стенд:** Kubuntu · logiops **0.3.5** · MX Master 3S Bolt  
**Дата:** 2026-11-23  
**Код:** `/home/stepan/projects/mxmaster-cfg`

Связано: [`smartshift-gestures-notes.md`](./smartshift-gestures-notes.md),
[`spike-findings.md`](./spike-findings.md), [`mvp-slice-notes.md`](./mvp-slice-notes.md).

---

## Что добавлено

1. **GUI — блок «Hi-res scroll (HiresScroll / 0x2121)»**
   - Чекбоксы: **hires**, **invert**, **target / divert**
   - Refresh читает `HiresScroll.GetConfig` → `bbb hires invert target`
   - Apply пишет блок в `/etc/logid.cfg` через существующий `CfgWriter`

2. **Helper**
   - `get-hiresscroll` / `set-hiresscroll --hires|--invert|--target`
   - `status` включает `hiresscroll` на каждом device

3. **Privileged wrapper**
   - `get_hiresscroll()` / `set_hiresscroll()` в `adapter/privileged.py`

4. **CfgWriter** (уже был)
   - `hiresscroll: { hires; invert; target; }` — без отдельного `divert`

---

## logiops 0.3.5 API (проверено introspect)

| Метод | Сигнатура | Смысл |
|-------|-----------|--------|
| `GetConfig` | → `bbb` | hires, invert, target |
| `SetHires` | `b` | hi-res on/off |
| `SetInvert` | `b` | invert |
| `SetTarget` | `b` | divert колеса в logiops |
| `SetUp` / `SetDown` | `s` | жесты divert (не в GUI MVP) |

Свойств D-Bus нет — только методы.  
В cfg **нет** поля `divert`: HID++ `Mode::Target` = libconfig `target`.

Источник: PixlOne/logiops `HiresScroll::IPC` (v0.3.5).  
`getConfig` при unset отдаёт дефолты `{true, false, false}` (не tri-state как SmartShift).

---

## Smoke (железо, Bolt)

| Проверка | Результат |
|----------|-----------|
| `status` → `hiresscroll` | OK `hires=true invert=false target=false` |
| `get-hiresscroll` | OK `bbb true false false` |
| `set-hiresscroll --hires false` | OK readback false (warning: Device timed out на Set*) |
| `set-hiresscroll --hires true` | OK readback true |
| `set-hiresscroll --invert true` затем false | OK обе стороны |
| `apply-cfg` с `hires:false invert:true target:false` | OK → cfg; GetConfig `bbb false true false`; DPI=1000; SmartShift threshold=30 |
| restore `hires:true invert:false` | OK после soft USB wake Bolt (`device_count` снова 1) |
| DPI / SmartShift / remap / gestures | не сломаны (тот же apply path) |

Скриншот: `media/hires-scroll/main-window.png`  
(зеркало в Project store: `media/hires-scroll/main-window.png`)

---

## Запуск

```bash
cd /home/stepan/projects/mxmaster-cfg
bash scripts/install-helper.sh   # обновить helper
./run.sh
```

```bash
pkexec /usr/local/libexec/mxmaster-cfg-helper get-hiresscroll
pkexec /usr/local/libexec/mxmaster-cfg-helper set-hiresscroll --hires true --invert false --target false
```

Если `device_count: 0` — **пошевелите MX Master 3S** (Bolt Easy-Switch) и снова Refresh.

---

## Gaps

- GUI не редактирует `SetUp` / `SetDown` (жесты divert при `target:true`).
- End-to-end «ощущение» hi-res глазом/пальцем — субъективно; проверка через GetConfig + cfg.
- BT не тестировали.
- Live Set* на Bolt часто `Device timed out` — как у SmartShift; readback авторитетен; persist через apply-cfg.
