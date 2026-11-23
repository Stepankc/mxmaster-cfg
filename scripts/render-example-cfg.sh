#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Render example profile → /tmp/logid.cfg without installing the package.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
python3 -m mxmaster_cfg.adapter.logiops_cfg \
  --profile "${ROOT}/examples/profiles/mx-master-3s-default.yaml" \
  --out /tmp/logid.cfg
echo "Preview:"
head -n 40 /tmp/logid.cfg
