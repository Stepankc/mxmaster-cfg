#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# One-click launcher for MX Master configurator (no pip install required).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"

# Prefer system PySide6 (apt) / venv python if already activated.
exec python3 -m mxmaster_cfg "$@"
