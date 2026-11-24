# Install

[English](install.md) · [Русский](install.ru.md)

## Dependencies

- **logiops ≥ 0.3** (`logid` daemon) — Ubuntu 26.04 apt ships 0.3.5
- **policykit-1** (`pkexec`)
- **PySide6** QtWidgets / QtCore / QtGui (system apt packages recommended on Kubuntu)
- Python **≥ 3.10**, PyYAML, jsonschema (see `requirements.txt`)

```bash
sudo apt install -y \
  python3-pyside6.qtwidgets python3-pyside6.qtcore python3-pyside6.qtgui \
  python3-yaml logiops policykit-1
```

## Install the privileged helper

Stock logiops D-Bus is **root-only**. The GUI never talks to the system bus
directly; it launches `helper/mxmaster-cfg-helper` through polkit (`pkexec`).

```bash
cd /path/to/mxmaster-cfg
bash scripts/install-helper.sh
```

This installs:

- `/usr/libexec/mxmaster-cfg-helper`
- `/usr/share/polkit-1/actions/org.mxmaster.cfg.policy`
- `/usr/share/polkit-1/rules.d/10-mxmaster-cfg.rules`

### How authentication works

- Action id: `org.mxmaster.cfg.helper`.
- For an **active local** session user in group **`sudo`** or **`admin`**
  (typical Kubuntu desktop login), the rules file returns **YES** — no password
  dialog for status polls, Apply, or wake. Your graphical login already
  authenticated the session.
- Otherwise the policy falls back to `auth_admin` /
  `auth_admin_keep` (~5 minutes keep). That short keep is why the GUI used to
  re-ask every few minutes before the rules file existed.
- Remote / inactive / non-admin subjects still need an admin password.

Re-run the script after pulling helper or polkit changes. Polkit reloads rules
automatically; if a prompt still appears, log out/in once or reboot.

## Optional: editable Python install

```bash
python3 -m pip install --user -e .
# or: python3 -m venv .venv && source .venv/bin/activate && pip install -e .
mxmaster-cfg
```

On some Ubuntu/Kubuntu system Pythons you may need a venv or
`--break-system-packages`. Prefer `./run.sh` if unsure.

## Application Menu (local checkout)

```bash
bash scripts/install-desktop.sh
```

Installs a user `.desktop` that launches `./run.sh` by absolute path and the
`mxmaster-cfg` icon. See [desktop.md](desktop.md). The `.deb` already ships a
system desktop entry.

## Verify

```bash
systemctl status logid --no-pager
pkexec /usr/libexec/mxmaster-cfg-helper status
pkexec /usr/libexec/mxmaster-cfg-helper wake-receiver   # optional Bolt USB wake
```
