# MX Master Linux-конфигуратор (имя TBD)

Приложение для настройки мышей **линейки Logitech MX Master** на Linux
через обёртку над **logiops** (`logid`): GUI (Qt 6 / PySide6) + адаптер
(запись cfg + D-Bus через привилегированный helper).

**Лицензия:** GPL-3.0-or-later  
**Платформа разработки:** Kubuntu (KDE)  
**Целевые пакеты:** Debian / Ubuntu (`.deb`)  
**Транспорт:** Logi Bolt (приоритет) + Bluetooth  
**MVP+:** без app-specific профилей · DPI + SmartShift + remap + жесты (CID 0xc3)

Связанные документы проекта (Agent Store):

- План: `docs/mx-master-3s-linux-plan.md`
- Spike: `docs/spike-findings.md` — **D-Bus logid root-only**
- MVP slice notes: `docs/mvp-slice-notes.md`
- SmartShift + gestures: `docs/smartshift-gestures-notes.md`
- Runbook: `docs/hardware-spike-runbook.md`

## Почему PySide6 + polkit helper

| Факт (spike 0.3.5) | Следствие для GUI |
|--------------------|-------------------|
| `pizza.pixl.LogiOps` system bus, policy `user="root"` only | User session **не** вызывает D-Bus напрямую |
| `/dev/hidraw*` 600 root | Daemon `logid` остаётся владельцем HID++ |
| Bolt: после `restart` устройство может не появиться без движения мыши | UI показывает quirk / «пошевелите мышь» |

Helper (`helper/mxmaster-cfg-helper`) запускается через **pkexec** + polkit
action `org.mxmaster.cfg.helper` (`auth_admin_keep` для активной сессии).

## Структура

```
scaffold/
├── LICENSE
├── README.md
├── pyproject.toml
├── requirements.txt
├── helper/mxmaster-cfg-helper   # root CLI → busctl / cfg+restart
├── polkit/org.mxmaster.cfg.policy
├── src/mxmaster_cfg/
│   ├── __main__.py
│   ├── gui/                     # PySide6 MVP
│   ├── adapter/                 # cfg writer + D-Bus + privileged
│   └── schema/
├── examples/profiles/
├── packaging/debian/
├── udev/
├── systemd/
├── run.sh                       # one-click launcher (sets PYTHONPATH)
├── scripts/install-helper.sh
└── tests/
```

## Путь на стенде Stepan (Kubuntu)

Абсолютный путь к дереву scaffold на этой машине:

```
/run/user/1000/cursor_agent_stores/bc-84f7f75d-7458-47cf-ad36-c6841e5ec89b/files/scaffold
```

(То же содержимое в Cursor Agent Store: `/cursor/stores/bc-84f7f75d-7458-47cf-ad36-c6841e5ec89b/scaffold`.)

## Быстрый старт на Kubuntu (этот стенд)

```bash
# 1) зависимости GUI (apt; уже есть python3-yaml)
sudo apt install -y \
  python3-pyside6.qtwidgets python3-pyside6.qtcore python3-pyside6.qtgui \
  logiops

# 2) поставить helper + polkit (один раз; pkexec спросит пароль)
cd /run/user/1000/cursor_agent_stores/bc-84f7f75d-7458-47cf-ad36-c6841e5ec89b/files/scaffold
bash scripts/install-helper.sh

# 3) убедиться что logid жив
systemctl status logid --no-pager

# 4) GUI — one-click (рекомендуется; сам выставляет PYTHONPATH)
./run.sh

# эквивалент вручную:
# PYTHONPATH=src python3 -m mxmaster_cfg
```

Если видите `No module named mxmaster_cfg` — запускали без `PYTHONPATH=src`
или не из каталога `scaffold`. Используйте `./run.sh` по абсолютному пути выше.

### Опционально: editable install

Чтобы `python3 -m mxmaster_cfg` работал из любого cwd без `PYTHONPATH`:

```bash
cd /run/user/1000/cursor_agent_stores/bc-84f7f75d-7458-47cf-ad36-c6841e5ec89b/files/scaffold
python3 -m pip install --user -e .
# или: python3 -m venv .venv && source .venv/bin/activate && pip install -e .
mxmaster-cfg   # console_script из pyproject.toml
```

На системном Python Kubuntu иногда нужен `pip install --break-system-packages -e .`
или venv — предпочтительнее venv / просто `./run.sh`.

В окне: **Обновить** → pkexec → статус устройства / DPI / SmartShift.  
**Применить** → пишет `/etc/logid.cfg` (бэкап `*.bak.mxmaster`) + `systemctl restart logid`
(+ soft USB wake Bolt, если device ещё не в D-Bus).

Проверка helper без GUI:

```bash
pkexec /usr/local/libexec/mxmaster-cfg-helper status
pkexec /usr/local/libexec/mxmaster-cfg-helper get-smartshift
pkexec /usr/local/libexec/mxmaster-cfg-helper set-smartshift --threshold 30
pkexec /usr/local/libexec/mxmaster-cfg-helper set-dpi --dpi 1200
```

Жесты и remap в GUI уходят **только** через `apply-cfg` (live `SetAction` на 0.3.5
ненадёжен). На MX Master 3S `TorqueSupport=false` — torque в cfg не пишется.

SmartShift `GetConfig` (logiops): mode **2=on, 1=off, 0=unset** — не путать с
«любой nonzero = on». `SetActive(active, clear)`: `clear=true` сбрасывает `on`,
а не выключает.

Dry-run cfg:

```bash
PYTHONPATH=src python3 -m mxmaster_cfg.adapter.logiops_cfg \
  --profile examples/profiles/mx-master-3s-default.yaml \
  --out /tmp/logid.cfg
```

### Bolt quirk

Если после restart в `status` `device_count: 0` — **пошевелите MX Master 3S**
(канал Easy-Switch на Bolt) и снова **Обновить**. Soft USB reset ресивера
`046d:c548` тоже поднимает device, но без движения мыши logid может молчать.

## Архитектура адаптера

1. **Профиль** (YAML/JSON) → schema в `schema/`.
2. **CfgWriter** → libconfig `/etc/logid.cfg`.
3. **Privileged helper** (pkexec): `status` / `get-dpi` / `set-dpi` /
   `set-button-action` / `apply-cfg`.
4. **LogiOpsDBusClient** — прямой busctl (для root/spike); GUI его не зовёт
   без прав.

D-Bus (0.3.5): service `pizza.pixl.LogiOps`, devices
`/pizza/pixl/logiops/devices/N`, интерфейсы `Device`, `DPI`, `SmartShift`,
`HiresScroll`, `Buttons`/`Button`, `Config`, `Receivers`.

## Упаковка

См. `packaging/debian/` и `packaging/README.md`.

В `.deb` нужно класть:

- `helper/mxmaster-cfg-helper` → `/usr/local/libexec/` или `/usr/libexec/`
- `polkit/org.mxmaster.cfg.policy` → `/usr/share/polkit-1/actions/`
- Python package + desktop entry (TBD)

`Depends: logiops (>= 0.3)` — на Ubuntu 26.04 apt `0.3.5` достаточен.

## Конфликт с Solaar / OpenLogi

Один owner HID++. Кнопка «Конфликт HID++» в GUI ищет процессы
`solaar` / `openlogi` / `ratbagd`.
