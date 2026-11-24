#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Install privileged helper + polkit policy (needs root / pkexec).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HELPER_SRC="$ROOT/helper/mxmaster-cfg-helper"
POLICY_SRC="$ROOT/polkit/org.mxmaster.cfg.policy"
HELPER_DST="/usr/libexec/mxmaster-cfg-helper"
POLICY_DST="/usr/share/polkit-1/actions/org.mxmaster.cfg.policy"
# Remove legacy path from early scaffolds so polkit annotate matches.
LEGACY_HELPER="/usr/local/libexec/mxmaster-cfg-helper"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Re-exec with pkexec…" >&2
  SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
  exec pkexec env DISPLAY="${DISPLAY:-}" WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-}" \
    XAUTHORITY="${XAUTHORITY:-}" \
    bash "$SELF" "$@"
fi

install -d /usr/libexec
install -m 0755 "$HELPER_SRC" "$HELPER_DST"
install -m 0644 "$POLICY_SRC" "$POLICY_DST"
if [[ -e "$LEGACY_HELPER" ]]; then
  rm -f "$LEGACY_HELPER"
fi

# Ensure python3 shebang works; helper is standalone (stdlib only).
command -v python3 >/dev/null

echo "Installed:"
echo "  $HELPER_DST"
echo "  $POLICY_DST"
echo "Test: pkexec $HELPER_DST status"
