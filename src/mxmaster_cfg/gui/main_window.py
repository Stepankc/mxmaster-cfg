# SPDX-License-Identifier: GPL-3.0-or-later
"""Main window: device, DPI, SmartShift, HiRes, thumbwheel, remap, gestures."""

from __future__ import annotations

import threading
from queue import Empty, SimpleQueue
from typing import Any, Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from mxmaster_cfg.adapter.logiops_cfg import CfgWriter
from mxmaster_cfg.adapter.logiops_dbus import CID_BACK, CID_FORWARD, CID_GESTURE
from mxmaster_cfg.adapter.privileged import (
    PrivilegedHelperError,
    apply_cfg_text,
    get_battery,
    status,
    wake_receiver,
)
from mxmaster_cfg.profiles import (
    ProfileError,
    delete_named_profile,
    list_profiles,
    load_named_profile,
    profiles_dir,
    save_named_profile,
)

# Battery auto-refresh interval (non-blocking; coexist-only HID++ probe).
BATTERY_REFRESH_MS = 45_000
# After apply-cfg with device_count=0, poll until Bolt reappears.
RECONNECT_POLL_MS = 2_000
RECONNECT_MAX_POLLS = 30  # ~60 s
# Drain worker results on the GUI thread (never touch QWidgets from workers).
_ASYNC_PUMP_MS = 50

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


def _norm_cid(cid: Any) -> int | None:
    if isinstance(cid, int):
        return cid
    if isinstance(cid, str):
        text = cid.strip().lower()
        if text.startswith("0x"):
            return int(text, 16)
        if text.isdigit():
            return int(text)
    return None


def _action_signature(action: dict[str, Any] | None) -> tuple[Any, ...]:
    if not isinstance(action, dict):
        return ("None",)
    kind = action.get("type", "None")
    keys = tuple(action.get("keys") or [])
    dpis = tuple(action.get("dpis") or [])
    return (kind, keys, dpis)


def _match_gesture_preset(action: dict[str, Any] | None) -> int:
    sig = _action_signature(action)
    for idx, (_label, preset) in enumerate(GESTURE_PRESETS):
        if _action_signature(preset) == sig:
            return idx
    return 0


