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
напрямую; вызывает `helper/mxmaster-cfg-helper` через polkit (`pkexec`).

```bash
cd /path/to/mxmaster-cfg
bash scripts/install-helper.sh
```

Устанавливает:

- `/usr/libexec/mxmaster-cfg-helper`
- `/usr/share/polkit-1/actions/org.mxmaster.cfg.policy`
- `/usr/share/polkit-1/rules.d/10-mxmaster-cfg.rules`

### Как работает аутентификация

- Action id: `org.mxmaster.cfg.helper`.
- Для **активной локальной** сессии пользователя из группы **`sudo`** или
  **`admin`** (обычный вход на Kubuntu) rules-файл возвращает **YES** — без
  диалога пароля на опрос статуса, Apply и wake. Графический логин уже
  аутентифицировал сессию.
- Иначе срабатывает fallback `auth_admin` / `auth_admin_keep` (~5 минут keep).
  Из‑за короткого keep GUI раньше снова спрашивал пароль каждые несколько
  минут, пока не было rules-файла.
- Удалённые / неактивные / не-admin субъекты по-прежнему требуют пароль admin.

После обновления helper или polkit перезапустите скрипт. Rules подхватываются
автоматически; если пароль всё ещё спрашивают — один раз выйдите/войдите или
перезагрузитесь.

## Опционально: editable install

```bash
python3 -m pip install --user -e .
# или: python3 -m venv .venv && source .venv/bin/activate && pip install -e .
mxmaster-cfg
```

На системном Python Kubuntu иногда нужен venv или
`--break-system-packages`. Надёжнее `./run.sh`.

## Меню приложений (локальный checkout)

```bash
bash scripts/install-desktop.sh
```

Ставит user `.desktop` с запуском `./run.sh` по абсолютному пути и иконку
`mxmaster-cfg`. См. [desktop.ru.md](desktop.ru.md). В `.deb` ярлык уже
системный.

## Проверка

```bash
systemctl status logid --no-pager
pkexec /usr/libexec/mxmaster-cfg-helper status
pkexec /usr/libexec/mxmaster-cfg-helper wake-receiver   # опционально soft wake Bolt
```
