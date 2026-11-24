# SPDX-License-Identifier: GPL-3.0-or-later
"""Main window: device, DPI, SmartShift, HiRes, thumbwheel, remap, gestures."""

from __future__ import annotations

import subprocess
import threading
import time
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
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from mxmaster_cfg.adapter.logiops_cfg import CfgWriter
from mxmaster_cfg.adapter.logiops_dbus import CID_GESTURE
from mxmaster_cfg.buttons import (
    ACTION_CHANGE_HOST_CUSTOM,
    ACTION_DEFAULT,
    ACTION_GESTURES,
    ACTION_KEY_CUSTOM,
    BUTTON_ACTION_PRESETS,
    REMAPPABLE_BUTTONS,
    action_signature,
    button_label,
    buttons_from_profile,
    change_host_preset_id,
    match_button_preset,
    normalize_host,
    resolve_button_action,
)
from mxmaster_cfg.gui.key_capture_widget import KeyCaptureBar
from mxmaster_cfg.adapter.plasma_scroll import (
    SCROLL_FACTOR_DEFAULT,
    SCROLL_FACTOR_MAX,
    SCROLL_FACTOR_MIN,
    apply_scroll_factor,
    list_logitech_scroll_targets,
    primary_scroll_factor,
)
from mxmaster_cfg.adapter.privileged import (
    PrivilegedHelperError,
    apply_cfg_text,
    set_dpi,
    set_smartshift,
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
from mxmaster_cfg.status_hold import (
    AUTO_WAKE_COOLDOWN_S,
    LAST_GOOD_HOLD_S,
    WAKE_SETTLE_MS,
    device_dicts,
    should_auto_wake,
    should_clear_device_labels,
    should_hold_last_good,
    soft_miss_quirk,
)

# Live status poll (device + battery); does not overwrite slider positions.
STATUS_POLL_MS = 15_000
# Debounce live D-Bus apply after slider / checkbox changes.
LIVE_DEBOUNCE_MS = 450
# Debounce Plasma ScrollFactor writes (user-level, no pkexec).
PLASMA_SCROLL_DEBOUNCE_MS = 200
# After apply-cfg with device_count=0, poll until Bolt reappears.
RECONNECT_POLL_MS = 2_000
RECONNECT_MAX_POLLS = 30  # ~60 s
# Drain worker results on the GUI thread (never touch QWidgets from workers).
_ASYNC_PUMP_MS = 50
DPI_STEP = 50
# Plasma ScrollFactor as centi-units (100 = 1.00×), DPI-like slider.
PLASMA_SCROLL_STEP = 5  # 0.05×
PLASMA_SCROLL_MIN = int(round(SCROLL_FACTOR_MIN * 100))  # 10
PLASMA_SCROLL_MAX = int(round(SCROLL_FACTOR_MAX * 100))  # 200
PLASMA_SCROLL_DEFAULT = int(round(SCROLL_FACTOR_DEFAULT * 100))  # 100
# Divert Axis multiplier (experimental) as centi-units.
SCROLL_MULT_STEP = 25  # 0.25×
SCROLL_MULT_MIN = 25  # 0.25×
SCROLL_MULT_MAX = 400  # 4.00×
SCROLL_MULT_DEFAULT = 100  # 1.00×


class _ValueSlider(QWidget):
    """Horizontal slider with a live numeric label (no spinbox)."""

    def __init__(
        self,
        minimum: int,
        maximum: int,
        value: int,
        *,
        step: int = 1,
        suffix: str = "",
        display_scale: float = 1.0,
        display_decimals: int = 0,
    ) -> None:
        super().__init__()
        self._step = max(1, int(step))
        self._suffix = suffix
        self._display_scale = float(display_scale) if display_scale else 1.0
        self._display_decimals = max(0, int(display_decimals))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(int(minimum), int(maximum))
        self.slider.setSingleStep(self._step)
        self.slider.setPageStep(max(self._step, (maximum - minimum) // 20))
        self.slider.setTickPosition(QSlider.TickPosition.NoTicks)
        self.lbl = QLabel()
        self.lbl.setMinimumWidth(56)
        self.lbl.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self.slider, stretch=1)
        layout.addWidget(self.lbl)
        self.slider.valueChanged.connect(self._sync_label)
        self.setValue(value)

    def _snap(self, value: int) -> int:
        step = self._step
        snapped = int(round(value / step) * step)
        return max(self.slider.minimum(), min(self.slider.maximum(), snapped))

    def _sync_label(self, value: int) -> None:
        snapped = self._snap(value)
        if self._display_scale != 1.0:
            shown = snapped / self._display_scale
            fmt = "%%.%df%%s" % self._display_decimals
            self.lbl.setText(fmt % (shown, self._suffix))
        else:
            self.lbl.setText("%s%s" % (snapped, self._suffix))

    def value(self) -> int:
        return self._snap(int(self.slider.value()))

    def setValue(self, value: int) -> None:
        snapped = self._snap(int(value))
        blocked = self.slider.blockSignals(True)
        self.slider.setValue(snapped)
        self.slider.blockSignals(blocked)
        self._sync_label(snapped)

    def setEnabled(self, enabled: bool) -> None:  # noqa: A003 — Qt API
        self.slider.setEnabled(enabled)
        self.lbl.setEnabled(enabled)
        super().setEnabled(enabled)

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

def _match_gesture_preset(action: dict[str, Any] | None) -> int:
    sig = action_signature(action if isinstance(action, dict) else None)
    for idx, (_label, preset) in enumerate(GESTURE_PRESETS):
        if action_signature(preset) == sig:
            return idx
    return 0


def _gesture_actions_from_profile(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for button in profile.get("buttons") or []:
        if not isinstance(button, dict):
            continue
        cid_raw = button.get("cid")
        if isinstance(cid_raw, int):
            cid = cid_raw
        elif isinstance(cid_raw, str) and cid_raw.lower().startswith("0x"):
            cid = int(cid_raw, 16)
        else:
            continue
        if cid != CID_GESTURE:
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


def _multiplier_from_hires_axes(hr: dict[str, Any]) -> float | None:
    """Best-effort |axis_multiplier| from explicit up/down Axis gestures."""
    for side in ("up", "down"):
        gest = hr.get(side)
        if not isinstance(gest, dict):
            continue
        if gest.get("mode") != "Axis":
            continue
        raw = gest.get("axis_multiplier")
        if raw is None:
            continue
        try:
            return abs(float(raw))
        except (TypeError, ValueError):
            continue
    return None


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MX Master Config")
        self.resize(720, 800)
        self._last_status: dict[str, Any] = {}
        # Last successful full-device status (dict devices); used on soft misses.
        self._last_good_status: dict[str, Any] | None = None
        self._last_good_monotonic: float = 0.0
        self._last_wake_monotonic: float = 0.0
        self._auto_wake_pending = False
        self._async_busy = False
        self._suppress_live = False
        self._initial_sync_done = False
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
        self._status_seq = 0

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
                "батарея · remap всех CID · жесты → polkit-helper → logid 0.3.5."
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
        self.btn_reread = QPushButton("Перечитать")
        self.btn_reread.setFlat(True)
        self.btn_reread.setToolTip(
            "Разово перечитать устройство и подтянуть слайдеры "
            "(обычно не нужно — статус обновляется сам)."
        )
        self.btn_reread.clicked.connect(lambda: self._on_refresh(sync_controls=True))
        status_form.addRow("", self.btn_reread)
        status_box.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        layout.addWidget(status_box)

        # --- DPI ---
        dpi_box = QGroupBox("DPI")
        dpi_form = QFormLayout(dpi_box)
        self.slider_dpi = _ValueSlider(200, 8000, 1000, step=DPI_STEP)
        self.slider_dpi.setToolTip(
            "Живой SetDPI по D-Bus (с задержкой). «Применить» пишет в cfg."
        )
        dpi_form.addRow("Целевой DPI:", self.slider_dpi)
        layout.addWidget(dpi_box)

        # --- Scroll speed (Plasma ScrollFactor — safe, no divert) ---
        scroll_box = QGroupBox("Скорость скролла (Plasma / libinput)")
        scroll_form = QFormLayout(scroll_box)
        self.slider_plasma_scroll = _ValueSlider(
            PLASMA_SCROLL_MIN,
            PLASMA_SCROLL_MAX,
            PLASMA_SCROLL_DEFAULT,
            step=PLASMA_SCROLL_STEP,
            suffix="×",
            display_scale=100.0,
            display_decimals=2,
        )
        self.slider_plasma_scroll.setToolTip(
            "Plasma/KWin scrollFactor: live D-Bus на Wayland "
            "(org.kde.KWin.InputDevice.scrollFactor) + persist в "
            "~/.config/kcminputrc. Одного kwriteconfig --notify мало — "
            "композитор не подхватывает. Без divert. "
            "Меньше = меньше строк на щелчок трещотки."
        )
        self.lbl_plasma_scroll = QLabel("устройство: —")
        self.lbl_plasma_scroll.setStyleSheet("color: #555;")
        self.lbl_plasma_scroll.setWordWrap(True)
        self.lbl_plasma_hint = QLabel(
            "Kubuntu/Wayland: слайдер сразу меняет KWin scrollFactor "
            "(Bolt: Logitech USB Receiver Mouse 1133:50504). HID++ не умеет "
            "«строк на щелчок». Без divert страница всегда скроллится."
        )
        self.lbl_plasma_hint.setWordWrap(True)
        scroll_form.addRow("Скорость:", self.slider_plasma_scroll)
        scroll_form.addRow(self.lbl_plasma_scroll)
        scroll_form.addRow(self.lbl_plasma_hint)
        layout.addWidget(scroll_box)

        # --- SmartShift ---
        ss_box = QGroupBox("SmartShift / MagSpeed")
        ss_form = QFormLayout(ss_box)
        self.chk_ss_on = QCheckBox("Включён (SmartShift / ratchet on)")
        self.chk_ss_on.setChecked(True)
        self.chk_ss_on.setToolTip(
            "logiops GetConfig: mode 2=on, 1=off, 0=unset. "
            "Снятие галочки пишет on:false (не clear). Live D-Bus + cfg. "
            "При включении hi-res сбрасывается — иначе микроскролл между "
            "щелчками трещотки."
        )
        self.lbl_ss_state = QLabel("состояние: —")
        self.lbl_ss_state.setStyleSheet("color: #555;")
        self.slider_ss_threshold = _ValueSlider(1, 50, 30, step=1)
        self.slider_ss_threshold.setToolTip(
            "SmartShift threshold — live SetConfig, затем «Применить» в cfg."
        )
        self.slider_ss_torque = _ValueSlider(0, 100, 50, step=1)
        self.slider_ss_torque.setEnabled(False)
        self.lbl_ss_torque_hint = QLabel(
            "TorqueSupport=false на MX Master 3S — крутящий момент в cfg не пишем."
        )
        self.lbl_ss_torque_hint.setWordWrap(True)
        ss_form.addRow(self.chk_ss_on)
        ss_form.addRow("D-Bus:", self.lbl_ss_state)
        ss_form.addRow("Threshold:", self.slider_ss_threshold)
        ss_form.addRow("Torque:", self.slider_ss_torque)
        ss_form.addRow(self.lbl_ss_torque_hint)
        layout.addWidget(ss_box)

        # --- HiRes Wheel (feature 0x2121) + optional divert Axis ---
        hr_box = QGroupBox("Колесо: hi-res / divert (HiresScroll / 0x2121)")
        hr_form = QFormLayout(hr_box)
        self.chk_hr_hires = QCheckBox(
            "Hi-res (плавный микроскролл между щелчками)"
        )
        # Default OFF: SmartShift/ratchet → one notch = one scroll step.
        self.chk_hr_hires.setChecked(False)
        self.chk_hr_hires.setToolTip(
            "logiops hiresscroll.hires → HID++ HiRes. "
            "ВКЛ: скролл от малейшего движения даже в режиме трещотки. "
            "ВЫКЛ (рекомендуется с SmartShift): скролл только на щелчок "
            "notch. GetConfig: первый bool из bbb."
        )
        self.chk_hr_invert = QCheckBox("Invert (инверсия направления)")
        self.chk_hr_invert.setChecked(False)
        self.chk_hr_invert.setToolTip("logiops hiresscroll.invert")
        self.chk_hr_target = QCheckBox(
            "Target / divert (только вместе с Axis-скоростью)"
        )
        self.chk_hr_target.setChecked(False)
        self.chk_hr_target.setEnabled(False)
        self.chk_hr_target.setToolTip(
            "HID++ Mode::Target. Один target:true БЕЗ up/down Axis "
            "глотает колесо (нет скролла страниц). Включается только "
            "чекбоксом ниже; Apply без скорости пишет target:false."
        )
        self.chk_hr_speed = QCheckBox(
            "Экспериментально: скорость через divert (Axis)"
        )
        self.chk_hr_speed.setChecked(False)
        self.chk_hr_speed.setToolTip(
            "Обходной путь logiops #116. По умолчанию ВЫКЛ — используйте "
            "слайдер Plasma выше. Если включить: всегда target + up/down "
            "Axis вместе; hi-res гасится (REL_WHEEL, не HI_RES), чтобы "
            "не вернуть микроскролл. «Применить в cfg»."
        )
        self.slider_hr_mult = _ValueSlider(
            SCROLL_MULT_MIN,
            SCROLL_MULT_MAX,
            SCROLL_MULT_DEFAULT,
            step=SCROLL_MULT_STEP,
            suffix="×",
            display_scale=100.0,
            display_decimals=2,
        )
        self.slider_hr_mult.setEnabled(False)
        self.slider_hr_mult.setToolTip(
            "axis_multiplier для REL_WHEEL при divert-скорости. "
            "Без Apply / без обеих осей скролл не меняется."
        )
        self.lbl_hr_state = QLabel("D-Bus: —")
        self.lbl_hr_state.setStyleSheet("color: #555;")
        self.lbl_hr_hint = QLabel(
            "Ratchet (SmartShift on): держите hi-res ВЫКЛ — скролл по "
            "щелчку, не от микродвижений. Divert без обеих осей ломает "
            "колесо; CfgWriter принудительно target:false. См. "
            "docs/scroll-speed.md."
        )
        self.lbl_hr_hint.setWordWrap(True)
        hr_form.addRow(self.chk_hr_hires)
        hr_form.addRow(self.chk_hr_invert)
        hr_form.addRow(self.chk_hr_target)
        hr_form.addRow(self.chk_hr_speed)
        hr_form.addRow("Множитель Axis:", self.slider_hr_mult)
        hr_form.addRow(self.lbl_hr_state)
        hr_form.addRow(self.lbl_hr_hint)
        layout.addWidget(hr_box)

        # Shared KEY_* completer model (buttons + thumb free-form editors).
        self._key_completer_model = QStringListModel(list(COMMON_KEY_NAMES))

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
        for preset_id, label, _g in THUMB_SCROLL_PRESETS:
            self.combo_tw_scroll.addItem(label, preset_id)
        self.combo_tw_scroll.setCurrentIndex(0)
        self.combo_tw_scroll.setToolTip(
            "Пресет left/right или Axis / OnInterval Keypress (свой). "
            "Нужен divert."
        )
        self.combo_tw_scroll.currentIndexChanged.connect(
            self._on_thumb_scroll_changed
        )

        self.edit_tw_axis = QLineEdit(DEFAULT_CUSTOM_AXIS)
        self.edit_tw_axis.setPlaceholderText("REL_HWHEEL_HI_RES")
        self.edit_tw_axis.setToolTip(
            "Свободный Axis: имя оси (REL_HWHEEL*, REL_WHEEL*…)."
        )
        axis_completer = QCompleter(list(COMMON_AXIS_NAMES), self.edit_tw_axis)
        axis_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        axis_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.edit_tw_axis.setCompleter(axis_completer)
        self.spin_tw_mult = QDoubleSpinBox()
        self.spin_tw_mult.setRange(0.05, 20.0)
        self.spin_tw_mult.setSingleStep(0.25)
        self.spin_tw_mult.setDecimals(3)
        self.spin_tw_mult.setValue(DEFAULT_CUSTOM_MULTIPLIER)
        self.spin_tw_mult.setToolTip(
            "axis_multiplier (модуль; left −, right +)."
        )
        self.tw_axis_row = QWidget()
        tw_axis_l = QHBoxLayout(self.tw_axis_row)
        tw_axis_l.setContentsMargins(0, 0, 0, 0)
        tw_axis_l.addWidget(self.edit_tw_axis, stretch=1)
        tw_axis_l.addWidget(QLabel("×"))
        tw_axis_l.addWidget(self.spin_tw_mult)
        self.tw_axis_row.setVisible(False)

        self.spin_tw_interval = QSpinBox()
        self.spin_tw_interval.setRange(1, 64)
        self.spin_tw_interval.setValue(DEFAULT_CUSTOM_INTERVAL)
        self.spin_tw_interval.setToolTip("OnInterval interval (шаги колеса).")
        self.edit_tw_scroll_keys = QLineEdit()
        self.edit_tw_scroll_keys.setPlaceholderText(
            "KEY_LEFTCTRL + KEY_TAB"
        )
        self.edit_tw_scroll_keys.setToolTip(
            "OnInterval Keypress: KEY_* через + / запятую / пробел."
        )
        scroll_key_completer = QCompleter(
            self._key_completer_model, self.edit_tw_scroll_keys
        )
        scroll_key_completer.setCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive
        )
        scroll_key_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.edit_tw_scroll_keys.setCompleter(scroll_key_completer)
        self.tw_interval_row = QWidget()
        tw_iv_l = QHBoxLayout(self.tw_interval_row)
        tw_iv_l.setContentsMargins(0, 0, 0, 0)
        tw_iv_l.addWidget(QLabel("interval"))
        tw_iv_l.addWidget(self.spin_tw_interval)
        tw_iv_l.addWidget(self.edit_tw_scroll_keys, stretch=1)
        self.tw_interval_row.setVisible(False)

        self.combo_tw_tap = QComboBox()
        self.combo_tw_touch = QComboBox()
        self.combo_tw_proxy = QComboBox()
        self.tw_action_key_edits: dict[str, QLineEdit] = {}
        for combo, field, tip in (
            (self.combo_tw_tap, "tap", "thumbwheel.tap (одиночный тап)"),
            (
                self.combo_tw_touch,
                "touch",
                "thumbwheel.touch (касание обода)",
            ),
            (
                self.combo_tw_proxy,
                "proxy",
                "thumbwheel.proxy (приближение пальца)",
            ),
        ):
            for preset_id, label, _a in THUMB_ACTION_PRESETS:
                combo.addItem(label, preset_id)
            combo.setCurrentIndex(0)
            combo.setToolTip(tip + ". Нужен divert. Haptic нет в 0.3.5.")
            combo.currentIndexChanged.connect(self._on_thumb_action_changed)
            key_edit = QLineEdit()
            key_edit.setPlaceholderText("KEY_MUTE  /  Ctrl+M")
            key_edit.setToolTip(
                "Свободный Keypress для "
                + field
                + ": KEY_* через + / , / пробел."
            )
            key_completer = QCompleter(self._key_completer_model, key_edit)
            key_completer.setCaseSensitivity(
                Qt.CaseSensitivity.CaseInsensitive
            )
            key_completer.setFilterMode(Qt.MatchFlag.MatchContains)
            key_edit.setCompleter(key_completer)
            key_edit.setVisible(False)
            self.tw_action_key_edits[field] = key_edit

        self.lbl_tw_state = QLabel("D-Bus: —")
        self.lbl_tw_state.setStyleSheet("color: #555;")
        self.lbl_tw_hint = QLabel(
            "GetConfig → bb (divert, invert). left/right/tap/touch/proxy — "
            "cfg (Apply). Неизвестный Axis/Keypress грузится как «свой». "
            "Haptic не в схеме logiops 0.3.5."
        )
        self.lbl_tw_hint.setWordWrap(True)
        tw_form.addRow(self.chk_tw_divert)
        tw_form.addRow(self.chk_tw_invert)
        tw_form.addRow("Left/Right:", self.combo_tw_scroll)
        tw_form.addRow("Axis (свой):", self.tw_axis_row)
        tw_form.addRow("OnInterval (свой):", self.tw_interval_row)
        tw_form.addRow("Tap:", self.combo_tw_tap)
        tw_form.addRow("", self.tw_action_key_edits["tap"])
        tw_form.addRow("Touch:", self.combo_tw_touch)
        tw_form.addRow("", self.tw_action_key_edits["touch"])
        tw_form.addRow("Proxy:", self.combo_tw_proxy)
        tw_form.addRow("", self.tw_action_key_edits["proxy"])
        tw_form.addRow(self.lbl_tw_state)
        tw_form.addRow(self.lbl_tw_hint)
        layout.addWidget(tw_box)
        self._sync_thumb_detail_editors()

        # --- Button remaps (all remappable CIDs) ---
        remap_box = QGroupBox("Remap кнопок (CID)")
        remap_form = QFormLayout(remap_box)
        self.button_combos: dict[int, QComboBox] = {}
        self.button_key_captures: dict[int, KeyCaptureBar] = {}
        self.button_host_edits: dict[int, QLineEdit] = {}
        for info in REMAPPABLE_BUTTONS:
            combo = QComboBox()
            for preset_id, preset_label, _action in BUTTON_ACTION_PRESETS:
                if (
                    preset_id == ACTION_GESTURES
                    and not info.supports_gestures
                ):
                    continue
                combo.addItem(preset_label, preset_id)
            # Select default for this button.
            default_idx = 0
            for i in range(combo.count()):
                if combo.itemData(i) == info.default_preset:
                    default_idx = i
                    break
            combo.setCurrentIndex(default_idx)
            combo.currentIndexChanged.connect(self._on_button_action_changed)

            key_cap = KeyCaptureBar()
            key_cap.setVisible(False)

            host_edit = QLineEdit()
            host_edit.setPlaceholderText("1 / 2 / 3 / next / prev")
            host_edit.setToolTip(
                "ChangeHost: номер канала Easy-Switch (1-based) или "
                "next / prev. logiops host."
            )
            host_edit.setMaximumWidth(160)
            host_edit.setVisible(False)

            row = QWidget()
            row_l = QVBoxLayout(row)
            row_l.setContentsMargins(0, 0, 0, 0)
            row_l.setSpacing(4)
            row_l.addWidget(combo)
            row_l.addWidget(key_cap)
            row_l.addWidget(host_edit)

            self.button_combos[info.cid] = combo
            self.button_key_captures[info.cid] = key_cap
            self.button_host_edits[info.cid] = host_edit
            remap_form.addRow(button_label(info, lang="ru") + ":", row)
        self.lbl_remap_hint = QLabel(
            "По умолчанию = не писать в cfg (firmware/ОС). "
            "Отключить = type None. "
            "Keypress (записать) — «Записать», затем chord на клавиатуре "
            "(Esc = отмена). "
            "ChangeHost — канал Easy-Switch (1…3 / next / prev). "
            "Жесты — только для 0xc3. Persist: «Применить в cfg»."
        )
        self.lbl_remap_hint.setWordWrap(True)
        self.lbl_remap_hint.setStyleSheet("color: #555;")
        remap_form.addRow(self.lbl_remap_hint)
        layout.addWidget(remap_box)
        self._sync_button_detail_editors()

        # --- Gestures (directions for CID 0xc3 when action = Gestures) ---
        self.gest_box = QGroupBox("Жесты (кнопка Gesture, CID 0xc3)")
        gest_form = QFormLayout(self.gest_box)
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
        layout.addWidget(self.gest_box)
        self._sync_gesture_box_enabled()

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
        self.btn_apply = QPushButton("Применить в cfg")
        self.btn_apply.setDefault(True)
        self.btn_apply.setToolTip(
            "Записать полный профиль в /etc/logid.cfg и restart logid "
            "(жесты, remap, hi-res, scroll Axis, thumb). "
            "DPI/SmartShift уже уходят live."
        )
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
            "DPI / SmartShift — live D-Bus. Скорость скролла — live "
            "Plasma ScrollFactor (без divert). Hi-res / divert Axis / "
            "жесты / remap / thumb — «Применить в cfg» (restart logid). "
            "Статус ~15 с. Профили на диске (не app-specific)."
        )
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(hint)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Загрузка устройства… (pkexec)")
        self._refresh_profile_list()

        self._status_timer = QTimer(self)
        self._status_timer.setInterval(STATUS_POLL_MS)
        self._status_timer.timeout.connect(self._on_status_poll)
        self._status_timer.start()

        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setInterval(RECONNECT_POLL_MS)
        self._reconnect_timer.timeout.connect(self._on_reconnect_tick)

        self._async_pump = QTimer(self)
        self._async_pump.setInterval(_ASYNC_PUMP_MS)
        self._async_pump.timeout.connect(self._drain_async_queue)
        self._async_pump.start()

        self._live_timer = QTimer(self)
        self._live_timer.setSingleShot(True)
        self._live_timer.setInterval(LIVE_DEBOUNCE_MS)
        self._live_timer.timeout.connect(self._on_live_apply)

        self._plasma_timer = QTimer(self)
        self._plasma_timer.setSingleShot(True)
        self._plasma_timer.setInterval(PLASMA_SCROLL_DEBOUNCE_MS)
        self._plasma_timer.timeout.connect(self._on_plasma_scroll_apply)

        # After USB wake, wait before a full status (avoid wake→empty race).
        self._wake_settle_timer = QTimer(self)
        self._wake_settle_timer.setSingleShot(True)
        self._wake_settle_timer.setInterval(WAKE_SETTLE_MS)
        self._wake_settle_timer.timeout.connect(self._on_wake_settle)

        self.slider_dpi.slider.sliderReleased.connect(self._schedule_live_apply)
        self.slider_dpi.slider.valueChanged.connect(
            lambda _v: self._schedule_live_apply()
        )
        self.slider_ss_threshold.slider.sliderReleased.connect(
            self._schedule_live_apply
        )
        self.slider_ss_threshold.slider.valueChanged.connect(
            lambda _v: self._schedule_live_apply()
        )
        self.slider_ss_torque.slider.sliderReleased.connect(
            self._schedule_live_apply
        )
        self.slider_ss_torque.slider.valueChanged.connect(
            lambda _v: self._schedule_live_apply()
        )
        self.chk_ss_on.toggled.connect(self._on_smartshift_toggled)
        self.chk_hr_speed.toggled.connect(self._on_hr_speed_toggled)
        self.slider_plasma_scroll.slider.sliderReleased.connect(
            self._schedule_plasma_scroll
        )
        self.slider_plasma_scroll.slider.valueChanged.connect(
            lambda _v: self._schedule_plasma_scroll()
        )

        # Initial load after the window is shown (sync sliders from device once).
        QTimer.singleShot(0, lambda: self._on_refresh(sync_controls=True))

    def _selected_button_preset(self, cid: int) -> str:
        combo = self.button_combos.get(cid)
        if combo is None:
            return ACTION_DEFAULT
        data = combo.currentData()
        if isinstance(data, str):
            return data
        return ACTION_DEFAULT

    def _on_button_action_changed(self, _index: int = 0) -> None:
        self._sync_gesture_box_enabled()
        self._sync_button_detail_editors()

    def _sync_gesture_box_enabled(self) -> None:
        """Show direction grid only when Gesture CID uses Gestures mode."""
        enabled = self._selected_button_preset(CID_GESTURE) == ACTION_GESTURES
        self.gest_box.setEnabled(enabled)
        self.gest_box.setVisible(True)

    def _sync_button_detail_editors(self) -> None:
        """Show Keypress / ChangeHost editors only when that preset is active."""
        for info in REMAPPABLE_BUTTONS:
            cid = info.cid
            preset = self._selected_button_preset(cid)
            key_cap = self.button_key_captures.get(cid)
            host_edit = self.button_host_edits.get(cid)
            if key_cap is not None:
                show = preset == ACTION_KEY_CUSTOM
                key_cap.setVisible(show)
                if not show and key_cap.is_listening():
                    # Leaving custom preset stops listen; keep current chord.
                    key_cap.set_keys(key_cap.keys())
            if host_edit is not None:
                host_edit.setVisible(preset == ACTION_CHANGE_HOST_CUSTOM)

    def _build_gesture_direction_actions(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for direction in GESTURE_DIRS:
            idx = self.gesture_combos[direction].currentIndex()
            action = dict(GESTURE_PRESETS[idx][1])
            if "keys" in action:
                action["keys"] = list(action["keys"])
            if "dpis" in action:
                action["dpis"] = list(action["dpis"])
            out[direction] = action
        return out

    def _custom_keys_for_cid(self, cid: int) -> list[str]:
        cap = self.button_key_captures.get(cid)
        if cap is None:
            return []
        return cap.keys()

    def _custom_host_for_cid(self, cid: int) -> int | str:
        edit = self.button_host_edits.get(cid)
        if edit is None:
            return 1
        host = normalize_host(edit.text())
        return 1 if host is None else host

    def _build_buttons(self) -> list[dict[str, Any]]:
        """Build profile ``buttons`` from per-CID pickers (omit Default)."""
        buttons: list[dict[str, Any]] = []
        for info in REMAPPABLE_BUTTONS:
            preset_id = self._selected_button_preset(info.cid)
            if preset_id == ACTION_DEFAULT:
                continue
            action = resolve_button_action(
                preset_id,
                custom_keys=self._custom_keys_for_cid(info.cid),
                host=self._custom_host_for_cid(info.cid),
                gesture_directions=self._build_gesture_direction_actions(),
            )
            if action is None:
                continue
            # Empty custom Keypress is useless — skip rather than write keys:[].
            if (
                preset_id == ACTION_KEY_CUSTOM
                and not (action.get("keys") or [])
            ):
                continue
            buttons.append(
                {
                    "cid": info.cid,
                    "label": info.key,
                    "action": action,
                }
            )
        return buttons

    def _build_profile(self) -> dict[str, Any]:
        dpi = int(self.slider_dpi.value())

        smartshift: dict[str, Any] = {
            "on": self.chk_ss_on.isChecked(),
            "threshold": int(self.slider_ss_threshold.value()),
        }
        # Only emit torque when device reports support.
        if self.slider_ss_torque.isEnabled():
            smartshift["torque"] = int(self.slider_ss_torque.value())

        thumbwheel = self._build_thumbwheel()
        hiresscroll = self._build_hiresscroll()

        return {
            "schema_version": 1,
            "meta": {
                "name": "GUI current",
                "description": "Snapshot from MX Master Config GUI",
                "transport": "any",
            },
            "device": {"name": "MX Master 3S", "family": "mx-master-3s"},
            "dpi": dpi,
            "plasma_scroll_factor": round(self._plasma_scroll_factor(), 3),
            "smartshift": smartshift,
            "hiresscroll": hiresscroll,
            "thumbwheel": thumbwheel,
            "buttons": self._build_buttons(),
        }

    def _scroll_multiplier(self) -> float:
        return max(0.05, float(self.slider_hr_mult.value()) / 100.0)

    def _plasma_scroll_factor(self) -> float:
        return max(
            SCROLL_FACTOR_MIN,
            min(
                SCROLL_FACTOR_MAX,
                float(self.slider_plasma_scroll.value()) / 100.0,
            ),
        )

    def _build_hiresscroll(self) -> dict[str, Any]:
        """Build hiresscroll; divert only when experimental speed is opted in.

        ``target:true`` without up/down Axis eats the wheel — never emit that.
        Default / safe path: hires false (discrete ratchet), target false
        (OS + Plasma ScrollFactor).
        """
        speed_on = self.chk_hr_speed.isChecked()
        # Divert Axis path forces hires off so we inject REL_WHEEL (not
        # HI_RES) and keep notch-sized steps.
        hires = False if speed_on else self.chk_hr_hires.isChecked()
        hr: dict[str, Any] = {
            "hires": bool(hires),
            "invert": self.chk_hr_invert.isChecked(),
            # Standalone target checkbox is display-only; Apply never diverts
            # unless the experimental speed opt-in is on (with multiplier).
            "target": bool(speed_on),
        }
        if speed_on:
            hr["scroll_multiplier"] = round(self._scroll_multiplier(), 3)
        return hr

    def _on_smartshift_toggled(self, checked: bool) -> None:
        """Ratchet on → kill hi-res micro-scroll between notches."""
        if checked and self.chk_hr_hires.isChecked():
            blocked = self.chk_hr_hires.blockSignals(True)
            self.chk_hr_hires.setChecked(False)
            self.chk_hr_hires.blockSignals(blocked)
            self.statusBar().showMessage(
                "SmartShift on → hi-res выкл (скролл по щелчку трещотки)"
            )
        self._schedule_live_apply()

    def _on_hr_speed_toggled(self, checked: bool) -> None:
        self.slider_hr_mult.setEnabled(bool(checked))
        # Target indicator follows speed; checkbox stays disabled (not a
        # separate control — orphan divert is unsafe).
        blocked = self.chk_hr_target.blockSignals(True)
        self.chk_hr_target.setChecked(bool(checked))
        self.chk_hr_target.blockSignals(blocked)
        self.chk_hr_target.setEnabled(False)
        if checked:
            # Discrete Axis (REL_WHEEL): turn off hi-res micro-scroll.
            blocked_h = self.chk_hr_hires.blockSignals(True)
            self.chk_hr_hires.setChecked(False)
            self.chk_hr_hires.blockSignals(blocked_h)
            self.chk_hr_hires.setEnabled(False)
        else:
            self.chk_hr_hires.setEnabled(True)

    def _apply_hiresscroll_controls(self, hr: dict[str, Any]) -> None:
        """Sync GUI hi-res / speed widgets from a profile dict."""
        if "hires" in hr:
            self.chk_hr_hires.setChecked(bool(hr["hires"]))
        if "invert" in hr:
            self.chk_hr_invert.setChecked(bool(hr["invert"]))
        mult = hr.get("scroll_multiplier")
        if mult is None:
            mult = _multiplier_from_hires_axes(hr)
        # Opt in only when profile has a complete divert+axes speed setup.
        has_speed = (
            bool(hr.get("target", False))
            and mult is not None
            and (
                isinstance(hr.get("up"), dict)
                and isinstance(hr.get("down"), dict)
                or hr.get("scroll_multiplier") is not None
            )
        )
        if has_speed and mult is not None:
            cents = int(round(float(mult) * 100))
            self.slider_hr_mult.setValue(cents)
            self.chk_hr_speed.setChecked(True)
            self._on_hr_speed_toggled(True)
        else:
            # Orphan target:true (no axes) → treat as unsafe; keep speed OFF
            # so next Apply clears divert.
            self.chk_hr_speed.setChecked(False)
            self._on_hr_speed_toggled(False)

    def _sync_plasma_scroll_controls(self) -> None:
        """Refresh Plasma ScrollFactor slider / device label from kcminputrc."""
        targets = list_logitech_scroll_targets()
        target, factor = primary_scroll_factor(targets)
        if target is None:
            self.lbl_plasma_scroll.setText(
                "устройство: Logitech-мышь не найдена в /sys "
                "(ScrollFactor не записан)"
            )
            return
        if factor is not None and not self.slider_plasma_scroll.slider.isSliderDown():
            cents = int(round(float(factor) * 100))
            cents = max(PLASMA_SCROLL_MIN, min(PLASMA_SCROLL_MAX, cents))
            blocked = self.slider_plasma_scroll.slider.blockSignals(True)
            self.slider_plasma_scroll.setValue(cents)
            self.slider_plasma_scroll.slider.blockSignals(blocked)
        extra = ""
        if len(targets) > 1:
            extra = f" · ещё {len(targets) - 1}"
        self.lbl_plasma_scroll.setText(
            f"устройство: {target.label()}{extra}"
        )

    def _schedule_plasma_scroll(self) -> None:
        if self._suppress_live or not self._initial_sync_done:
            return
        self._plasma_timer.start()

    def _on_plasma_scroll_apply(self) -> None:
        """Debounced ScrollFactor: kcminputrc + live KWin D-Bus (Wayland)."""
        if self._suppress_live:
            return
        factor = self._plasma_scroll_factor()
        try:
            written = apply_scroll_factor(factor)
        except (OSError, subprocess.SubprocessError, ValueError, RuntimeError) as exc:
            self.lbl_plasma_scroll.setText(f"ошибка scrollFactor: {exc}")
            self.statusBar().showMessage(f"Plasma scroll: {exc}")
            return
        if not written:
            self.lbl_plasma_scroll.setText(
                "устройство: нет Logitech-мыши — scrollFactor не записан"
            )
            self.statusBar().showMessage(
                "Plasma scroll: указатель Logitech не найден"
            )
            return
        live_nodes = [t.event_node for t in written if t.event_node]
        live_bit = (
            f" · KWin live {', '.join(live_nodes)}"
            if live_nodes
            else " · только файл (нет KWin node)"
        )
        self.lbl_plasma_scroll.setText(
            f"устройство: {written[0].label()}{live_bit}"
        )
        self.statusBar().showMessage(
            f"KWin scrollFactor {factor:.2f}× → {written[0].name}"
            + (f" ({live_nodes[0]})" if live_nodes else "")
        )

    def _selected_thumb_scroll_preset(self) -> str:
        data = self.combo_tw_scroll.currentData()
        return data if isinstance(data, str) else SCROLL_OMIT

    def _selected_thumb_action_preset(self, field: str) -> str:
        combo = {
            "tap": self.combo_tw_tap,
            "touch": self.combo_tw_touch,
            "proxy": self.combo_tw_proxy,
        }.get(field)
        if combo is None:
            return THUMB_ACTION_OMIT
        data = combo.currentData()
        return data if isinstance(data, str) else THUMB_ACTION_OMIT

    def _on_thumb_scroll_changed(self, _index: int = 0) -> None:
        self._sync_thumb_detail_editors()

    def _on_thumb_action_changed(self, _index: int = 0) -> None:
        self._sync_thumb_detail_editors()

    def _sync_thumb_detail_editors(self) -> None:
        scroll = self._selected_thumb_scroll_preset()
        self.tw_axis_row.setVisible(scroll == SCROLL_AXIS_CUSTOM)
        self.tw_interval_row.setVisible(scroll == SCROLL_INTERVAL_KEY_CUSTOM)
        for field, edit in self.tw_action_key_edits.items():
            edit.setVisible(
                self._selected_thumb_action_preset(field) == ACTION_KEY_CUSTOM
            )

    def _set_combo_data(self, combo: QComboBox, preset_id: str) -> None:
        idx = 0
        for i in range(combo.count()):
            if combo.itemData(i) == preset_id:
                idx = i
                break
        combo.setCurrentIndex(idx)

    def _build_thumbwheel(self) -> dict[str, Any]:
        return build_thumbwheel(
            divert=self.chk_tw_divert.isChecked(),
            invert=self.chk_tw_invert.isChecked(),
            scroll_preset=self._selected_thumb_scroll_preset(),
            tap_preset=self._selected_thumb_action_preset("tap"),
            touch_preset=self._selected_thumb_action_preset("touch"),
            proxy_preset=self._selected_thumb_action_preset("proxy"),
            axis=self.edit_tw_axis.text(),
            multiplier=float(self.spin_tw_mult.value()),
            interval=int(self.spin_tw_interval.value()),
            scroll_keys_text=self.edit_tw_scroll_keys.text(),
            tap_keys_text=self.tw_action_key_edits["tap"].text(),
            touch_keys_text=self.tw_action_key_edits["touch"].text(),
            proxy_keys_text=self.tw_action_key_edits["proxy"].text(),
        )

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

    def _next_status_seq(self) -> int:
        self._status_seq += 1
        return self._status_seq

    def _on_refresh(self, *, sync_controls: bool = True) -> None:
        seq = self._next_status_seq()

        def _ok(data: dict[str, Any]) -> None:
            if seq != self._status_seq:
                return  # stale — a newer status/wake superseded this
            self._apply_status_data(data, sync_controls=sync_controls)

        if not self._run_async(
            status,
            _ok,
            on_err=self._on_refresh_error,
            busy_message="Обновление… (pkexec)",
        ):
            self.statusBar().showMessage("Уже выполняется запрос к helper…")

    def _on_status_poll(self) -> None:
        """Periodic live status: labels/battery only (keep user slider edits)."""
        if self._async_busy or self._reconnect_active:
            return
        if self.slider_dpi.slider.isSliderDown():
            return
        if self.slider_ss_threshold.slider.isSliderDown():
            return
        if self.slider_ss_torque.slider.isSliderDown():
            return
        if self.slider_hr_mult.slider.isSliderDown():
            return
        if self.slider_plasma_scroll.slider.isSliderDown():
            return

        seq = self._next_status_seq()

        def _ok(data: dict[str, Any]) -> None:
            if seq != self._status_seq:
                return
            self._apply_status_data(data, sync_controls=False)

        def _err(_exc: BaseException) -> None:
            return

        self._run_async(status, _ok, on_err=_err)

    def _schedule_live_apply(self) -> None:
        if self._suppress_live or not self._initial_sync_done:
            return
        self._live_timer.start()

    def _on_live_apply(self) -> None:
        """Debounced live DPI + SmartShift via D-Bus (no logid restart)."""
        if self._suppress_live or self._async_busy:
            return
        dpi = int(self.slider_dpi.value())
        on = self.chk_ss_on.isChecked()
        threshold = int(self.slider_ss_threshold.value())
        torque_enabled = self.slider_ss_torque.isEnabled()
        torque = int(self.slider_ss_torque.value()) if torque_enabled else None

        def _do() -> dict[str, Any]:
            out: dict[str, Any] = {"dpi": set_dpi(dpi)}
            ss_kwargs: dict[str, Any] = {"on": on, "threshold": threshold}
            if torque is not None:
                ss_kwargs["torque"] = torque
            out["smartshift"] = set_smartshift(**ss_kwargs)
            return out

        def _ok(result: dict[str, Any]) -> None:
            self.statusBar().showMessage(
                "Live: DPI %s · SmartShift on=%s threshold=%s"
                % (dpi, on, threshold)
            )
            _ = result

        def _err(exc: BaseException) -> None:
            self.statusBar().showMessage("Live apply: %s" % exc)

        if not self._run_async(
            _do,
            _ok,
            on_err=_err,
            busy_message="Live DPI/SmartShift…",
        ):
            # Retry shortly if another helper call is in flight.
            self._live_timer.start()

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

    def _remember_good_status(self, data: dict[str, Any]) -> None:
        self._last_good_status = data
        self._last_good_monotonic = time.monotonic()

    def _hold_last_good_ui(self, empty_data: dict[str, Any]) -> bool:
        """Keep last device labels on a soft D-Bus miss; start reconnect."""
        now = time.monotonic()
        good = self._last_good_status
        if not should_hold_last_good(
            has_devices=False,
            last_good=good,
            last_good_mono=self._last_good_monotonic,
            now_mono=now,
            hold_s=LAST_GOOD_HOLD_S,
            logid_active=(
                bool(empty_data.get("logid_active"))
                if "logid_active" in empty_data
                else None
            ),
            empty_poll=empty_data,
        ):
            return False
        assert good is not None
        age = now - self._last_good_monotonic
        # Re-paint from last good without touching slider positions.
        held = dict(good)
        held["quirk"] = soft_miss_quirk(age)
        held["held_last_good"] = True
        held["empty_poll"] = {
            "logid_active": empty_data.get("logid_active"),
            "quirk": empty_data.get("quirk"),
        }
        self._last_status = held
        devices = device_dicts(good)
        dev = devices[0]
        self.lbl_name.setText(str(dev.get("name") or "?"))
        self.lbl_path.setText(str(dev.get("path") or "?"))
        pid = dev.get("product_id")
        self.lbl_pid.setText(str(pid) if pid is not None else "—")
        self._apply_battery_label(dev)
        self.lbl_quirk.setText(str(held["quirk"]))
        self.statusBar().showMessage(
            "devices=0 (держим снимок) · logid=%s · опрос…"
            % empty_data.get("logid_active")
        )
        if not self._reconnect_active:
            self._start_reconnect()
        self._maybe_auto_wake(empty_data)
        return True

    def _clear_device_labels(self, data: dict[str, Any]) -> None:
        # Never wipe a last-good snapshot on soft empty while logid is up.
        if not should_clear_device_labels(
            has_devices=False,
            last_good=self._last_good_status,
            last_good_mono=self._last_good_monotonic,
            now_mono=time.monotonic(),
            hold_s=LAST_GOOD_HOLD_S,
            logid_active=(
                bool(data.get("logid_active"))
                if "logid_active" in data
                else None
            ),
            empty_poll=data,
        ):
            if self._hold_last_good_ui(data):
                return
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

    def _maybe_auto_wake(self, data: dict[str, Any]) -> None:
        """Soft USB wake when count=0, with cooldown (no wake-race)."""
        now = time.monotonic()
        if not should_auto_wake(
            has_devices=False,
            now_mono=now,
            last_wake_mono=self._last_wake_monotonic,
            cooldown_s=AUTO_WAKE_COOLDOWN_S,
            blocked=(
                self._async_busy
                or self._auto_wake_pending
                or self._wake_settle_timer.isActive()
            ),
        ):
            return
        _ = data
        self._auto_wake_pending = True
        self._last_wake_monotonic = now
        self.statusBar().showMessage("Auto wake Bolt… (pkexec)")

        def _ok(result: dict[str, Any]) -> None:
            self._auto_wake_pending = False
            self._last_wake_monotonic = time.monotonic()
            # Do not apply path-only wake payload; settle then status.
            if not self._reconnect_active:
                self._start_reconnect()
            self._wake_settle_timer.start()
            woke = result.get("bolt_usb_wake")
            self.statusBar().showMessage(
                "Auto wake %s — ждём settle %s мс…"
                % ("OK" if woke else "skip", WAKE_SETTLE_MS)
            )

        def _err(exc: BaseException) -> None:
            self._auto_wake_pending = False
            self.statusBar().showMessage("Auto wake: %s" % exc)

        if not self._run_async(
            wake_receiver,
            _ok,
            on_err=_err,
            busy_message="Auto wake Bolt… (pkexec)",
        ):
            self._auto_wake_pending = False

    def _on_wake_settle(self) -> None:
        """Full status after USB wake settle — avoids empty race right after."""
        if self._async_busy:
            # Try again shortly once helper is free.
            self._wake_settle_timer.start()
            return
        self._on_refresh(sync_controls=True)

    def _apply_status_data(
        self,
        data: dict[str, Any],
        *,
        clear_reconnect: bool = True,
        sync_controls: bool = True,
    ) -> None:
        self._last_status = data
        devices = device_dicts(data)
        if not devices:
            if self._hold_last_good_ui(data):
                return
            self._clear_device_labels(data)
            self._maybe_auto_wake(data)
            if not self._reconnect_active:
                self._start_reconnect()
            return

        self._remember_good_status(data)
        if clear_reconnect:
            self._stop_reconnect(clear_message=False)

        dev = devices[0]
        self.lbl_name.setText(str(dev.get("name") or "?"))
        self.lbl_path.setText(str(dev.get("path") or "?"))
        pid = dev.get("product_id")
        self.lbl_pid.setText(str(pid) if pid is not None else "—")
        self._apply_battery_label(dev)
        if dev.get("dpi") is not None:
            self.lbl_quirk.setText(data.get("quirk") or "OK")
        else:
            msg = dev.get("dpi_error") or data.get("quirk") or "DPI недоступен"
            self.lbl_quirk.setText(str(msg))

        ss = dev.get("smartshift")
        torque_support = bool(dev.get("smartshift_torque_support"))
        self.slider_ss_torque.setEnabled(torque_support)
        if torque_support:
            self.lbl_ss_torque_hint.setText(
                "Torque поддерживается — live + cfg."
            )
        else:
            self.lbl_ss_torque_hint.setText(
                "TorqueSupport=false на этом устройстве — torque в cfg не пишем."
            )

        prev_suppress = self._suppress_live
        self._suppress_live = True
        try:
            if sync_controls:
                if dev.get("dpi") is not None:
                    self.slider_dpi.setValue(int(dev["dpi"]))
                if isinstance(ss, dict):
                    mode = int(ss.get("mode", 0) or 0)
                    if mode == 2:
                        self.chk_ss_on.setChecked(True)
                    elif mode == 1:
                        self.chk_ss_on.setChecked(False)
                    if ss.get("threshold") is not None:
                        self.slider_ss_threshold.setValue(int(ss["threshold"]))
                    if torque_support and ss.get("torque") is not None:
                        self.slider_ss_torque.setValue(int(ss["torque"]))

                hs = dev.get("hiresscroll")
                if isinstance(hs, dict):
                    # D-Bus only returns bbb — no axis_multiplier. Sync
                    # hires/invert only. Never mirror orphan target:true into
                    # a control that could re-Apply divert without Axis.
                    self.chk_hr_hires.setChecked(bool(hs.get("hires", False)))
                    self.chk_hr_invert.setChecked(bool(hs.get("invert", False)))
                    if hs.get("target") and not self.chk_hr_speed.isChecked():
                        self.lbl_hr_hint.setText(
                            "⚠ На устройстве target/divert=true. Без up/down "
                            "Axis колесо не скроллит страницы. Нажмите "
                            "«Применить в cfg» (скорость divert выкл.) — "
                            "запишется безопасный target:false. "
                            "Скорость: слайдер Plasma выше."
                        )

                tw = dev.get("thumbwheel")
                if isinstance(tw, dict):
                    self.chk_tw_divert.setChecked(bool(tw.get("divert", False)))
                    self.chk_tw_invert.setChecked(bool(tw.get("invert", False)))
        finally:
            self._suppress_live = prev_suppress
            if sync_controls:
                self._initial_sync_done = True
                self._live_timer.stop()
                self._plasma_timer.stop()
                self._sync_plasma_scroll_controls()

        if isinstance(ss, dict):
            mode = int(ss.get("mode", 0) or 0)
            on_state = ss.get("on_state")
            if on_state is None:
                on_state = {2: "on", 1: "off"}.get(mode, "unset")
            self.lbl_ss_state.setText("mode=%s (%s)" % (mode, on_state))
        else:
            self.lbl_ss_state.setText("состояние: н/д")

        hs = dev.get("hiresscroll")
        if isinstance(hs, dict):
            self.lbl_hr_state.setText(
                "bbb hires=%s invert=%s target=%s"
                % (
                    bool(hs.get("hires", False)),
                    bool(hs.get("invert", False)),
                    bool(hs.get("target", False)),
                )
            )
        else:
            err = dev.get("hiresscroll_error") or "н/д"
            self.lbl_hr_state.setText("D-Bus: %s" % err)

        tw = dev.get("thumbwheel")
        if isinstance(tw, dict):
            self.lbl_tw_state.setText(
                "bb divert=%s invert=%s"
                % (
                    bool(tw.get("divert", False)),
                    bool(tw.get("invert", False)),
                )
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
        plasma_factor = float(profile.get("plasma_scroll_factor") or 0)

        def _do_apply() -> dict[str, Any]:
            result = apply_cfg_text(cfg_text)
            # User-level; keep beside cfg apply so profiles restore speed too.
            if plasma_factor > 0:
                try:
                    written = apply_scroll_factor(plasma_factor)
                    result = dict(result)
                    result["plasma_scroll_factor"] = plasma_factor
                    result["plasma_scroll_devices"] = [
                        t.label() for t in written
                    ]
                except (OSError, subprocess.SubprocessError, ValueError) as exc:
                    result = dict(result)
                    result["plasma_scroll_error"] = str(exc)
            return result

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
        buttons = profile.get("buttons") or []
        gesture_dirs = 0
        for button in buttons:
            if not isinstance(button, dict):
                continue
            action = button.get("action") or {}
            if action.get("type") == "Gestures":
                gesture_dirs = len(action.get("gestures") or [])
                break
        remap_cids = []
        for button in buttons:
            if isinstance(button, dict) and button.get("cid") is not None:
                cid = button["cid"]
                remap_cids.append(
                    hex(cid) if isinstance(cid, int) else str(cid)
                )
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
                f"Plasma ScrollFactor: "
                f"{profile.get('plasma_scroll_factor', '—')}\n"
                f"SmartShift: on={ss.get('on')} threshold={ss.get('threshold')}\n"
                f"HiRes: hires={hr.get('hires')} invert={hr.get('invert')} "
                f"target={hr.get('target')} "
                f"mult={hr.get('scroll_multiplier', '—')}\n"
                f"ThumbWheel: divert={tw.get('divert')} invert={tw.get('invert')}\n"
                f"Remap: {', '.join(remap_cids) or '—'}"
                f" (жесты 0xc3: {gesture_dirs} напр.)\n"
                f"devices: {devices}\n"
                f"bolt_usb_wake: {result.get('bolt_usb_wake')}"
            )
        if result.get("plasma_scroll_error"):
            msg += f"\n\n⚠ Plasma ScrollFactor: {result['plasma_scroll_error']}"
        elif result.get("plasma_scroll_devices"):
            msg += (
                "\nPlasma devices: "
                + ", ".join(result["plasma_scroll_devices"])
            )
        if quirk:
            msg += f"\n\n⚠ {quirk}"
        QMessageBox.information(self, title, msg)

        if devices:
            self._stop_reconnect(clear_message=False)
            self.statusBar().showMessage("Apply OK — обновляю статус…")
            self._on_refresh(sync_controls=True)
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
        if self._async_busy or self._auto_wake_pending:
            return
        if self._wake_settle_timer.isActive():
            return
        if self._reconnect_left <= 0:
            self._stop_reconnect(clear_message=False)
            # Hold UI if we still have a recent good snapshot.
            if self._last_good_status and should_hold_last_good(
                has_devices=False,
                last_good=self._last_good_status,
                last_good_mono=self._last_good_monotonic,
                now_mono=time.monotonic(),
                logid_active=True,
            ):
                self.statusBar().showMessage(
                    "Опрос закончен — держим последний снимок; "
                    "пошевелите мышь или «Разбудить ресивер»"
                )
            else:
                self.statusBar().showMessage(
                    "Устройство не появилось — пошевелите мышь или "
                    "«Разбудить ресивер»"
                )
            return
        self._reconnect_left -= 1
        left = self._reconnect_left
        seq = self._next_status_seq()

        def _ok(data: dict[str, Any]) -> None:
            if seq != self._status_seq:
                return
            devices = device_dicts(data)
            if devices:
                self._stop_reconnect(clear_message=True)
                self._apply_status_data(
                    data, clear_reconnect=False, sync_controls=True
                )
                self.statusBar().showMessage(
                    "Устройство снова на связи · devices=%s"
                    % data.get("device_count")
                )
                return
            # Soft miss: keep last good labels; do not clear to "(нет)".
            if self._last_good_status and should_hold_last_good(
                has_devices=False,
                last_good=self._last_good_status,
                last_good_mono=self._last_good_monotonic,
                now_mono=time.monotonic(),
                logid_active=(
                    bool(data.get("logid_active"))
                    if "logid_active" in data
                    else True
                ),
                empty_poll=data,
            ):
                self.lbl_quirk.setText(
                    soft_miss_quirk(
                        time.monotonic() - self._last_good_monotonic
                    )
                )
            self.statusBar().showMessage(
                "Ожидание Bolt… ещё ~%s с (пошевелите мышь)"
                % max(1, left * RECONNECT_POLL_MS // 1000)
            )
            self._maybe_auto_wake(data)

        def _err(exc: BaseException) -> None:
            if self._reconnect_active:
                self.statusBar().showMessage(
                    "Опрос: %s (повтор…)" % exc
                )

        self._run_async(status, _ok, on_err=_err)

    def _on_wake_receiver(self) -> None:
        """Manual wake: USB toggle, then settle + status (no immediate race)."""

        def _ok(data: dict[str, Any]) -> None:
            self._last_wake_monotonic = time.monotonic()
            self._next_status_seq()  # invalidate in-flight status
            path_hits = data.get("device_count") or len(
                data.get("devices") or []
            )
            # Never apply path-string wake payload as full status.
            if not self._reconnect_active:
                self._start_reconnect()
            self._wake_settle_timer.start()
            self.statusBar().showMessage(
                "Ресивер разбужен · paths=%s — settle %s мс, затем статус…"
                % (path_hits, WAKE_SETTLE_MS)
            )
            if not path_hits and data.get("quirk"):
                # Soft hint only; keep last-good labels if any.
                if not (
                    self._last_good_status
                    and should_hold_last_good(
                        has_devices=False,
                        last_good=self._last_good_status,
                        last_good_mono=self._last_good_monotonic,
                        now_mono=time.monotonic(),
                        logid_active=True,
                        empty_poll=data,
                    )
                ):
                    self.lbl_quirk.setText(str(data.get("quirk")))

        def _err(exc: BaseException) -> None:
            QMessageBox.warning(self, "Разбудить ресивер", str(exc))
            self.statusBar().showMessage("Wake failed")

        self._wake_settle_timer.stop()
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
        plasma_factor = float(profile.get("plasma_scroll_factor") or 0)

        def _do_apply() -> dict[str, Any]:
            result = apply_cfg_text(cfg_text)
            if plasma_factor > 0:
                try:
                    written = apply_scroll_factor(plasma_factor)
                    result = dict(result)
                    result["plasma_scroll_factor"] = plasma_factor
                    result["plasma_scroll_devices"] = [
                        t.label() for t in written
                    ]
                except (OSError, subprocess.SubprocessError, ValueError) as exc:
                    result = dict(result)
                    result["plasma_scroll_error"] = str(exc)
            return result

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
        prev = self._suppress_live
        self._suppress_live = True
        try:
            if profile.get("dpi") is not None:
                self.slider_dpi.setValue(int(profile["dpi"]))

            if profile.get("plasma_scroll_factor") is not None:
                cents = int(
                    round(float(profile["plasma_scroll_factor"]) * 100)
                )
                cents = max(PLASMA_SCROLL_MIN, min(PLASMA_SCROLL_MAX, cents))
                self.slider_plasma_scroll.setValue(cents)

            ss = profile.get("smartshift") or {}
            if isinstance(ss, dict):
                if "on" in ss:
                    self.chk_ss_on.setChecked(bool(ss["on"]))
                if ss.get("threshold") is not None:
                    self.slider_ss_threshold.setValue(int(ss["threshold"]))
                if (
                    ss.get("torque") is not None
                    and self.slider_ss_torque.isEnabled()
                ):
                    self.slider_ss_torque.setValue(int(ss["torque"]))

            hr = profile.get("hiresscroll") or {}
            if isinstance(hr, dict):
                self._apply_hiresscroll_controls(hr)

            tw = profile.get("thumbwheel") or {}
            if isinstance(tw, dict):
                if "divert" in tw:
                    self.chk_tw_divert.setChecked(bool(tw["divert"]))
                if "invert" in tw:
                    self.chk_tw_invert.setChecked(bool(tw["invert"]))
                scroll_id = match_scroll_preset(tw)
                self._set_combo_data(self.combo_tw_scroll, scroll_id)
                axis, mult = extract_custom_axis_fields(tw)
                self.edit_tw_axis.setText(axis)
                self.spin_tw_mult.setValue(float(mult))
                interval, keys_text = extract_custom_interval_fields(tw)
                self.spin_tw_interval.setValue(int(interval))
                self.edit_tw_scroll_keys.setText(keys_text)
                for field, combo in (
                    ("tap", self.combo_tw_tap),
                    ("touch", self.combo_tw_touch),
                    ("proxy", self.combo_tw_proxy),
                ):
                    act = tw.get(field)
                    preset_id = match_thumb_action(act)
                    self._set_combo_data(combo, preset_id)
                    edit = self.tw_action_key_edits.get(field)
                    if (
                        preset_id == ACTION_KEY_CUSTOM
                        and isinstance(act, dict)
                        and edit is not None
                    ):
                        edit.setText(
                            format_keys_text(act.get("keys") or [])
                        )
                self._sync_thumb_detail_editors()

            configured = buttons_from_profile(profile)
            for info in REMAPPABLE_BUTTONS:
                combo = self.button_combos.get(info.cid)
                if combo is None:
                    continue
                key_cap = self.button_key_captures.get(info.cid)
                host_edit = self.button_host_edits.get(info.cid)
                if info.cid in configured:
                    act = configured[info.cid]
                    preset_id = match_button_preset(act)
                else:
                    act = None
                    preset_id = ACTION_DEFAULT

                if preset_id == ACTION_KEY_CUSTOM and isinstance(act, dict):
                    if key_cap is not None:
                        key_cap.set_keys(list(act.get("keys") or []))
                if (
                    preset_id
                    in {
                        ACTION_CHANGE_HOST_CUSTOM,
                        "change_host_1",
                        "change_host_2",
                        "change_host_3",
                        "change_host_next",
                        "change_host_prev",
                    }
                    and isinstance(act, dict)
                    and host_edit is not None
                ):
                    host = normalize_host(act.get("host"))
                    if host is not None:
                        host_edit.setText(str(host))
                    # Unknown host → force custom preset + editor.
                    if change_host_preset_id(host) == ACTION_CHANGE_HOST_CUSTOM:
                        preset_id = ACTION_CHANGE_HOST_CUSTOM

                idx = 0
                for i in range(combo.count()):
                    if combo.itemData(i) == preset_id:
                        idx = i
                        break
                combo.setCurrentIndex(idx)

            for direction, action in _gesture_actions_from_profile(
                profile
            ).items():
                if direction in self.gesture_combos:
                    self.gesture_combos[direction].setCurrentIndex(
                        _match_gesture_preset(action)
                    )
            self._sync_gesture_box_enabled()
            self._sync_button_detail_editors()
        finally:
            self._suppress_live = prev
            self._live_timer.stop()
            if self._initial_sync_done:
                self._schedule_live_apply()

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