def _gesture_actions_from_profile(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for button in profile.get("buttons") or []:
        if not isinstance(button, dict):
            continue
        if _norm_cid(button.get("cid")) != CID_GESTURE:
            continue
        action = button.get("action") or {}
        if action.get("type") != "Gestures":
            continue
        for gest in action.get("gestures") or []:
            if not isinstance(gest, dict):
                continue
            direction = gest.get("direction")
            nested = gest.get("action")
            if isinstance(direction, str) and isinstance(nested, dict):
                out[direction] = nested
    return out


def _match_thumb_scroll_preset(thumb: dict[str, Any]) -> int:
    left = thumb.get("left")
    if not isinstance(left, dict):
        return 0  # OS / omit
    mode = left.get("mode")
    axis = left.get("axis")
    for idx, (_label, preset) in enumerate(THUMB_SCROLL_PRESETS):
        if preset is None:
            continue
        if preset.get("mode") != mode:
            continue
        if mode == "Axis" and preset.get("axis") != axis:
            continue
        if mode == "OnInterval" and preset.get("mode") == "OnInterval":
            return idx
        if mode in {"Axis", "NoPress"}:
            return idx
    return 0


def _match_thumb_tap_preset(tap: Any) -> int:
    if not isinstance(tap, dict):
        return 0
    sig = _action_signature(tap)
    for idx, (_label, preset) in enumerate(THUMB_TAP_PRESETS):
        if preset is None:
            continue
        if _action_signature(preset) == sig:
            return idx
    return 0


def _match_remap_preset(profile: dict[str, Any]) -> int | None:
    """Pick remap combo index from forward/back Keypress buttons."""
    forward_keys: list[str] | None = None
    back_keys: list[str] | None = None
    for button in profile.get("buttons") or []:
        if not isinstance(button, dict):
            continue
        cid = _norm_cid(button.get("cid"))
        action = button.get("action") or {}
        if action.get("type") != "Keypress":
            continue
        keys = list(action.get("keys") or [])
        if cid == CID_FORWARD:
            forward_keys = keys
        elif cid == CID_BACK:
            back_keys = keys
    if forward_keys == ["KEY_FORWARD"] and (
        back_keys in (None, ["KEY_BACK"])
    ):
        return 0
    if forward_keys == ["KEY_BACK"]:
        return 1
    if back_keys == ["KEY_FORWARD"]:
        return 3
    if back_keys == ["KEY_BACK"] and forward_keys in (None, ["KEY_FORWARD"]):
        return 2
    return None


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MX Master Config")
        self.resize(720, 800)
        self._last_status: dict[str, Any] = {}
        self._async_busy = False
        # Worker threads only put into this queue; a GUI-thread QTimer drains it.
        # (QThread + Signal→lambda was DirectConnection and crashed PySide6/3.14
        # in QFontEngineFT when Refresh updated labels off-thread.)
        self._async_queue: SimpleQueue[
            tuple[
                Callable[[Any], None] | None,
                Callable[[BaseException], None] | None,
                tuple[str, Any],
            ]
        ] = SimpleQueue()
        self._reconnect_left = 0
        self._reconnect_active = False

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.setCentralWidget(scroll)
        root = QWidget()
        scroll.setWidget(root)
        layout = QVBoxLayout(root)

        title = QLabel("MX Master Config")
        font = title.font()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        layout.addWidget(
            QLabel(
                "mxmaster-cfg · DPI · SmartShift · HiRes · ThumbWheel · "
                "батарея · remap · жесты → polkit-helper → logid 0.3.5 (Bolt)."
            )
        )

        # --- Device status ---
        status_box = QGroupBox("Устройство")
        status_form = QFormLayout(status_box)
        status_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        self.lbl_name = QLabel("—")
        self.lbl_path = QLabel("—")
        self.lbl_pid = QLabel("—")
        # One-line battery row: wrap used to clip under the next GroupBox.
        self.lbl_battery = QLabel("—")
        self.lbl_battery.setWordWrap(False)
        self.lbl_battery.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.lbl_battery.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        bat_font = self.lbl_battery.font()
        bat_font.setBold(True)
        self.lbl_battery.setFont(bat_font)
        self.lbl_quirk = QLabel("")
        self.lbl_quirk.setWordWrap(True)
        self.lbl_quirk.setStyleSheet("color: #a15c00;")
        status_form.addRow("Имя:", self.lbl_name)
        status_form.addRow("D-Bus:", self.lbl_path)
        status_form.addRow("ProductID:", self.lbl_pid)
        status_form.addRow("Батарея:", self.lbl_battery)
        status_form.addRow("Статус:", self.lbl_quirk)
        status_box.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
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

        # --- Named on-disk profiles (XDG) ---
        prof_box = QGroupBox("Профили (~/.config/mxmaster-cfg/profiles/)")
        prof_layout = QVBoxLayout(prof_box)
        self.list_profiles = QListWidget()
        self.list_profiles.setMinimumHeight(90)
        self.list_profiles.itemDoubleClicked.connect(
            lambda _item: self._on_profile_load()
        )
        prof_layout.addWidget(self.list_profiles)
        prof_btns = QHBoxLayout()
        self.btn_prof_refresh = QPushButton("Список")
        self.btn_prof_refresh.clicked.connect(self._refresh_profile_list)
        prof_btns.addWidget(self.btn_prof_refresh)
        self.btn_prof_save = QPushButton("Сохранить как…")
        self.btn_prof_save.clicked.connect(self._on_profile_save_as)
        prof_btns.addWidget(self.btn_prof_save)
        self.btn_prof_load = QPushButton("Загрузить")
        self.btn_prof_load.clicked.connect(self._on_profile_load)
        prof_btns.addWidget(self.btn_prof_load)
        self.btn_prof_apply = QPushButton("На устройство")
        self.btn_prof_apply.setToolTip(
            "Применить выбранный профиль с диска (cfg + restart logid)"
        )
        self.btn_prof_apply.clicked.connect(self._on_profile_apply_device)
        prof_btns.addWidget(self.btn_prof_apply)
        self.btn_prof_delete = QPushButton("Удалить")
        self.btn_prof_delete.clicked.connect(self._on_profile_delete)
        prof_btns.addWidget(self.btn_prof_delete)
        prof_btns.addStretch(1)
        prof_layout.addLayout(prof_btns)
        self.lbl_prof_path = QLabel(str(profiles_dir()))
        self.lbl_prof_path.setWordWrap(True)
        self.lbl_prof_path.setStyleSheet("color: #555;")
        prof_layout.addWidget(self.lbl_prof_path)
        layout.addWidget(prof_box)

        # --- Actions ---
        buttons = QHBoxLayout()
        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.clicked.connect(self._on_refresh)
        buttons.addWidget(self.btn_refresh)

        self.btn_apply = QPushButton("Применить")
        self.btn_apply.setDefault(True)
        self.btn_apply.clicked.connect(self._on_apply)
        buttons.addWidget(self.btn_apply)

        self.btn_wake = QPushButton("Разбудить ресивер")
        self.btn_wake.setToolTip(
            "Soft USB wake Logi Bolt (046d:c548) и опрос, пока устройство "
            "не появится в logid. Полезно после Apply при device_count=0."
        )
        self.btn_wake.clicked.connect(self._on_wake_receiver)
        buttons.addWidget(self.btn_wake)

        self.btn_conflict = QPushButton("Конфликт HID++")
        self.btn_conflict.clicked.connect(self._on_check_conflict)
        buttons.addWidget(self.btn_conflict)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        hint = QLabel(
            "Применить пишет /etc/logid.cfg через pkexec и делает "
            "systemctl restart logid (при отсутствии device — soft USB wake "
            "Bolt + опрос). Батарея обновляется ~каждые 45 с без блокировки UI. "
            "Профили — именованные YAML/JSON на диске (не app-specific)."
        )
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(hint)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Загрузка устройства… (pkexec)")
        self._refresh_profile_list()

        self._battery_timer = QTimer(self)
        self._battery_timer.setInterval(BATTERY_REFRESH_MS)
        self._battery_timer.timeout.connect(self._on_battery_tick)
        self._battery_timer.start()

        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setInterval(RECONNECT_POLL_MS)
        self._reconnect_timer.timeout.connect(self._on_reconnect_tick)

        self._async_pump = QTimer(self)
        self._async_pump.setInterval(_ASYNC_PUMP_MS)
        self._async_pump.timeout.connect(self._drain_async_queue)
        self._async_pump.start()

        # Initial load after the window is shown (same safe queue path as «Обновить»).
        QTimer.singleShot(0, self._on_refresh)

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
            "schema_version": 1,
            "meta": {
                "name": "GUI current",
                "description": "Snapshot from MX Master Config GUI",
                "transport": "any",
            },
            "device": {"name": "MX Master 3S", "family": "mx-master-3s"},
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

    def _run_async(
        self,
        fn: Callable[[], Any],
        on_ok: Callable[[Any], None],
        *,
        on_err: Callable[[BaseException], None] | None = None,
        busy_message: str | None = None,
    ) -> bool:
        """Run ``fn`` in a daemon thread; deliver result via GUI-thread queue.

        Do **not** use QThread+Signal→lambda: PySide6 may invoke the callable
        with DirectConnection on the worker thread, and updating QLabel /
        QStatusBar there SIGSEGVs in QFontEngineFT (seen on Python 3.14).
        """
        if self._async_busy:
            return False
        self._async_busy = True
        if busy_message:
            self.statusBar().showMessage(busy_message)

        queue = self._async_queue

        def runner() -> None:
            try:
                payload: tuple[str, Any] = ("ok", fn())
            except BaseException as exc:  # noqa: BLE001 — marshal to GUI
                payload = ("err", exc)
            queue.put((on_ok, on_err, payload))

        threading.Thread(
            target=runner,
            name="mxmaster-cfg-helper",
            daemon=True,
        ).start()
        return True

    def _drain_async_queue(self) -> None:
        """Apply worker results on the GUI thread only."""
        while True:
            try:
                on_ok, on_err, payload = self._async_queue.get_nowait()
            except Empty:
                break
            self._async_busy = False
            kind, value = payload
            if kind == "ok":
                if on_ok is not None:
                    on_ok(value)
            elif on_err is not None:
                on_err(value)
            else:
                self.statusBar().showMessage("Ошибка: %s" % value)

    def _on_refresh(self) -> None:
        if not self._run_async(
            status,
            self._apply_status_data,
            on_err=self._on_refresh_error,
            busy_message="Обновление… (pkexec)",
        ):
            self.statusBar().showMessage("Уже выполняется запрос к helper…")

    def _on_refresh_error(self, exc: BaseException) -> None:
        self.lbl_quirk.setText(str(exc))
        self.statusBar().showMessage("Ошибка helper/pkexec")
        if isinstance(exc, PrivilegedHelperError):
            QMessageBox.warning(
                self,
                "Helper",
                f"{exc}\n\nУстановите helper:\n"
                "  scripts/install-helper.sh",
            )

    def _apply_status_data(
        self, data: dict[str, Any], *, clear_reconnect: bool = True
    ) -> None:
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
                "logid active=%s, devices=0 — пошевелите мышь или "
                "«Разбудить ресивер» (Bolt)"
                % data.get("logid_active")
            )
            return

        if clear_reconnect:
            self._stop_reconnect(clear_message=False)

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
            self.lbl_ss_torque_hint.setText(
                "Torque поддерживается — значение уйдёт в cfg."
            )
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
                state = "почти полн."
            elif status == "full":
                state = "полный"
            elif status == "discharging" or charging is False:
                state = "разряд"
            else:
                state = status or "?"
            src_raw = str(bat.get("source") or "")
            if src_raw.startswith("hidpp:"):
                src = "HID++"
            elif src_raw.startswith("upower:"):
                src = "UPower"
            elif src_raw.startswith("sysfs:"):
                src = "sysfs"
            elif "LogiOps.Battery" in src_raw:
                src = "D-Bus"
            else:
                src = "D-Bus" if src_raw else "?"
            # Single compact line so QFormLayout does not clip under DPI.
            line = "%s%% · %s · %s" % (pct, state, src)
            if bat.get("logid_stopped"):
                line += " · pause"
            tip = "Источник: %s" % (src_raw or src)
            if bat.get("feature"):
                tip += " · feature %s" % bat.get("feature")
            if bat.get("hidraw"):
                tip += " · %s" % bat.get("hidraw")
            self.lbl_battery.setText(line)
            self.lbl_battery.setToolTip(tip)
            return
        err = dev.get("battery_error") or "н/д"
        err_s = str(err)
        if "hidraw probe failed" in err_s and "UPower" in err_s:
            short = "н/д"
            tip = "Нет данных UPower/sysfs и HID++ 0x1004"
        elif "no Battery interface" in err_s:
            short = "н/д"
            tip = "Батарея недоступна (D-Bus / UPower / HID++)"
        else:
            short = "н/д"
            tip = err_s
        self.lbl_battery.setText(short)
        self.lbl_battery.setToolTip(tip)

    def _on_apply(self) -> None:
        profile = self._build_profile()
        cfg_text = CfgWriter(profile).render()

        def _do_apply() -> dict[str, Any]:
            return apply_cfg_text(cfg_text)

        def _ok(result: dict[str, Any]) -> None:
            self._handle_apply_result(profile, result, title="Применить")

        def _err(exc: BaseException) -> None:
            QMessageBox.warning(self, "Применить", str(exc))
            self.statusBar().showMessage("Apply failed")

        if not self._run_async(
            _do_apply,
            _ok,
            on_err=_err,
            busy_message="Применение cfg… (pkexec)",
        ):
            self.statusBar().showMessage("Уже выполняется запрос к helper…")

    def _handle_apply_result(
        self,
        profile: dict[str, Any],
        result: dict[str, Any],
        *,
        title: str,
        profile_name: str | None = None,
    ) -> None:
        quirk = result.get("quirk")
        devices = result.get("devices") or []
        ss = profile.get("smartshift") or {}
        hr = profile.get("hiresscroll") or {}
        tw = profile.get("thumbwheel") or {}
        gestures = []
        buttons = profile.get("buttons") or []
        if buttons:
            action = (buttons[0] or {}).get("action") or {}
            gestures = action.get("gestures") or []
        if profile_name:
            msg = (
                f"Профиль «{profile_name}» применён.\n"
                f"Записано {result.get('wrote')}\n"
                f"devices: {devices}\n"
                f"bolt_usb_wake: {result.get('bolt_usb_wake')}"
            )
        else:
            msg = (
                f"Записано {result.get('wrote')}\n"
                f"DPI: {profile.get('dpi')}\n"
                f"SmartShift: on={ss.get('on')} threshold={ss.get('threshold')}\n"
                f"HiRes: hires={hr.get('hires')} invert={hr.get('invert')} "
                f"target={hr.get('target')}\n"
                f"ThumbWheel: divert={tw.get('divert')} invert={tw.get('invert')}\n"
                f"Жесты: CID 0xc3 ({len(gestures)} направлений)\n"
                f"devices: {devices}\n"
                f"bolt_usb_wake: {result.get('bolt_usb_wake')}"
            )
        if quirk:
            msg += f"\n\n⚠ {quirk}"
        QMessageBox.information(self, title, msg)

        if devices:
            self._stop_reconnect(clear_message=False)
            self.statusBar().showMessage("Apply OK — обновляю статус…")
            self._on_refresh()
        else:
            self.statusBar().showMessage(
                "Apply OK, devices=0 — опрос Bolt / soft wake…"
            )
            self._start_reconnect()

    def _start_reconnect(self) -> None:
        self._reconnect_active = True
        self._reconnect_left = RECONNECT_MAX_POLLS
        if not self._reconnect_timer.isActive():
            self._reconnect_timer.start()
        # Immediate first poll (also covers wake already done by apply-cfg).
        self._on_reconnect_tick()

    def _stop_reconnect(self, *, clear_message: bool) -> None:
        was = self._reconnect_active
        self._reconnect_active = False
        self._reconnect_left = 0
        self._reconnect_timer.stop()
        if was and clear_message:
            self.statusBar().clearMessage()

    def _on_reconnect_tick(self) -> None:
        if not self._reconnect_active:
            self._reconnect_timer.stop()
            return
        if self._async_busy:
            return
        if self._reconnect_left <= 0:
            self._stop_reconnect(clear_message=False)
            self.statusBar().showMessage(
                "Устройство не появилось — пошевелите мышь или "
                "«Разбудить ресивер»"
            )
            return
        self._reconnect_left -= 1
        left = self._reconnect_left

        def _ok(data: dict[str, Any]) -> None:
            if not self._reconnect_active:
                return
            devices = data.get("devices") or []
            if devices:
                self._stop_reconnect(clear_message=True)
                self._apply_status_data(data, clear_reconnect=False)
                self.statusBar().showMessage(
                    "Устройство снова на связи · devices=%s"
                    % data.get("device_count")
                )
                return
            self.statusBar().showMessage(
                "Ожидание Bolt… ещё ~%s с (пошевелите мышь)"
                % max(1, left * RECONNECT_POLL_MS // 1000)
            )

        def _err(exc: BaseException) -> None:
            if self._reconnect_active:
                self.statusBar().showMessage(
                    "Опрос: %s (повтор…)" % exc
                )

        self._run_async(status, _ok, on_err=_err)

    def _on_battery_tick(self) -> None:
        if self._async_busy or self._reconnect_active:
            return
        devices = (self._last_status or {}).get("devices") or []
        if not devices:
            return

        def _ok(data: dict[str, Any]) -> None:
            # Lightweight: only refresh battery row.
            self._apply_battery_label(
                {
                    "battery": data.get("battery"),
                    "battery_available": data.get("battery_available"),
                    "battery_error": data.get("battery_error"),
                }
            )

        def _err(_exc: BaseException) -> None:
            # Silent on timer — avoid dialog spam.
            return

        self._run_async(
            lambda: get_battery(allow_stop_logid=False),
            _ok,
            on_err=_err,
        )

    def _on_wake_receiver(self) -> None:
        def _ok(data: dict[str, Any]) -> None:
            devices = data.get("devices") or []
            if devices:
                self._stop_reconnect(clear_message=True)
                self.statusBar().showMessage(
                    "Ресивер разбужен · devices=%s — обновляю…"
                    % data.get("device_count")
                )
                self._on_refresh()
            else:
                quirk = data.get("quirk") or "devices=0"
                self.lbl_quirk.setText(str(quirk))
                self.statusBar().showMessage(
                    "Wake OK, devices=0 — опрос…"
                )
                self._start_reconnect()

        def _err(exc: BaseException) -> None:
            QMessageBox.warning(self, "Разбудить ресивер", str(exc))
            self.statusBar().showMessage("Wake failed")

        if not self._run_async(
            wake_receiver,
            _ok,
            on_err=_err,
            busy_message="Soft USB wake Bolt… (pkexec)",
        ):
            self.statusBar().showMessage("Уже выполняется запрос к helper…")

    def _selected_profile_name(self) -> str | None:
        item = self.list_profiles.currentItem()
        if item is None:
            return None
        return item.text().strip() or None

    def _refresh_profile_list(self) -> None:
        current = self._selected_profile_name()
        self.list_profiles.clear()
        self.lbl_prof_path.setText(str(profiles_dir()))
        for entry in list_profiles():
            self.list_profiles.addItem(entry.name)
        if current:
            matches = self.list_profiles.findItems(
                current, Qt.MatchFlag.MatchExactly
            )
            if matches:
                self.list_profiles.setCurrentItem(matches[0])

    def _on_profile_save_as(self) -> None:
        suggested = self._selected_profile_name() or "mx-master-3s"
        name, ok = QInputDialog.getText(
            self,
            "Сохранить профиль",
            "Имя профиля (файл в ~/.config/mxmaster-cfg/profiles/):",
            text=suggested,
        )
        if not ok:
            return
        try:
            path = save_named_profile(name, self._build_profile(), fmt="yaml")
        except ProfileError as exc:
            QMessageBox.warning(self, "Профиль", str(exc))
            return
        self._refresh_profile_list()
        matches = self.list_profiles.findItems(
            path.stem, Qt.MatchFlag.MatchExactly
        )
        if matches:
            self.list_profiles.setCurrentItem(matches[0])
        self.statusBar().showMessage(f"Профиль сохранён: {path}")
        QMessageBox.information(self, "Профиль", f"Сохранено:\n{path}")

    def _on_profile_load(self) -> None:
        name = self._selected_profile_name()
        if not name:
            QMessageBox.information(
                self, "Профиль", "Выберите профиль в списке."
            )
            return
        try:
            profile = load_named_profile(name)
            self._apply_profile_to_ui(profile)
        except ProfileError as exc:
            QMessageBox.warning(self, "Профиль", str(exc))
            return
        self.statusBar().showMessage(f"Загружен профиль: {name}")

    def _on_profile_apply_device(self) -> None:
        name = self._selected_profile_name()
        if not name:
            QMessageBox.information(
                self, "Профиль", "Выберите профиль в списке."
            )
            return
        try:
            profile = load_named_profile(name)
            self._apply_profile_to_ui(profile)
        except ProfileError as exc:
            QMessageBox.warning(self, "Профиль", str(exc))
            return
        cfg_text = CfgWriter(profile).render()

        def _do_apply() -> dict[str, Any]:
            return apply_cfg_text(cfg_text)

        def _ok(result: dict[str, Any]) -> None:
            self._handle_apply_result(
                profile,
                result,
                title="На устройство",
                profile_name=name,
            )

        def _err(exc: BaseException) -> None:
            QMessageBox.warning(self, "На устройство", str(exc))
            self.statusBar().showMessage("Profile apply failed")

        if not self._run_async(
            _do_apply,
            _ok,
            on_err=_err,
            busy_message=f"Профиль «{name}» → устройство…",
        ):
            self.statusBar().showMessage("Уже выполняется запрос к helper…")

    def _on_profile_delete(self) -> None:
        name = self._selected_profile_name()
        if not name:
            QMessageBox.information(
                self, "Профиль", "Выберите профиль в списке."
            )
            return
        reply = QMessageBox.question(
            self,
            "Удалить профиль",
            f"Удалить «{name}» с диска?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            delete_named_profile(name)
        except ProfileError as exc:
            QMessageBox.warning(self, "Профиль", str(exc))
            return
        self._refresh_profile_list()
        self.statusBar().showMessage(f"Удалён профиль: {name}")

    def _apply_profile_to_ui(self, profile: dict[str, Any]) -> None:
        if profile.get("dpi") is not None:
            self.spin_dpi.setValue(int(profile["dpi"]))

        ss = profile.get("smartshift") or {}
        if isinstance(ss, dict):
            if "on" in ss:
                self.chk_ss_on.setChecked(bool(ss["on"]))
            if ss.get("threshold") is not None:
                self.spin_ss_threshold.setValue(int(ss["threshold"]))
            if ss.get("torque") is not None and self.spin_ss_torque.isEnabled():
                self.spin_ss_torque.setValue(int(ss["torque"]))

        hr = profile.get("hiresscroll") or {}
        if isinstance(hr, dict):
            if "hires" in hr:
                self.chk_hr_hires.setChecked(bool(hr["hires"]))
            if "invert" in hr:
                self.chk_hr_invert.setChecked(bool(hr["invert"]))
            if "target" in hr:
                self.chk_hr_target.setChecked(bool(hr["target"]))

        tw = profile.get("thumbwheel") or {}
        if isinstance(tw, dict):
            if "divert" in tw:
                self.chk_tw_divert.setChecked(bool(tw["divert"]))
            if "invert" in tw:
                self.chk_tw_invert.setChecked(bool(tw["invert"]))
            self.combo_tw_scroll.setCurrentIndex(
                _match_thumb_scroll_preset(tw)
            )
            self.combo_tw_tap.setCurrentIndex(_match_thumb_tap_preset(tw.get("tap")))

        for direction, action in _gesture_actions_from_profile(profile).items():
            if direction in self.gesture_combos:
                self.gesture_combos[direction].setCurrentIndex(
                    _match_gesture_preset(action)
                )

        remap_idx = _match_remap_preset(profile)
        if remap_idx is not None:
            self.combo_remap.setCurrentIndex(remap_idx)

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
