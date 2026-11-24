# SPDX-License-Identifier: GPL-3.0-or-later
"""Keypress capture bar: Record → listen for a chord → store KEY_* list.

Esc cancels listening without changing the stored chord.
Clear empties the chord. Re-Record replaces it.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from mxmaster_cfg.buttons import format_keys_text
from mxmaster_cfg.key_capture import (
    chord_from_qt_key,
    is_escape_key,
    is_modifier_key,
)


class KeyCaptureBar(QWidget):
    """Inline capture control for one remappable CID."""

    keys_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._keys: list[str] = []
        self._listening = False
        self._keys_before_listen: list[str] = []

        self.lbl = QLabel("—")
        self.lbl.setWordWrap(True)
        self.lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        self.btn_record = QPushButton("Записать")
        self.btn_record.setToolTip(
            "Record / Записать: нажмите, затем chord на клавиатуре. "
            "Esc — отмена без изменения."
        )
        self.btn_record.clicked.connect(self._on_record_clicked)

        self.btn_clear = QPushButton("Очистить")
        self.btn_clear.setToolTip("Clear stored Keypress chord")
        self.btn_clear.clicked.connect(self.clear_keys)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(self.lbl, stretch=1)
        row.addWidget(self.btn_record)
        row.addWidget(self.btn_clear)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._refresh_label()

    def keys(self) -> list[str]:
        return list(self._keys)

    def set_keys(self, keys: list[str] | None) -> None:
        self._stop_listening(restore=False)
        self._keys = list(keys or [])
        self._refresh_label()
        self.keys_changed.emit()

    def clear_keys(self) -> None:
        self._stop_listening(restore=False)
        if not self._keys:
            self._refresh_label()
            return
        self._keys = []
        self._refresh_label()
        self.keys_changed.emit()

    def is_listening(self) -> bool:
        return self._listening

    def _on_record_clicked(self) -> None:
        if self._listening:
            # Second click cancels (same as Esc).
            self._stop_listening(restore=True)
            return
        self._start_listening()

    def _start_listening(self) -> None:
        self._keys_before_listen = list(self._keys)
        self._listening = True
        self.btn_record.setText("Отмена")
        self.lbl.setText("Нажмите клавиши… / press keys… (Esc = cancel)")
        self.lbl.setStyleSheet("color: #a60; font-weight: bold;")
        self.grabKeyboard()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def _stop_listening(self, *, restore: bool) -> None:
        was = self._listening
        self._listening = False
        self.btn_record.setText("Записать")
        self.lbl.setStyleSheet("")
        if was:
            self.releaseKeyboard()
        if restore:
            self._keys = list(self._keys_before_listen)
        self._refresh_label()

    def _refresh_label(self) -> None:
        if self._listening:
            return
        if self._keys:
            self.lbl.setText(format_keys_text(self._keys))
        else:
            self.lbl.setText("нет аккорда — нажмите «Записать»")

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if not self._listening:
            super().keyPressEvent(event)
            return
        key = int(event.key())
        if is_escape_key(key):
            event.accept()
            self._stop_listening(restore=True)
            return
        if is_modifier_key(key) or event.isAutoRepeat():
            event.accept()
            return
        mods = event.modifiers()
        mods_i = int(mods.value) if hasattr(mods, "value") else int(mods)
        chord = chord_from_qt_key(key, mods_i)
        if chord is None:
            event.accept()
            return
        self._keys = chord
        event.accept()
        self._stop_listening(restore=False)
        self.keys_changed.emit()

    def keyReleaseEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if self._listening:
            event.accept()
            return
        super().keyReleaseEvent(event)


def install_capture_cancel_on_escape(
    widget: KeyCaptureBar,
    *,
    on_cancel: Callable[[], None] | None = None,
) -> None:
    """Optional hook — Esc is already handled inside KeyCaptureBar."""
    _ = (widget, on_cancel)
