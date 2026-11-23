# Установка

[English](install.md) · [Русский](install.ru.md)

## Зависимости

- **logiops ≥ 0.3** (демон `logid`) — в Ubuntu 26.04 apt: 0.3.5
- **policykit-1** (`pkexec`)
- **PySide6** QtWidgets / QtCore / QtGui (на Kubuntu лучше пакеты apt)
- Python **≥ 3.10**, PyYAML, jsonschema (см. `requirements.txt`)

```bash
sudo apt install -y \
  python3-pyside6.qtwidgets python3-pyside6.qtcore python3-pyside6.qtgui \
  python3-yaml logiops policykit-1
```

## Установка привилегированного helper

D-Bus logiops из коробки — **только root**. GUI не ходит на system bus
напрямую; вызывает `helper/mxmaster-cfg-helper` через polkit.

```bash
cd /path/to/mxmaster-cfg
bash scripts/install-helper.sh
```

Устанавливает:

- `/usr/local/libexec/mxmaster-cfg-helper`
- `/usr/share/polkit-1/actions/org.mxmaster.cfg.policy`

Action: `org.mxmaster.cfg.helper` (`auth_admin_keep` для активной сессии).

После обновления helper перезапустите скрипт.

## Опционально: editable install

```bash
python3 -m pip install --user -e .
# или: python3 -m venv .venv && source .venv/bin/activate && pip install -e .
mxmaster-cfg
```

На системном Python Kubuntu иногда нужен venv или
`--break-system-packages`. Надёжнее `./run.sh`.

## Проверка

```bash
systemctl status logid --no-pager
pkexec /usr/local/libexec/mxmaster-cfg-helper status
```
