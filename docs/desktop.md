# Desktop launcher

[English](desktop.md) · [Русский](desktop.ru.md)

## Packaged (`.deb`)

The package installs:

- `/usr/share/applications/mxmaster-cfg.desktop` — **Name:** MX Master Config
- `/usr/share/icons/hicolor/scalable/apps/mxmaster-cfg.svg`
- `/usr/bin/mxmaster-cfg` as `Exec=`

After install, open **MX Master Config** from the Application Menu
(KDE: Kickoff / KRunner).

## Local checkout (no `.deb`)

```bash
cd /path/to/mxmaster-cfg
bash scripts/install-helper.sh      # once — polkit helper
bash scripts/install-desktop.sh    # user .desktop → ./run.sh (absolute path)
```

This writes `~/.local/share/applications/mxmaster-cfg.desktop` with
`Exec=/absolute/path/to/run.sh` and installs the same icon under
`~/.local/share/icons/hicolor/scalable/apps/`.

Remove:

```bash
bash scripts/install-desktop.sh --remove
```

Window / app title: **MX Master Config** (project name `mxmaster-cfg`).
