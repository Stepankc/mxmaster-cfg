# SPDX-License-Identifier: GPL-3.0-or-later
"""Main window: device, DPI, SmartShift, remap, gesture button — Apply via helper."""

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
        self.setWindowTitle("MX Master — конфигуратор (MVP+)")
        self.resize(720, 720)
        self._last_status: dict[str, Any] = {}

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.setCentralWidget(scroll)
        root = QWidget()
        scroll.setWidget(root)
        layout = QVBoxLayout(root)

        title = QLabel("MX Master Linux (имя TBD)")
        font = title.font()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        layout.addWidget(
            QLabel(
                "DPI · SmartShift · remap · жесты (CID 0xc3) → polkit-helper → "
                "logid 0.3.5 (Bolt)."
            )
        )

        # --- Device status ---
        status_box = QGroupBox("Устройство")
        status_form = QFormLayout(status_box)
        self.lbl_name = QLabel("—")
        self.lbl_path = QLabel("—")
        self.lbl_pid = QLabel("—")
        self.lbl_quirk = QLabel("")
        self.lbl_quirk.setWordWrap(True)
        self.lbl_quirk.setStyleSheet("color: #a15c00;")
        status_form.addRow("Имя:", self.lbl_name)
        status_form.addRow("D-Bus:", self.lbl_path)
        status_form.addRow("ProductID:", self.lbl_pid)
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

        return {
            "device": {"name": "MX Master 3S"},
            "dpi": dpi,
            "smartshift": smartshift,
            "hiresscroll": {"hires": True, "invert": False, "target": False},
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
            quirk = data.get("quirk") or "Устройство не найдено."
            self.lbl_quirk.setText(str(quirk))
            self.statusBar().showMessage(
                "logid active=%s, devices=0" % data.get("logid_active")
            )
            return

        dev = devices[0]
        self.lbl_name.setText(str(dev.get("name") or "?"))
        self.lbl_path.setText(str(dev.get("path") or "?"))
        pid = dev.get("product_id")
        self.lbl_pid.setText(str(pid) if pid is not None else "—")
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

        self.statusBar().showMessage(
            "Устройств: %s · logid=%s"
            % (data.get("device_count"), data.get("logid_active"))
        )

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
        msg = (
            f"Записано {result.get('wrote')}\n"
            f"DPI: {profile['dpi']}\n"
            f"SmartShift: on={ss.get('on')} threshold={ss.get('threshold')}\n"
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
