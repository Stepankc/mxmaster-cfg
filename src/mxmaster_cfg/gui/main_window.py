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
    QSlider,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from mxmaster_cfg.adapter.logiops_cfg import CfgWriter
from mxmaster_cfg.adapter.logiops_dbus import CID_BACK, CID_FORWARD, CID_GESTURE
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

# Live status poll (device + battery); does not overwrite slider positions.
STATUS_POLL_MS = 15_000
# Debounce live D-Bus apply after slider / checkbox changes.
LIVE_DEBOUNCE_MS = 450
# After apply-cfg with device_count=0, poll until Bolt reappears.
RECONNECT_POLL_MS = 2_000
RECONNECT_MAX_POLLS = 30  # ~60 s
# Drain worker results on the GUI thread (never touch QWidgets from workers).
_ASYNC_PUMP_MS = 50
DPI_STEP = 50
# Scroll multiplier stored as centi-units (100 = 1.0×) for integer slider.
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

        # --- SmartShift ---
        ss_box = QGroupBox("SmartShift / MagSpeed")
        ss_form = QFormLayout(ss_box)
        self.chk_ss_on = QCheckBox("Включён (SmartShift on)")
        self.chk_ss_on.setChecked(True)
        self.chk_ss_on.setToolTip(
            "logiops GetConfig: mode 2=on, 1=off, 0=unset. "
            "Снятие галочки пишет on:false (не clear). Live D-Bus + cfg."
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

        # --- HiRes Wheel (feature 0x2121) + divert scroll speed ---
        hr_box = QGroupBox("Hi-res scroll / скорость (HiresScroll / 0x2121)")
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
        self.chk_hr_target = QCheckBox(
            "Target / divert (только вместе со скоростью)"
        )
        self.chk_hr_target.setChecked(False)
        self.chk_hr_target.setEnabled(False)
        self.chk_hr_target.setToolTip(
            "HID++ Mode::Target. Один target:true БЕЗ up/down Axis "
            "глотает колесо (нет скролла страниц). Включается только "
            "чекбоксом скорости ниже; Apply без скорости пишет target:false."
        )
        self.chk_hr_speed = QCheckBox(
            "Экспериментально: скорость через divert (Axis)"
        )
        self.chk_hr_speed.setChecked(False)
        self.chk_hr_speed.setToolTip(
            "ОПАСНО на части стендов (Bolt): divert перехватывает колесо. "
            "По умолчанию ВЫКЛ — обычный скролл через ОС (KDE Scroll speed). "
            "Если включить: target + up/down Axis обязательны вместе "
            "(logiops #116). «Применить в cfg»."
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
            "axis_multiplier для REL_WHEEL(_HI_RES), только если divert "
            "скорость включена. Без Apply / без Axis скролл не меняется."
        )
        self.lbl_hr_state = QLabel("D-Bus: —")
        self.lbl_hr_state.setStyleSheet("color: #555;")
        self.lbl_hr_hint = QLabel(
            "Безопасный путь (по умолчанию): hires/invert, target=false — "
            "скролл страниц как у ОС. Скорость: KDE → Mouse → Scroll speed. "
            "Divert+Axis — экспериментально; target без Axis ломает колесо "
            "(см. docs/scroll-speed.md)."
        )
        self.lbl_hr_hint.setWordWrap(True)
        hr_form.addRow(self.chk_hr_hires)
        hr_form.addRow(self.chk_hr_invert)
        hr_form.addRow(self.chk_hr_target)
        hr_form.addRow(self.chk_hr_speed)
        hr_form.addRow("Множитель:", self.slider_hr_mult)
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
            "Слайдеры DPI / SmartShift — live D-Bus. Скорость скролла "
            "(divert + Axis) и жесты/remap/hi-res/thumb — через "
            "«Применить в cfg» (restart logid). Без divert скорость — в "
            "KDE System Settings. Статус ~15 с. Профили на диске "
            "(не app-specific)."
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
        self.chk_ss_on.toggled.connect(lambda _v: self._schedule_live_apply())
        self.chk_hr_speed.toggled.connect(self._on_hr_speed_toggled)

        # Initial load after the window is shown (sync sliders from device once).
        QTimer.singleShot(0, lambda: self._on_refresh(sync_controls=True))

    def _build_profile(self) -> dict[str, Any]:
        label, cid, preset = REMAP_CHOICES[self.combo_remap.currentIndex()]
        _ = label
        dpi = int(self.slider_dpi.value())
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
            "smartshift": smartshift,
            "hiresscroll": hiresscroll,
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

    def _scroll_multiplier(self) -> float:
        return max(0.05, float(self.slider_hr_mult.value()) / 100.0)

    def _build_hiresscroll(self) -> dict[str, Any]:
        """Build hiresscroll; divert only when experimental speed is opted in.

        ``target:true`` without up/down Axis eats the wheel — never emit that.
        Default / safe path: hires+invert only, target false (OS scroll).
        """
        speed_on = self.chk_hr_speed.isChecked()
        hr: dict[str, Any] = {
            "hires": self.chk_hr_hires.isChecked(),
            "invert": self.chk_hr_invert.isChecked(),
            # Standalone target checkbox is display-only; Apply never diverts
            # unless the experimental speed opt-in is on (with multiplier).
            "target": bool(speed_on),
        }
        if speed_on:
            hr["scroll_multiplier"] = round(self._scroll_multiplier(), 3)
        return hr

    def _on_hr_speed_toggled(self, checked: bool) -> None:
        self.slider_hr_mult.setEnabled(bool(checked))
        # Target indicator follows speed; checkbox stays disabled (not a
        # separate control — orphan divert is unsafe).
        blocked = self.chk_hr_target.blockSignals(True)
        self.chk_hr_target.setChecked(bool(checked))
        self.chk_hr_target.blockSignals(blocked)
        self.chk_hr_target.setEnabled(False)

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

    def _on_refresh(self, *, sync_controls: bool = True) -> None:
        def _ok(data: dict[str, Any]) -> None:
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

        def _ok(data: dict[str, Any]) -> None:
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

    def _apply_status_data(
        self,
        data: dict[str, Any],
        *,
        clear_reconnect: bool = True,
        sync_controls: bool = True,
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
                    self.chk_hr_hires.setChecked(bool(hs.get("hires", True)))
                    self.chk_hr_invert.setChecked(bool(hs.get("invert", False)))
                    if hs.get("target") and not self.chk_hr_speed.isChecked():
                        self.lbl_hr_hint.setText(
                            "⚠ На устройстве target/divert=true. Без up/down "
                            "Axis колесо не скроллит страницы. Нажмите "
                            "«Применить в cfg» (скорость divert выкл.) — "
                            "запишется безопасный target:false. "
                            "Скорость ОС: KDE → Mouse → Scroll speed."
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
                    bool(hs.get("hires", True)),
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
                f"target={hr.get('target')} "
                f"mult={hr.get('scroll_multiplier', '—')}\n"
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
                self._apply_status_data(
                    data, clear_reconnect=False, sync_controls=True
                )
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

    def _on_wake_receiver(self) -> None:
        def _ok(data: dict[str, Any]) -> None:
            devices = data.get("devices") or []
            if devices:
                self._stop_reconnect(clear_message=True)
                self.statusBar().showMessage(
                    "Ресивер разбужен · devices=%s — обновляю…"
                    % data.get("device_count")
                )
                self._on_refresh(sync_controls=True)
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
        prev = self._suppress_live
        self._suppress_live = True
        try:
            if profile.get("dpi") is not None:
                self.slider_dpi.setValue(int(profile["dpi"]))

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
                self.combo_tw_scroll.setCurrentIndex(
                    _match_thumb_scroll_preset(tw)
                )
                self.combo_tw_tap.setCurrentIndex(
                    _match_thumb_tap_preset(tw.get("tap"))
                )

            for direction, action in _gesture_actions_from_profile(
                profile
            ).items():
                if direction in self.gesture_combos:
                    self.gesture_combos[direction].setCurrentIndex(
                        _match_gesture_preset(action)
                    )

            remap_idx = _match_remap_preset(profile)
            if remap_idx is not None:
                self.combo_remap.setCurrentIndex(remap_idx)
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
