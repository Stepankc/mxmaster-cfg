# MX Master Config (Linux)

[English](README.md) · [Русский](README.ru.md)

Linux GUI для мышей **Logitech MX Master** через **[logiops](https://github.com/PixlOne/logiops)** (`logid`):
DPI, SmartShift, hi-res scroll, thumb wheel, батарея (если logiops отдаёт),
remap кнопок и жесты (CID `0xc3`).

| | |
|---|---|
| **Лицензия** | GPL-3.0-or-later |
| **GUI** | Qt 6 / PySide6 (удобно для KDE / Kubuntu) |
| **Пакеты** | семейство Debian / Ubuntu (эскиз `.deb` в дереве) |
| **Транспорт** | Logi Bolt (приоритет) + Bluetooth |
| **Требования** | **logiops ≥ 0.3** (проверено на 0.3.5) |

> Отображаемое имя: **MX Master Config (Linux)** · репозиторий: `mxmaster-cfg`  
> Не официальный продукт Logitech.

![Главное окно](media/hires-scroll/main-window.png)

## Возможности

- Статус устройства через привилегированный helper (`pkexec` + polkit)
- **DPI** чтение/запись (live D-Bus + persist через cfg)
- **SmartShift** on/off + threshold (корректный **tri-state** `GetConfig` в logiops)
- **Hi-res scroll** (`HiresScroll` / `0x2121`): hires, invert, target/divert
- **Thumb wheel** (`ThumbWheel` / `0x2150`): divert, invert, пресеты left/right/tap
- **Батарея** (Unified Battery `0x1004`), если logiops отдаёт по D-Bus
  (на пакете 0.3.5 — н/д, GUI показывает причину)
- **Remap** Forward/Back и пресеты **жестов** (persist через `/etc/logid.cfg` + restart `logid`)
- Подсказка Bolt-quirk («пошевелите мышь»), если после restart устройств нет
- Проверка конфликта HID++ (Solaar / OpenLogi / ratbagd)

## Быстрый старт (Debian / Ubuntu / Kubuntu)

```bash
# 1) Зависимости
sudo apt install -y \
  python3-pyside6.qtwidgets python3-pyside6.qtcore python3-pyside6.qtgui \
  logiops policykit-1

# 2) Helper + polkit (один раз спросит пароль)
cd /path/to/mxmaster-cfg
bash scripts/install-helper.sh

# 3) logid должен быть запущен
systemctl status logid --no-pager

# 4) GUI (выставляет PYTHONPATH)
./run.sh
```

Ошибка `No module named mxmaster_cfg` — запуск без `PYTHONPATH=src`.
Используйте `./run.sh` или editable: `python3 -m pip install --user -e .`

Подробнее: [docs/install.ru.md](docs/install.ru.md) · [docs/run.ru.md](docs/run.ru.md)

### Smoke helper CLI

```bash
pkexec /usr/local/libexec/mxmaster-cfg-helper status
pkexec /usr/local/libexec/mxmaster-cfg-helper get-dpi
pkexec /usr/local/libexec/mxmaster-cfg-helper set-dpi --dpi 1200
pkexec /usr/local/libexec/mxmaster-cfg-helper get-smartshift
pkexec /usr/local/libexec/mxmaster-cfg-helper get-hiresscroll
pkexec /usr/local/libexec/mxmaster-cfg-helper get-thumbwheel
pkexec /usr/local/libexec/mxmaster-cfg-helper get-battery
```

**Применить** в GUI пишет `/etc/logid.cfg` (бэкап `*.bak.mxmaster`) и
перезапускает `logid`. Жесты и remap идут **только** через cfg+restart
(live `Button.SetAction` на 0.3.5 ненадёжен).

## Bolt / Bluetooth

- После `systemctl restart logid` на Bolt часто `device_count: 0`, пока не
  **пошевелите мышь** (канал Easy-Switch). Soft USB wake `046d:c548` помогает,
  но движение мыши всё равно может быть нужно.
- Bluetooth поддерживается logiops; основной smoke — **Logi Bolt**.
- Один owner HID++: не держите Solaar/OpenLogi параллельно.

## SmartShift tri-state (важно)

`SmartShift.GetConfig` в logiops: mode **2 = on**, **1 = off**, **0 = unset** —
не «любой nonzero = on». См. [docs/smartshift.ru.md](docs/smartshift.ru.md).

## Документация

| Тема | English | Русский |
|------|---------|---------|
| Установка helper | [docs/install.md](docs/install.md) | [docs/install.ru.md](docs/install.ru.md) |
| Запуск | [docs/run.md](docs/run.md) | [docs/run.ru.md](docs/run.ru.md) |
| SmartShift | [docs/smartshift.md](docs/smartshift.md) | [docs/smartshift.ru.md](docs/smartshift.ru.md) |
| Hi-res scroll | [docs/hires-scroll.md](docs/hires-scroll.md) | [docs/hires-scroll.ru.md](docs/hires-scroll.ru.md) |
| Thumb wheel | [docs/thumbwheel.md](docs/thumbwheel.md) | [docs/thumbwheel.ru.md](docs/thumbwheel.ru.md) |
| Батарея | [docs/battery.md](docs/battery.md) | [docs/battery.ru.md](docs/battery.ru.md) |
| Жесты | [docs/gestures.md](docs/gestures.md) | [docs/gestures.ru.md](docs/gestures.ru.md) |
| Contributing | [CONTRIBUTING.md](CONTRIBUTING.md) | [CONTRIBUTING.ru.md](CONTRIBUTING.ru.md) |

Инженерные заметки: `docs/*-notes.md`, план, spike, runbook.

## Структура

```
.
├── helper/mxmaster-cfg-helper
├── polkit/org.mxmaster.cfg.policy
├── src/mxmaster_cfg/
├── scripts/install-helper.sh
├── run.sh
├── examples/profiles/
├── packaging/debian/
└── docs/
```

## Упаковка

См. [packaging/README.md](packaging/README.md). Задумано: `logiops (>= 0.3)`,
`policykit-1`, пакеты PySide6.

## Лицензия

[GPL-3.0-or-later](LICENSE) — в линии с logiops.
