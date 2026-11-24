# SPDX-License-Identifier: GPL-3.0-or-later
"""Main window: device, DPI, SmartShift, HiRes, thumbwheel, remap, gestures."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from mxmaster_cfg.adapter.logiops_cfg import CfgWriter
from mxmaster_cfg.adapter.logiops_dbus import CID_BACK, CID_FORWARD, CID_GESTURE
from mxmaster_cfg.adapter.privileged import PrivilegedHelperError, apply_cfg_text, status

# Remap presets for forward/back.
REMAP_CHOICES: list[tuple[str, int, str]] = [
    ("Forward → KEY_FORWARD (штатно)", CID_FORWARD, "forward"),
    ("Forward → KEY_BACK", CID_FORWARD, "back"),
    ("Back → KEY_BACK (штатно)", CID_BACK, "back"),
    ("Back → KEY_FORWARD", CID_BACK, "forward"),
]

# Thumb wheel left/right gesture presets (need divert=true except "OS default").
# Each entry: (label, gesture_dict | None). None = omit side (OS handles scroll).
THUMB_SCROLL_PRESETS: list[tuple[str, dict[str, Any] | None]] = [
    ("ОС / не divert (omit)", None),
    (
        "Axis REL_HWHEEL_HI_RES",
        {
            "mode": "Axis",
            "axis": "REL_HWHEEL_HI_RES",
            "axis_multiplier": 1,
        },
    ),
    (
        "Axis REL_HWHEEL",
        {"mode": "Axis", "axis": "REL_HWHEEL", "axis_multiplier": 1},
    ),
    ("Отключить (NoPress)", {"mode": "NoPress"}),
    (
        "Громкость (OnInterval)",
        {
            "mode": "OnInterval",
            "interval": 2,
            "action": {"type": "Keypress", "keys": ["KEY_VOLUMEUP"]},
        },
    ),
]

# Opposite side volume key for the volume preset (left vs right).
_THUMB_VOL_KEYS = {
    "left": ["KEY_VOLUMEDOWN"],
    "right": ["KEY_VOLUMEUP"],
}

THUMB_TAP_PRESETS: list[tuple[str, dict[str, Any] | None]] = [
    ("Нет", None),
    ("None (явный)", {"type": "None"}),
    ("KEY_MUTE", {"type": "Keypress", "keys": ["KEY_MUTE"]}),
    ("KEY_PLAYPAUSE", {"type": "Keypress", "keys": ["KEY_PLAYPAUSE"]}),
    ("KEY_LEFTMETA", {"type": "Keypress", "keys": ["KEY_LEFTMETA"]}),
]

# Gesture direction action presets → profile action dict.
GESTURE_DIRS = ("Up", "Down", "Left", "Right", "None")  # None = tap
GESTURE_PRESETS: list[tuple[str, dict[str, Any]]] = [
    ("Нет (None)", {"type": "None"}),
    (
        "Keypress Meta+Up",
        {"type": "Keypress", "keys": ["KEY_LEFTMETA", "KEY_UP"]},
    ),
    (
        "Keypress Meta+Down",
        {"type": "Keypress", "keys": ["KEY_LEFTMETA", "KEY_DOWN"]},
    ),
    (
        "Keypress Meta+Left",
        {"type": "Keypress", "keys": ["KEY_LEFTMETA", "KEY_LEFT"]},
    ),
    (
        "Keypress Meta+Right",
        {"type": "Keypress", "keys": ["KEY_LEFTMETA", "KEY_RIGHT"]},
    ),
    ("Keypress Meta (tap)", {"type": "Keypress", "keys": ["KEY_LEFTMETA"]}),
    (
        "CycleDPI 400…1600",
        {
            "type": "CycleDPI",
            "dpis": [400, 600, 800, 1000, 1200, 1400, 1600],
        },
    ),
    ("ToggleSmartShift", {"type": "ToggleSmartShift"}),
]

# Default gesture map for MX Master 3S gesture button.
_DEFAULT_GESTURE_IDX = {
    "Up": 1,  # Meta+Up
    "Down": 2,  # Meta+Down
    "Left": 6,  # CycleDPI (as in logiops example)
    "Right": 4,  # Meta+Right
    "None": 5,  # Meta tap
}

CYCLE_DPI_LIST = [400, 600, 800, 1000, 1200, 1400, 1600]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MX Master Config (Linux)")
        self.resize(720, 800)
        self._last_status: dict[str, Any] = {}

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.setCentralWidget(scroll)
        root = QWidget()
        scroll.setWidget(root)
        layout = QVBoxLayout(root)

        title = QLabel("MX Master Config (Linux)")
        font = title.font()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        layout.addWidget(
            QLabel(
                "DPI · SmartShift · HiRes · ThumbWheel · батарея · remap · "
                "жесты → polkit-helper → logid 0.3.5 (Bolt)."
            )
        )

        # --- Device status ---
        status_box = QGroupBox("Устройство")
        status_form = QFormLayout(status_box)
        self.lbl_name = QLabel("—")
        self.lbl_path = QLabel("—")
        self.lbl_pid = QLabel("—")
        self.lbl_battery = QLabel("—")
        self.lbl_battery.setWordWrap(True)
        self.lbl_quirk = QLabel("")
        self.lbl_quirk.setWordWrap(True)
        self.lbl_quirk.setStyleSheet("color: #a15c00;")
        status_form.addRow("Имя:", self.lbl_name)
        status_form.addRow("D-Bus:", self.lbl_path)
        status_form.addRow("ProductID:", self.lbl_pid)
        status_form.addRow("Батарея:", self.lbl_battery)
        status_form.addRow("Статус:", self.lbl_quirk)
        layout.addWidget(status_box)

        # --- DPI ---
        dpi_box = QGroupBox("DPI")
        dpi_form = QFormLayout(dpi_box)
        self.spin_dpi = QSpinBox()
        self.spin_dpi.setRange(200, 8000)
        self.spin_dpi.setSingleStep(50)
        self.spin_dpi.setValue(1000)
        dpi_form.addRow("Целевой DPI:", self.spin_dpi)
        layout.addWidget(dpi_box)

        # --- SmartShift ---
        ss_box = QGroupBox("SmartShift / MagSpeed")
        ss_form = QFormLayout(ss_box)
        self.chk_ss_on = QCheckBox("Включён (SmartShift on)")
        self.chk_ss_on.setChecked(True)
        self.chk_ss_on.setToolTip(
            "logiops GetConfig: mode 2=on, 1=off, 0=unset. "
            "Снятие галочки пишет on:false (не clear)."
        )
        self.lbl_ss_state = QLabel("состояние: —")
        self.lbl_ss_state.setStyleSheet("color: #555;")
        self.spin_ss_threshold = QSpinBox()
        self.spin_ss_threshold.setRange(1, 50)
        self.spin_ss_threshold.setValue(30)
        self.spin_ss_torque = QSpinBox()
        self.spin_ss_torque.setRange(0, 100)
        self.spin_ss_torque.setValue(50)
        self.spin_ss_torque.setEnabled(False)
        self.lbl_ss_torque_hint = QLabel(
            "TorqueSupport=false на MX Master 3S — крутящий момент в cfg не пишем."
        )
        self.lbl_ss_torque_hint.setWordWrap(True)
        ss_form.addRow(self.chk_ss_on)
        ss_form.addRow("D-Bus:", self.lbl_ss_state)
        ss_form.addRow("Threshold:", self.spin_ss_threshold)
        ss_form.addRow("Torque:", self.spin_ss_torque)
        ss_form.addRow(self.lbl_ss_torque_hint)
        layout.addWidget(ss_box)

        # --- HiRes Wheel (feature 0x2121) ---
        hr_box = QGroupBox("Hi-res scroll (HiresScroll / 0x2121)")
        hr_form = QFormLayout(hr_box)
        self.chk_hr_hires = QCheckBox("Hi-res (высокое разрешение колеса)")
        self.chk_hr_hires.setChecked(True)
        self.chk_hr_hires.setToolTip(
            "logiops hiresscroll.hires → HID++ HiRes mode. "
            "GetConfig: первый bool из bbb."
        )
        self.chk_hr_invert = QCheckBox("Invert (инверсия направления)")
        self.chk_hr_invert.setChecked(False)
        self.chk_hr_invert.setToolTip("logiops hiresscroll.invert")
        self.chk_hr_target = QCheckBox("Target / divert (колесо → logiops)")
        self.chk_hr_target.setChecked(False)
        self.chk_hr_target.setToolTip(
            "logiops hiresscroll.target = HID++ divert (Mode::Target). "
            "При true события колеса уходят в logiops (SetUp/SetDown); "
            "обычно оставляйте выкл. для обычного скролла."
        )
        self.lbl_hr_state = QLabel("D-Bus: —")
        self.lbl_hr_state.setStyleSheet("color: #555;")
        self.lbl_hr_hint = QLabel(
            "В cfg: hires / invert / target. Отдельного поля divert в logiops "
            "0.3.5 нет — target и есть divert."
        )
        self.lbl_hr_hint.setWordWrap(True)
        hr_form.addRow(self.chk_hr_hires)
        hr_form.addRow(self.chk_hr_invert)
        hr_form.addRow(self.chk_hr_target)
        hr_form.addRow(self.lbl_hr_state)
        hr_form.addRow(self.lbl_hr_hint)
        layout.addWidget(hr_box)

        # --- Thumb wheel (feature 0x2150) ---
        tw_box = QGroupBox("Thumb wheel (0x2150)")
        tw_form = QFormLayout(tw_box)
        self.chk_tw_divert = QCheckBox("Divert (колесо → logiops)")
        self.chk_tw_divert.setChecked(False)
        self.chk_tw_divert.setToolTip(
            "thumbwheel.divert — без divert left/right/tap/touch/proxy "
            "не работают; ОС получает горизонтальный скролл."
        )
        self.chk_tw_invert = QCheckBox("Invert (инверсия направления)")
        self.chk_tw_invert.setChecked(False)
        self.chk_tw_invert.setToolTip("thumbwheel.invert")
        self.combo_tw_scroll = QComboBox()
        for label, _g in THUMB_SCROLL_PRESETS:
            self.combo_tw_scroll.addItem(label)
        self.combo_tw_scroll.setCurrentIndex(0)
        self.combo_tw_scroll.setToolTip(
            "Пресет для left/right. Для Axis/NoPress/громкости нужен divert."
        )
        self.combo_tw_tap = QComboBox()
        for label, _a in THUMB_TAP_PRESETS:
            self.combo_tw_tap.addItem(label)
        self.combo_tw_tap.setCurrentIndex(0)
        self.combo_tw_tap.setToolTip(
            "thumbwheel.tap (одиночный тап). Haptic в схеме logiops 0.3.5 нет."
        )
        self.lbl_tw_state = QLabel("D-Bus: —")
        self.lbl_tw_state.setStyleSheet("color: #555;")
        self.lbl_tw_hint = QLabel(
            "GetConfig → bb (divert, invert). left/right/tap/touch/proxy — "
            "только cfg. Haptic не поддерживается схемой logiops 0.3.5."
        )
        self.lbl_tw_hint.setWordWrap(True)
        tw_form.addRow(self.chk_tw_divert)
        tw_form.addRow(self.chk_tw_invert)
        tw_form.addRow("Left/Right:", self.combo_tw_scroll)
        tw_form.addRow("Tap:", self.combo_tw_tap)
        tw_form.addRow(self.lbl_tw_state)
        tw_form.addRow(self.lbl_tw_hint)
        layout.addWidget(tw_box)

        # --- Remap ---
        remap_box = QGroupBox("Remap Forward/Back")
        remap_form = QFormLayout(remap_box)
        self.combo_remap = QComboBox()
        for label, _cid, _preset in REMAP_CHOICES:
            self.combo_remap.addItem(label)
        remap_form.addRow("Кнопка:", self.combo_remap)
        layout.addWidget(remap_box)

        # --- Gestures ---
        gest_box = QGroupBox("Жесты (кнопка Gesture, CID 0xc3)")
        gest_form = QFormLayout(gest_box)
        self.gesture_combos: dict[str, QComboBox] = {}
        labels = {
            "Up": "Вверх",
            "Down": "Вниз",
            "Left": "Влево",
            "Right": "Вправо",
            "None": "Tap (None)",
        }
        for direction in GESTURE_DIRS:
            combo = QComboBox()
            for preset_label, _action in GESTURE_PRESETS:
                combo.addItem(preset_label)
            combo.setCurrentIndex(_DEFAULT_GESTURE_IDX.get(direction, 0))
            self.gesture_combos[direction] = combo
            gest_form.addRow(f"{labels[direction]}:", combo)
        layout.addWidget(gest_box)

        # --- Actions ---
        buttons = QHBoxLayout()
        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.clicked.connect(self._on_refresh)
        buttons.addWidget(self.btn_refresh)

        self.btn_apply = QPushButton("Применить")
        self.btn_apply.setDefault(True)
        self.btn_apply.clicked.connect(self._on_apply)
        buttons.addWidget(self.btn_apply)

        self.btn_conflict = QPushButton("Конфликт HID++")
        self.btn_conflict.clicked.connect(self._on_check_conflict)
        buttons.addWidget(self.btn_conflict)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        hint = QLabel(
            "Применить пишет /etc/logid.cfg через pkexec и делает "
            "systemctl restart logid (при отсутствии device — soft USB wake Bolt). "
            "Пароль polkit спросит у Stepan."
        )
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(hint)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Готово — нажмите «Обновить» (pkexec)")

    def _build_profile(self) -> dict[str, Any]:
        label, cid, preset = REMAP_CHOICES[self.combo_remap.currentIndex()]
        _ = label
        dpi = int(self.spin_dpi.value())
        keys = ["KEY_FORWARD"] if preset == "forward" else ["KEY_BACK"]
        other_cid = CID_BACK if cid == CID_FORWARD else CID_FORWARD
        other_keys = ["KEY_BACK"] if other_cid == CID_BACK else ["KEY_FORWARD"]

        gestures: list[dict[str, Any]] = []
        for direction in GESTURE_DIRS:
            idx = self.gesture_combos[direction].currentIndex()
            action = dict(GESTURE_PRESETS[idx][1])
            # Deep-ish copy for nested lists
            if "keys" in action:
                action["keys"] = list(action["keys"])
            if "dpis" in action:
                action["dpis"] = list(action["dpis"])
            mode = "OnRelease"
            gestures.append(
                {
                    "direction": direction,
                    "mode": mode,
                    "action": action,
                }
            )

        smartshift: dict[str, Any] = {
            "on": self.chk_ss_on.isChecked(),
            "threshold": int(self.spin_ss_threshold.value()),
        }
        # Only emit torque when device reports support (or user enabled spin).
        if self.spin_ss_torque.isEnabled():
            smartshift["torque"] = int(self.spin_ss_torque.value())

        thumbwheel = self._build_thumbwheel()

        return {
            "device": {"name": "MX Master 3S"},
            "dpi": dpi,
            "smartshift": smartshift,
            "hiresscroll": {
                "hires": self.chk_hr_hires.isChecked(),
                "invert": self.chk_hr_invert.isChecked(),
                "target": self.chk_hr_target.isChecked(),
            },
            "thumbwheel": thumbwheel,
            "buttons": [
                {
                    "cid": CID_GESTURE,
                    "label": "gesture",
                    "action": {"type": "Gestures", "gestures": gestures},
                },
                {
                    "cid": cid,
                    "action": {"type": "Keypress", "keys": keys},
                },
                {
                    "cid": other_cid,
                    "action": {"type": "Keypress", "keys": other_keys},
                },
            ],
        }

    def _build_thumbwheel(self) -> dict[str, Any]:
        divert = self.chk_tw_divert.isChecked()
        invert = self.chk_tw_invert.isChecked()
        tw: dict[str, Any] = {"divert": divert, "invert": invert}

        scroll_idx = self.combo_tw_scroll.currentIndex()
        scroll_base = THUMB_SCROLL_PRESETS[scroll_idx][1]
        if divert and isinstance(scroll_base, dict):
            for side in ("left", "right"):
                gest = dict(scroll_base)
                # Volume preset: opposite keys per side.
                if gest.get("mode") == "OnInterval":
                    action = dict(gest.get("action") or {})
                    if action.get("type") == "Keypress":
                        action["keys"] = list(_THUMB_VOL_KEYS[side])
                        gest["action"] = action
                elif gest.get("mode") == "Axis":
                    # Mirror multiplier: left negative, right positive.
                    mult = int(gest.get("axis_multiplier", 1) or 1)
                    gest["axis_multiplier"] = -abs(mult) if side == "left" else abs(mult)
                tw[side] = gest

        tap_idx = self.combo_tw_tap.currentIndex()
        tap = THUMB_TAP_PRESETS[tap_idx][1]
        if divert and isinstance(tap, dict):
            action = dict(tap)
            if "keys" in action:
                action["keys"] = list(action["keys"])
            tw["tap"] = action
        return tw

    def _on_refresh(self) -> None:
        try:
            data = status()
        except PrivilegedHelperError as exc:
            self.lbl_quirk.setText(str(exc))
            self.statusBar().showMessage("Ошибка helper/pkexec")
            QMessageBox.warning(
                self,
                "Helper",
                f"{exc}\n\nУстановите helper:\n"
                "  scaffold/scripts/install-helper.sh",
            )
            return

        self._last_status = data
        devices = data.get("devices") or []
        if not devices:
            self.lbl_name.setText("(нет)")
            self.lbl_path.setText("—")
            self.lbl_pid.setText("—")
            self.lbl_battery.setText("—")
            quirk = data.get("quirk") or "Устройство не найдено."
            self.lbl_quirk.setText(str(quirk))
            self.statusBar().showMessage(
                "logid active=%s, devices=0 — пошевелите мышь (Bolt)"
                % data.get("logid_active")
            )
            return

        dev = devices[0]
        self.lbl_name.setText(str(dev.get("name") or "?"))
        self.lbl_path.setText(str(dev.get("path") or "?"))
        pid = dev.get("product_id")
        self.lbl_pid.setText(str(pid) if pid is not None else "—")
        self._apply_battery_label(dev)
        if dev.get("dpi") is not None:
            self.spin_dpi.setValue(int(dev["dpi"]))
            self.lbl_quirk.setText(data.get("quirk") or "OK")
        else:
            msg = dev.get("dpi_error") or data.get("quirk") or "DPI недоступен"
            self.lbl_quirk.setText(str(msg))

        ss = dev.get("smartshift")
        torque_support = bool(dev.get("smartshift_torque_support"))
        self.spin_ss_torque.setEnabled(torque_support)
        if torque_support:
            self.lbl_ss_torque_hint.setText("Torque поддерживается — значение уйдёт в cfg.")
        else:
            self.lbl_ss_torque_hint.setText(
                "TorqueSupport=false на этом устройстве — torque в cfg не пишем."
            )
        if isinstance(ss, dict):
            # GetConfig tri-state: 2=on, 1=off, 0=unset — never treat 1 as on.
            mode = int(ss.get("mode", 0) or 0)
            on_state = ss.get("on_state")
            if on_state is None:
                on_state = {2: "on", 1: "off"}.get(mode, "unset")
            self.lbl_ss_state.setText(
                "mode=%s (%s)" % (mode, on_state)
            )
            if mode == 2:
                self.chk_ss_on.setChecked(True)
            elif mode == 1:
                self.chk_ss_on.setChecked(False)
            # mode 0 (unset): leave checkbox as-is / default on for apply
            if ss.get("threshold") is not None:
                self.spin_ss_threshold.setValue(int(ss["threshold"]))
            if torque_support and ss.get("torque") is not None:
                self.spin_ss_torque.setValue(int(ss["torque"]))
        else:
            self.lbl_ss_state.setText("состояние: н/д")

        hs = dev.get("hiresscroll")
        if isinstance(hs, dict):
            hires = bool(hs.get("hires", True))
            invert = bool(hs.get("invert", False))
            target = bool(hs.get("target", False))
            self.chk_hr_hires.setChecked(hires)
            self.chk_hr_invert.setChecked(invert)
            self.chk_hr_target.setChecked(target)
            self.lbl_hr_state.setText(
                "bbb hires=%s invert=%s target=%s"
                % (hires, invert, target)
            )
        else:
            err = dev.get("hiresscroll_error") or "н/д"
            self.lbl_hr_state.setText("D-Bus: %s" % err)

        tw = dev.get("thumbwheel")
        if isinstance(tw, dict):
            divert = bool(tw.get("divert", False))
            invert_tw = bool(tw.get("invert", False))
            self.chk_tw_divert.setChecked(divert)
            self.chk_tw_invert.setChecked(invert_tw)
            self.lbl_tw_state.setText(
                "bb divert=%s invert=%s" % (divert, invert_tw)
            )
        else:
            err = dev.get("thumbwheel_error") or "н/д"
            self.lbl_tw_state.setText("D-Bus: %s" % err)

        self.statusBar().showMessage(
            "Устройств: %s · logid=%s · батарея=%s"
            % (
                data.get("device_count"),
                data.get("logid_active"),
                "ok" if dev.get("battery_available") else "н/д",
            )
        )

    def _apply_battery_label(self, dev: dict[str, Any]) -> None:
        bat = dev.get("battery")
        if isinstance(bat, dict) and bat.get("percent") is not None:
            pct = int(bat["percent"])
            status = str(bat.get("status") or "")
            charging = bat.get("charging")
            if status == "charging" or (charging is True and status != "full"):
                state = "зарядка"
            elif status == "almost_full":
                state = "почти полный (зарядка)"
            elif status == "full":
                state = "полный"
            elif status == "discharging" or charging is False:
                state = "разряд"
            else:
                state = status or "?"
            src = bat.get("source") or "?"
            # Shorten noisy hidraw paths for the status row.
            if src.startswith("hidpp:"):
                src = "HID++ 0x1004"
            elif src.startswith("upower:"):
                src = "UPower"
            elif src.startswith("sysfs:"):
                src = "sysfs"
            note = ""
            if bat.get("logid_stopped"):
                note = " · logid pause"
            self.lbl_battery.setText("%s%% (%s) · %s%s" % (pct, state, src, note))
            return
        err = dev.get("battery_error") or "н/д"
        # Keep the UI short; full reason is in helper JSON.
        err_s = str(err)
        if "hidraw probe failed" in err_s and "UPower" in err_s:
            self.lbl_battery.setText(
                "н/д — нет данных UPower/sysfs и HID++ 0x1004"
            )
        elif "no Battery interface" in err_s:
            self.lbl_battery.setText(
                "н/д — батарея недоступна (D-Bus/UPower/HID++)"
            )
        else:
            self.lbl_battery.setText("н/д — %s" % err)

    def _on_apply(self) -> None:
        profile = self._build_profile()
        cfg_text = CfgWriter(profile).render()
        try:
            result = apply_cfg_text(cfg_text)
        except PrivilegedHelperError as exc:
            QMessageBox.warning(self, "Применить", str(exc))
            self.statusBar().showMessage("Apply failed")
            return

        quirk = result.get("quirk")
        ss = profile["smartshift"]
        hr = profile["hiresscroll"]
        tw = profile.get("thumbwheel") or {}
        msg = (
            f"Записано {result.get('wrote')}\n"
            f"DPI: {profile['dpi']}\n"
            f"SmartShift: on={ss.get('on')} threshold={ss.get('threshold')}\n"
            f"HiRes: hires={hr.get('hires')} invert={hr.get('invert')} "
            f"target={hr.get('target')}\n"
            f"ThumbWheel: divert={tw.get('divert')} invert={tw.get('invert')}\n"
            f"Жесты: CID 0xc3 ({len(profile['buttons'][0]['action']['gestures'])} направлений)\n"
            f"devices: {result.get('devices') or []}\n"
            f"bolt_usb_wake: {result.get('bolt_usb_wake')}"
        )
        if quirk:
            msg += f"\n\n⚠ {quirk}"
        QMessageBox.information(self, "Применить", msg)
        self.statusBar().showMessage("Apply OK — обновляю статус…")
        self._on_refresh()

    def _on_check_conflict(self) -> None:
        import subprocess

        try:
            out = subprocess.check_output(["ps", "-eo", "comm="], text=True)
        except OSError as exc:
            QMessageBox.warning(self, "Конфликт", f"Не удалось проверить: {exc}")
            return

        rivals = sorted(
            {
                name.strip()
                for name in out.splitlines()
                if name.strip()
                in {"solaar", "openlogi", "openlogi-agent", "ratbagd"}
            }
        )
        if rivals:
            QMessageBox.warning(
                self,
                "Конфликт HID++",
                "Обнаружены возможные конкуренты:\n  - "
                + "\n  - ".join(rivals)
                + "\n\nОстановите их перед работой с logid.",
            )
        else:
            QMessageBox.information(
                self,
                "Конфликт HID++",
                "Solaar / OpenLogi / ratbagd не найдены в ps.",
            )
