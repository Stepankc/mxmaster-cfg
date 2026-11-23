#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Quick D-Bus probes for Stepan's spike (system bus by default).
set -euo pipefail

SERVICE="pizza.pixl.LogiOps"
ROOT="/pizza/pixl/logiops"

echo "== busctl status =="
busctl --system status "$SERVICE" || true

echo
echo "== busctl tree =="
busctl --system tree "$SERVICE" || true

echo
echo "== introspect root =="
busctl --system introspect "$SERVICE" "$ROOT" || true

echo
echo "== Python client =="
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT_DIR}/src${PYTHONPATH:+:$PYTHONPATH}"
python3 -m mxmaster_cfg.adapter.logiops_dbus --tree || true
