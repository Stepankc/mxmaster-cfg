# Spike findings — logiops на MX Master 3S (Kubuntu)

**Заполнил:** agent bc-ecc9efe1 (Stepan self-hosted worker)  
**Дата:** 2026-11-23  
**Стенд:** Ubuntu 26.04.1 LTS (Resolute) / Kubuntu · kernel `7.0.0-43-generic` · **Wayland** · host `stepan-ms7c56`  
**Мышь:** MX Master 3S · прошивку не трогали  

Инструкции: [`hardware-spike-runbook.md`](./hardware-spike-runbook.md).  
Артефакты: `internal/spike-artifacts/` (`logid-verbose-spike.log`, `logid-device-introspect.txt`, `logid-dpi-smartshift-probe.txt`).

---

## 1. Версия и источник logiops

| Поле | Значение |
|------|----------|
| Источник | **apt** (`universe`) via `pkexec apt-get install -y logiops` |
| Версия `logid` | **v0.3.5** (`0.3.5-1build2`) |
| Путь unit | `/usr/lib/systemd/system/logid.service` (enabled → `graphical.target`) |
| Путь cfg по умолчанию | `/etc/logid.cfg` |
| ≥ 0.3 (Bolt + IPC)? | **да** |

```
# apt-cache policy logiops
logiops:
  Установлен: 0.3.5-1build2
  Кандидат:   0.3.5-1build2
  500 http://archive.ubuntu.com/ubuntu resolute/universe amd64 Packages

# logid --version
v0.3.5
```

Unit: `Type=simple`, `ExecStart=/usr/bin/logid`, `User=root`.  
После spike: unit **active/enabled**; `/etc/logid.cfg` **восстановлен** из бэкапа (закомментированный example).

Self-build **не нужен** для MVP на этом стенде — пакет Ubuntu 26.04 уже ≥0.3.

---

## 2. Bolt

| Проверка | Результат | Заметки |
|----------|-----------|---------|
| Ресивер в `lsusb` (ожид. `046d:c548`) | **OK** | `Bus 001 Device 004: ID 046d:c548 Logitech, Inc. Logi Bolt Receiver` |
| `Device found` в `logid -v` | **OK** | `Device found: MX Master 3S on /dev/hidraw4:2` |
| Нужен `io_timeout` / Easy-Switch | **частично** | Корневой `io_timeout: 60000;` → `SettingTypeException` в 0.3.5-apt. После `systemctl restart` устройство иногда **не** появляется, пока нет движения / soft USB reset (`authorized` 0→1 на `1-6`). |
| SmartShift apply | **OK** | cfg `threshold: 30` → D-Bus `GetConfig` = `yyy 2 30 0` |
| Gesture button | **CID видны** | remappable: `0x52, 0x53, 0x56, 0xc3, 0xc4, 0xd7` (+ thumb `0x2150`); gesture actions **не** гоняли end-to-end |
| Remap forward/back | **CID OK** | `0x56` / `0x53` remappable+gesture; remap apply не тестировали |
| Hi-res scroll | **OK (config)** | `GetConfig` → `bbb true false false` (= hires/invert/target из cfg) |
| После suspend/reconnect | **не тестировали** | Soft USB reset ресивера поднимает device за ~1–2 с |

```
# фрагмент sudo logid -v (Bolt)
[INFO] Detected receiver at /dev/hidraw4
[INFO] Device found: MX Master 3S on /dev/hidraw4:2
[DEBUG] /dev/hidraw4:2 remappable buttons: 0x52 0x53 0x56 0xc3 0xc4 0xd7
[DEBUG] Thumb wheel detected (0x2150)
```

**ProductID (D-Bus):** `45108` = `0xb034` (HID++ id 3S).

---

## 3. Bluetooth

| Проверка | Результат | Заметки |
|----------|-----------|---------|
| PID (ожид. `046d:b034`) | **нет** | В `bluetoothctl devices` только AirPods; MX Master **не спарен** |
| `Device found` в `logid -v` | **не тестировали** | Нет BT-канала на стенде |
| SmartShift / gestures / remap / hi-res | — | Блокер: нужен pairing / Easy-Switch на BT |

```
# bluetoothctl devices
Device F0:04:E1:ED:2C:DA AirPods Pro - Find My
```

---

## 4. D-Bus IPC

| Проверка | Результат |
|----------|-----------|
| `busctl status pizza.pixl.LogiOps` | **OK** (сервис на system bus, PID logid) |
| `busctl tree` показывает device nodes | **OK как root**; как user — **Access denied** |
| Introspect совпадает с wiki draft? | Interfaces: `Device`, `DPI`, `SmartShift`, `HiresScroll`, `ThumbWheel`, `Buttons`, `Config`, `Receivers` — достаточно для MVP |
| User session может вызывать методы? | **Нет** — policy deny для non-root |
| AccessDenied / нужна polkit? | **Да** — stock `pizza.pixl.LogiOps.conf` разрешает send/receive **только `user="root"`** |
| Bus: system vs session (`USE_USER_BUS`) | **system** (пакетный unit) |

