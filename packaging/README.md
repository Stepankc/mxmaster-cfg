# Debian / Ubuntu packaging

Goal: a real `.deb` for Debian/Ubuntu (Kubuntu as the primary stand).

Sources live in [`debian/`](debian/) (symlinked from repo-root `debian` →
`packaging/debian`).

## Depends

From `debian/control`:

- `logiops (>= 0.3)` — tested with **0.3.5** from apt (Bolt + D-Bus)
- `python3-pyside6.qtwidgets` (+ qtcore/qtgui)
- `python3-yaml`, `python3-jsonschema`
- `policykit-1` (`pkexec`)

Helper + polkit policy are **required** (stock logiops D-Bus policy is root-only).
Packaged helper path: `/usr/libexec/mxmaster-cfg-helper`.

## Build

From the repository root:

```bash
# Build deps (once):
sudo apt install -y debhelper dh-python pybuild-plugin-pyproject \
  python3-setuptools python3-all python3-yaml python3-jsonschema \
  python3-pyside6.qtwidgets dpkg-dev

# Binary package:
./packaging/build-deb.sh
# equivalent:
#   ln -sfn packaging/debian debian   # already committed as symlink
#   dpkg-buildpackage -us -uc -b
```

Artifacts appear **one directory above** the repo (`../mxmaster-cfg_*.deb`),
as usual for `dpkg-buildpackage`.

```bash
sudo apt install ../mxmaster-cfg_*.deb
# or: sudo dpkg -i ../mxmaster-cfg_*.deb && sudo apt -f install
```

The package installs:

| Path | Role |
|------|------|
| `/usr/bin/mxmaster-cfg` | GUI entry point (setuptools script) |
| `/usr/libexec/mxmaster-cfg-helper` | polkit helper |
| `/usr/share/polkit-1/actions/org.mxmaster.cfg.policy` | polkit action |
| `/usr/share/applications/mxmaster-cfg.desktop` | desktop entry |
| `/usr/share/mxmaster-cfg/examples/` | example profiles |
| `/usr/lib/udev/rules.d/99-mx-master-hidraw.rules` | hidraw access |

Named user profiles remain under `~/.config/mxmaster-cfg/profiles/` (not packaged).

## Related tree paths

| Path | Purpose |
|------|---------|
| `../udev/99-mx-master-hidraw.rules` | hidraw + uinput |
| `../systemd/NOTES.md` | system `logid` vs user units |
| `../polkit/org.mxmaster.cfg.policy` | source policy (→ `/usr/libexec`) |
