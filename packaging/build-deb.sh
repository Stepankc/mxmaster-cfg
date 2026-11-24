#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Build a binary .deb from the repo using packaging/debian/.
#
# Usage (from repo root or here):
#   ./packaging/build-deb.sh
#   # or: dpkg-buildpackage -us -uc -b   (after linking debian/)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -e debian && ! -L debian ]]; then
  echo "error: ./debian exists and is not a symlink to packaging/debian" >&2
  echo "       move it aside, then re-run." >&2
  exit 1
fi
ln -sfn packaging/debian debian

# Ensure helper is executable in the tree.
chmod +x helper/mxmaster-cfg-helper packaging/debian/rules packaging/build-deb.sh

echo "Building mxmaster-cfg with dpkg-buildpackage (binary-only)…"
dpkg-buildpackage -us -uc -b

echo
echo "Artifacts (parent of repo):"
ls -1 ../mxmaster-cfg_*.deb ../mxmaster-cfg_*.changes ../mxmaster-cfg_*.buildinfo 2>/dev/null || true
echo
echo "Install: sudo apt install ../mxmaster-cfg_*.deb"
echo "Or:      sudo dpkg -i ../mxmaster-cfg_*.deb && sudo apt -f install"
