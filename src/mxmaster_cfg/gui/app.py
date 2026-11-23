# SPDX-License-Identifier: GPL-3.0-or-later
"""Application bootstrap (PySide6)."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from mxmaster_cfg.gui.main_window import MainWindow


def run_app(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else ["mxmaster-cfg", *argv])
    app = QApplication(argv)
    app.setApplicationName("MX Master Configurator")  # display name; project name TBD
    app.setOrganizationName("mxmaster-linux")  # temporary
    window = MainWindow()
    window.show()
    return app.exec()
