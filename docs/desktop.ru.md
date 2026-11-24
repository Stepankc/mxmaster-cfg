# Ярлык в меню приложений

[English](desktop.md) · [Русский](desktop.ru.md)

## Пакет (`.deb`)

Пакет ставит:

- `/usr/share/applications/mxmaster-cfg.desktop` — **Name:** MX Master Config
- `/usr/share/icons/hicolor/scalable/apps/mxmaster-cfg.svg`
- `/usr/bin/mxmaster-cfg` в `Exec=`

После установки ищите **MX Master Config** в меню приложений
(KDE: Kickoff / KRunner).

## Локальный checkout (без `.deb`)

```bash
cd /path/to/mxmaster-cfg
bash scripts/install-helper.sh      # один раз — polkit helper
bash scripts/install-desktop.sh    # user .desktop → ./run.sh (абсолютный путь)
```

Пишет `~/.local/share/applications/mxmaster-cfg.desktop` с
`Exec=/абсолютный/путь/к/run.sh` и иконку в
`~/.local/share/icons/hicolor/scalable/apps/`.

Убрать:

```bash
bash scripts/install-desktop.sh --remove
```

Заголовок окна / приложения: **MX Master Config** (имя проекта `mxmaster-cfg`).
