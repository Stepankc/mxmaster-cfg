# SPDX-License-Identifier: GPL-3.0-or-later
"""Entry point: ``python -m mxmaster_cfg``."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Allow ``python -m mxmaster_cfg.adapter.logiops_cfg`` via setuptools script later.
    from mxmaster_cfg.gui.app import run_app

    return run_app(argv)


if __name__ == "__main__":
    raise SystemExit(main())
