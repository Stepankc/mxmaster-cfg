# MVP GUI vertical slice — заметки (LMMS-5)

**Стенд:** Kubuntu / Ubuntu 26.04 · host `stepan-ms7c56` · Wayland · logiops **0.3.5**  
**Мышь:** MX Master 3S · Logi Bolt (`046d:c548`) · ProductID D-Bus `45108`  
**Дата:** 2026-11-23  
**Код:** `scaffold/` в Agent Store (расширен in-place)

---

## Что сделано

1. **Polkit + helper**
   - `scaffold/helper/mxmaster-cfg-helper` → установлен в `/usr/local/libexec/mxmaster-cfg-helper`
   - `scaffold/polkit/org.mxmaster.cfg.policy` → `/usr/share/polkit-1/actions/`
   - Action `org.mxmaster.cfg.helper`, `auth_admin_keep` для активной сессии, `allow_gui`
   - Установка: `scaffold/scripts/install-helper.sh` (через pkexec)

2. **PySide6 GUI** (`python3 -m mxmaster_cfg`)
   - Показ устройства (имя, D-Bus path, ProductID)
   - DPI spinbox + **Применить** / **Обновить**
   - Один remap (Forward/Back ↔ KEY_FORWARD/KEY_BACK)
   - Статус Bolt-quirk в UI («пошевелите мышь»)
   - Кнопка конфликта HID++ (Solaar/OpenLogi/ratbagd)

3. **Адаптеры**
   - `adapter/privileged.py` — GUI → pkexec → helper
   - `adapter/logiops_dbus.py` — реальные пути `…/devices/N`, GetDPI/SetDPI
   - `adapter/logiops_cfg.py` — запись профиля → libconfig (без изменений API)

4. **Документация**
   - `scaffold/README.md` — как запускать на Kubuntu
   - packaging/systemd notes обновлены под root-only D-Bus

5. **Скриншот**
   - `media/mvp-slice/main-window.png` — устройство найдено, DPI 1000, status OK

---

## Smoke-test (реальная мышь)

| Шаг | Результат |
|-----|-----------|
| `pkexec … helper status` | OK; quirk-текст когда devices=0 |
| `apply-cfg` → `/etc/logid.cfg` + restart | OK; backup `*.bak.mxmaster` |
| После soft USB reset `authorized` 0→1 | Device появляется; DPI читается |
| `set-dpi --dpi 1400` + readback | **OK** (`1400`) |
| `get-dpi` | **OK** |
| `set-button-action` (live D-Bus `Button.SetAction`) | **FAIL** — формат строки action не принят logid; remap в MVP идёт через **cfg+restart** |
| GUI Refresh / Apply (pkexec) | OK (пароль polkit у Stepan / keep) |
| Конфликт Solaar | не установлен — GUI сообщает «не найдены» |

---

## Как запустить снова

Абсолютный путь scaffold на стенде Stepan:

`/run/user/1000/cursor_agent_stores/bc-84f7f75d-7458-47cf-ad36-c6841e5ec89b/files/scaffold`

```bash
# один раз
sudo apt install -y python3-pyside6.qtwidgets python3-pyside6.qtcore python3-pyside6.qtgui
bash /run/user/1000/cursor_agent_stores/bc-84f7f75d-7458-47cf-ad36-c6841e5ec89b/files/scaffold/scripts/install-helper.sh

# GUI (one-click — выставляет PYTHONPATH)
/run/user/1000/cursor_agent_stores/bc-84f7f75d-7458-47cf-ad36-c6841e5ec89b/files/scaffold/run.sh
```

Ошибка `No module named mxmaster_cfg` = запуск без `PYTHONPATH` / не из `scaffold`.
Опционально: `cd …/scaffold && pip install --user -e .` (см. README).

Helper CLI:

```bash
pkexec /usr/local/libexec/mxmaster-cfg-helper status
pkexec /usr/local/libexec/mxmaster-cfg-helper set-dpi --dpi 1200
```

---

## Оставшиеся пробелы

- **SmartShift + gestures UI** — сделано в LMMS-7, см. [`smartshift-gestures-notes.md`](./smartshift-gestures-notes.md).
- **HiresScroll UI** — сделано (LMMS-9); см. [`hires-scroll-notes.md`](./hires-scroll-notes.md).
- **Bluetooth** — не тестировали (мышь не спарена; Easy-Switch → BT нужен follow-up).
- **Live `Button.SetAction`** — формат D-Bus строки не подтверждён; persist-remap/gestures = cfg writer.
- **DPI timeout** — иногда `Device timed out` сразу после reconnect; повтор GetDPI / движение мыши помогает.
- **Имя проекта / .deb** — TBD; packaging всё ещё эскиз.
- **Не ослабляли** stock `pizza.pixl.LogiOps.conf` (намеренно — только helper).

---

## Файлы (verify)

- `scaffold/helper/mxmaster-cfg-helper`
- `scaffold/polkit/org.mxmaster.cfg.policy`
- `scaffold/scripts/install-helper.sh`
- `scaffold/src/mxmaster_cfg/adapter/privileged.py`
- `scaffold/src/mxmaster_cfg/adapter/logiops_dbus.py`
- `scaffold/src/mxmaster_cfg/gui/main_window.py`
- `scaffold/README.md`
- `docs/mvp-slice-notes.md` (этот файл)
- `media/mvp-slice/main-window.png`
