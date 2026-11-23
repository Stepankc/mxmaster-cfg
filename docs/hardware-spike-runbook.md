# Hardware spike runbook — MX Master 3S на Kubuntu

**Для:** Stepan  
**Цель:** подтвердить Bolt-first + BT путь через **logiops** (`logid` ≥ 0.3): обнаружение, SmartShift, жесты, ремап, D-Bus IPC; зафиксировать конфликты с Solaar.  
**Результат:** заполнить [`spike-findings.md`](./spike-findings.md) и прислать вывод команд ниже.

Связанный скелет: `scaffold/` (CfgWriter + D-Bus probe).  
План: [`mx-master-3s-linux-plan.md`](./mx-master-3s-linux-plan.md) (**статус: утверждён**, 2026-11-23).

---

## 0. Подготовка стенда

```bash
hostnamectl
cat /etc/os-release
uname -a
echo "SESSION: $XDG_SESSION_TYPE"   # ожидание: wayland или x11
groups                              # plugdev / input полезны для hidraw/uinput
```

Опционально клон скелета на машину (если store синхронизирован иначе — скопируйте `scaffold/`).

---

## 1. Установка logiops

### 1.1 Из репозитория Ubuntu/Kubuntu (сначала)

```bash
apt-cache policy logiops
sudo apt update
sudo apt install -y logiops
logid --version || logid -h || true
dpkg -L logiops | head -50
systemctl cat logid || systemctl cat logid.service || true
```

**Нужна версия ≥ 0.3** (Bolt + IPC). Если пакет `< 0.3` или отсутствует — собрать из upstream:

```bash
sudo apt install -y build-essential cmake libevdev-dev libudev-dev libconfig++-dev \
  libglib2.0-dev pkg-config git
git clone --recursive https://github.com/PixlOne/logiops.git
cd logiops
git checkout v0.3.5   # или новее тег
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make -j"$(nproc)"
sudo make install
sudo systemctl daemon-reload
# unit/config paths: проверить, куда cmake положил logid.service и logid.cfg
```

Зафиксируйте в findings: **версия**, **источник** (apt / self-build), путь к cfg и unit.

---

## 2. Конфликт с Solaar / OpenLogi — до тестов

Один owner HID++ на устройство.

```bash
pgrep -a solaar || true
pgrep -a openlogi || true
systemctl --user status openlogi-agent.service 2>/dev/null || true
pgrep -a ratbagd || true
```

Остановить перед spike:

```bash
# Solaar GUI/tray
pkill -f solaar || true
# OpenLogi, если стоит
systemctl --user stop openlogi-agent.service 2>/dev/null || true
```

Позже (шаг 8) — специально включить Solaar снова и задокументировать конфликт.

---

## 3. Тест A — Logi Bolt (приоритет)

1. Выключить BT-канал мыши / отключить BT-pairing на время теста (Easy-Switch на канал Bolt).
2. Вставить Bolt-ресивер.

```bash
lsusb | grep -i 046d || true
# ожидаемые ориентиры: ресивер c548; мышь может не светиться отдельным USB id через Bolt

ls -l /dev/hidraw* 2>/dev/null
ls -l /dev/uinput 2>/dev/null

# verbose logid на переднем плане (если unit уже занял устройство — stop unit)
sudo systemctl stop logid 2>/dev/null || sudo systemctl stop logid.service 2>/dev/null || true
sudo logid -v
```

Ожидание в логе: что-то вроде `Device found: MX Master 3S` (или близкое имя).  
Если устройство видно только при движении курсора — известный Bolt quirk; попробуйте:

```bash
# временно в cfg (см. шаг 5) добавить в корень / device:
# io_timeout: 60000;
```

и Easy-Switch туда-обратно.

**В findings:** обнаружен ли 3S на Bolt? Нужен ли `io_timeout`? Стабильность после suspend/reconnect (кратко).

`Ctrl+C` после сбора лога.

---

## 4. Тест B — Bluetooth

1. Вынуть Bolt (или переключить Easy-Switch на BT).
2. Pair через KDE Bluetooth или `bluetoothctl`.

```bash
bluetoothctl devices
lsusb | grep -i 046d || true
# BT 3S часто как 046d:b034 через uhid/hidraw

sudo logid -v
```

**В findings:** BT надёжнее/хуже Bolt для detect и hi-res scroll?

---

## 5. Минимальный cfg: SmartShift + gesture + remap

Создайте `/tmp/logid-spike.cfg` (или сгенерируйте из скелета):

```bash
# если scaffold на машине:
chmod +x scaffold/scripts/render-example-cfg.sh
./scaffold/scripts/render-example-cfg.sh
# → /tmp/logid.cfg
```

Ручной минимум (подправьте `name:` под точное имя из `logid -v`):

