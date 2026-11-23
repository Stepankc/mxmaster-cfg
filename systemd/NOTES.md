# systemd: system vs user (заметки для MVP)

## Что уже даёт logiops

Пакет **logiops** обычно ставит:

- бинарь `logid`;
- **system** unit `logid.service` (или аналогичное имя — проверить `systemctl cat logid`);
- D-Bus policy для system bus (`pizza.pixl.LogiOps`);
- конфиг по умолчанию `/etc/logid.cfg`.

Наш GUI — **user** процесс (сессия KDE). Он:

1. пишет профиль в `~/.config/<project>/` (имя TBD);
2. либо генерирует `/etc/logid.cfg` через pkexec/polkit и дергает reload;
3. либо вызывает D-Bus методы `logid` на **system** bus (нужны права policy).

## System unit (ожидаемый паттерн)

```bash
systemctl status logid
sudo systemctl enable --now logid
sudo systemctl restart logid
journalctl -u logid -b --no-pager
```

Для отладки без unit:

```bash
sudo logid -v -c /tmp/logid.cfg
```

## User unit — когда нужен нам

Свой user-agent **не обязателен** в MVP, пока `logid` system daemon покрывает divert/жесты.
User unit имел бы смысл для:

- нашего будущего тонкого helper’а (уведомления, conflict check при логине);
- сценария `USE_USER_BUS` (редко; сверять build flags logiops).

Эскиз (не ставить, пока не понадобится):

```ini
# ~/.config/systemd/user/mxmaster-cfg-helper.service
[Unit]
Description=MX Master cfg helper (scaffold)
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/mxmaster-cfg --helper
Restart=on-failure

[Install]
WantedBy=default.target
```

## Права D-Bus

System bus + root-owned service → клиент из user session получает AccessDenied
(spike подтвердил: stock `pizza.pixl.LogiOps.conf` — только `user="root"`).

MVP путь: **не** ослаблять D-Bus policy пакета; GUI → `pkexec`
`/usr/local/libexec/mxmaster-cfg-helper` (polkit `org.mxmaster.cfg.helper`) →
`busctl` / запись `/etc/logid.cfg` + `systemctl restart logid`.

## Конфликт сервисов

Не запускать параллельно с:

- `solaar` (пользовательский);
- `openlogi-agent.service` (user);
- `ratbagd` на том же устройстве (если piper активен).

Проверка: `systemctl --user status openlogi-agent`; `pgrep -a solaar`.