```
# busctl --system tree pizza.pixl.LogiOps   # as root
/pizza/pixl/logiops/devices/0
/pizza/pixl/logiops/receivers/0

# as user:
Failed to introspect ... Access denied
```

**Проверенные вызовы (root) после cfg dpi=1200 / smartshift threshold=30:**

| Метод | Результат |
|-------|-----------|
| `DPI.GetDPI(0)` | `q 1200` |
| `DPI.GetDPIs(0)` | `aqqb 2 200 8000 50 true` |
| `SmartShift.GetConfig` | `yyy 2 30 0` |
| `HiresScroll.GetConfig` | `bbb true false false` |
| `Device.Name` | `"MX Master 3S"` |

**Вывод для GUI v1:** либо polkit helper / ослабленная dbus policy для группы пользователя, либо apply через запись cfg + `systemctl restart` (с учётом Bolt re-detect quirk). Чистый user→D-Bus из коробки **не работает**.

---

## 5. Solaar (опционально) и конфликт

**`solaar show`:** не запускался — пакет **не установлен** (кандидат apt `1.1.19-1`). OpenLogi / ratbagd тоже отсутствуют.

**Конфликт с logid:**

| Сценарий | Поведение |
|----------|-----------|
| Только logid | Работает (этот spike) |
| Только Solaar | не проверяли |
| Оба сразу | не проверяли (Solaar не ставили; uninstall не актуален) |

Достаточно ли детекта по `pgrep` для GUI MVP? **Да как первый слой** (`pgrep -a solaar|openlogi|logid`); плюс предупреждение в UI. Реальный dual-open конфликт — отдельный мини-тест после явного OK на установку Solaar.

---

## 6. udev / права

| Вопрос | Ответ |
|--------|-------|
| Права на `/dev/hidraw*` | `crw------- root:root` (600) — logid root OK; user без daemon не откроет |
| `/dev/uinput` доступен? | `crw------- root:root` — для divert/жестов через root-logid ок; user-uinput нет |
| Нужны кастомные rules из `scaffold/udev/`? | Для daemon-path — **не обязательно**. Для user-bus / non-root экспериментов — да (`plugdev`/`input` + uinput) |
| Группы пользователя | `stepan` ∈ `plugdev`, `sudo`; **не** в `input` |

---

## 7. Выводы для MVP

- **Bolt как primary:** **работает** (detect + DPI/SmartShift/HiRes apply). Flaky re-detect после restart без движения мыши / без USB soft-reset — заложить reconnect UX / retry.
- **BT как обязательный fallback:** **не проверен** на стенде (нет pairing). Нужен follow-up: Easy-Switch → BT, повторить detect + те же D-Bus Get*.
- **Depends: logiops из репо** vs **self-build/форк:** **apt 0.3.5 достаточен** на Ubuntu 26.04. Форк не блокер сейчас; `io_timeout` из wiki на этом пакете не принялся.
- **D-Bus apply** vs **только cfg+restart** для GUI v1: D-Bus API **зрелый для root** (`SetDPI` / `SetActive` / `SetThreshold` есть). Для user GUI — **нужен polkit или cfg+restart**. Рекомендация: v1 = cfg writer + restart + status via privileged helper; параллельно polkit rule.
- **Блокеры / сюрпризы:**
  1. D-Bus **root-only** (stock policy).
  2. BT путь не проверен (нет device в bluetoothctl).
  3. Bolt re-detect после restart без input/USB reset.
  4. `io_timeout` в корне cfg → `SettingTypeException` на 0.3.5-1build2.
  5. `sudo` без TTY — для агента пришлось `pkexec` (GUI polkit).

---

## 8. Артефакты

Список приложенных логов/файлов:

- `/run/user/1000/cursor_agent_stores/bc-84f7f75d-7458-47cf-ad36-c6841e5ec89b/files/internal/spike-artifacts/logid-verbose-spike.log`
- `/run/user/1000/cursor_agent_stores/bc-84f7f75d-7458-47cf-ad36-c6841e5ec89b/files/internal/spike-artifacts/logid-device-introspect.txt`
- `/run/user/1000/cursor_agent_stores/bc-84f7f75d-7458-47cf-ad36-c6841e5ec89b/files/internal/spike-artifacts/logid-dpi-smartshift-probe.txt`
- Бэкап cfg: `/etc/logid.cfg.bak.spike.20261123120001` (system; оригинал восстановлен в `/etc/logid.cfg`)