```bash
sudo tee /tmp/logid-spike.cfg >/dev/null <<'EOF'
devices: (
  {
    name: "MX Master 3S";
    smartshift:
    {
      on: true;
      threshold: 30;
    };
    hiresscroll:
    {
      hires: true;
      invert: false;
      target: false;
    };
    dpi: 1000;
    buttons: (
      {
        cid: 0xc3;
        action =
        {
          type: "Gestures";
          gestures: (
            {
              direction: "Up";
              mode: "OnRelease";
              action =
              {
                type: "Keypress";
                keys: ["KEY_LEFTMETA", "KEY_UP"];
              };
            },
            {
              direction: "Down";
              mode: "OnRelease";
              action =
              {
                type: "Keypress";
                keys: ["KEY_LEFTMETA", "KEY_DOWN"];
              };
            },
            {
              direction: "Left";
              mode: "OnRelease";
              action =
              {
                type: "Keypress";
                keys: ["KEY_LEFTMETA", "KEY_LEFT"];
              };
            },
            {
              direction: "Right";
              mode: "OnRelease";
              action =
              {
                type: "Keypress";
                keys: ["KEY_LEFTMETA", "KEY_RIGHT"];
              };
            }
          );
        };
      },
      {
        cid: 0xc4;
        action =
        {
          type: "ToggleSmartShift";
        };
      },
      {
        cid: 0x56;
        action =
        {
          type: "Keypress";
          keys: ["KEY_FORWARD"];
        };
      },
      {
        cid: 0x53;
        action =
        {
          type: "Keypress";
          keys: ["KEY_BACK"];
        };
      }
    );
  }
);
EOF
```

Применить:

```bash
# бэкап system cfg, если есть
sudo cp -a /etc/logid.cfg /etc/logid.cfg.bak.$(date +%Y%m%d) 2>/dev/null || true
sudo cp /tmp/logid-spike.cfg /etc/logid.cfg
sudo systemctl restart logid || sudo systemctl restart logid.service
# или foreground:
# sudo logid -v -c /tmp/logid-spike.cfg
```

Проверки руками:

| Действие | Ожидание |
|----------|----------|
| Кнопка режима (CID `0xc4`) | переключение ratchet ↔ free-spin |
| Gesture hold + ↑↓←→ | Meta+стрелки (KWin) |
| Forward / Back | браузерные кнопки |
| Колесо | hi-res если feature/транспорт позволяют |

Повторите на **Bolt и BT**. Отметьте, что не сработало.

---

## 6. D-Bus probes (logiops ≥ 0.3)

```bash
busctl --system status pizza.pixl.LogiOps
busctl --system tree pizza.pixl.LogiOps
busctl --system introspect pizza.pixl.LogiOps /pizza/pixl/logiops

# DeviceManager / Configuration — имена методов draft; смотрите introspect:
busctl --system introspect pizza.pixl.LogiOps /pizza/pixl/logiops pizza.pixl.LogiOps.DeviceManager || true
busctl --system introspect pizza.pixl.LogiOps /pizza/pixl/logiops pizza.pixl.LogiOps.Configuration || true

# от обычного пользователя (важно для GUI):
busctl --system call pizza.pixl.LogiOps /pizza/pixl/logiops \
  pizza.pixl.LogiOps.DeviceManager enumerate 2>&1 || true
```

Со скриптом скелета:

```bash
chmod +x scaffold/scripts/probe-logiops-dbus.sh
./scaffold/scripts/probe-logiops-dbus.sh
```

**В findings:** доступен ли IPC от user? AccessDenied? Отличаются ли имена интерфейсов от wiki draft?

---

## 7. Solaar show (опционально, после остановки logid)

Для батареи / feature dump / PID — не держать вместе с `logid`.

```bash
sudo systemctl stop logid 2>/dev/null || true
sudo apt install -y solaar   # если ещё нет
solaar show
# сохраните вывод для 3S: features, battery, WPID
```

Потом снова остановите Solaar перед возвратом к logid.

---

## 8. Конфликт: Solaar + logid одновременно

```bash
sudo systemctl start logid
solaar &    # или из меню
# пошевелить мышь / жесты
sudo journalctl -u logid -b --no-pager | tail -80
sudo logid -v   # во втором терминале, если unit не удобен
```

**В findings:** оба ломаются? кто «побеждает»? достаточно ли GUI-предупреждения `pgrep solaar`?

---

## 9. udev / права (если «Device found» нет)

```bash
ls -l /dev/hidraw* /dev/uinput
id
# шаблон из скелета:
# sudo cp scaffold/udev/99-mx-master-hidraw.rules /etc/udev/rules.d/
# sudo udevadm control --reload-rules && sudo udevadm trigger
# переподключить мышь/ресивер; добавить пользователя в plugdev/input при необходимости
```

---

## 10. Что вставить обратно в проект

Заполните [`spike-findings.md`](./spike-findings.md) и приложите (paste / файлы):

1. `apt-cache policy logiops` + фактическая версия `logid`
2. Фрагмент `sudo logid -v` на **Bolt** и на **BT** (успех/fail)
3. Итог apply SmartShift / gesture / remap (таблица ок/не ок)
4. Вывод `busctl --system tree pizza.pixl.LogiOps` + был ли AccessDenied у user
5. Вывод `solaar show` (опционально)
6. Наблюдение конфликта Solaar↔logid
7. Решение-рекомендация: `Depends: logiops` из репо **или** self-build/форк (TBD)

Достаточно текста в findings + куски логов; полные journal не обязательны.
