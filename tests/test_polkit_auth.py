# SPDX-License-Identifier: GPL-3.0-or-later
"""Sanity checks for polkit policy/rules that avoid mid-session re-prompts."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "polkit" / "org.mxmaster.cfg.policy"
RULES = ROOT / "polkit" / "10-mxmaster-cfg.rules"
DEB_INSTALL = ROOT / "packaging" / "debian" / "mxmaster-cfg.install"
INSTALL_HELPER = ROOT / "scripts" / "install-helper.sh"


def test_rules_file_grants_yes_for_active_local_admin() -> None:
    text = RULES.read_text(encoding="utf-8")
    assert 'action.id !== "org.mxmaster.cfg.helper"' in text
    assert "subject.active" in text
    assert "subject.local" in text
    assert 'subject.isInGroup("sudo")' in text
    assert 'subject.isInGroup("admin")' in text
    assert "polkit.Result.YES" in text
    # Must not fall back to short-lived keep for the happy path.
    assert "AUTH_ADMIN_KEEP" not in text


def test_policy_keeps_auth_admin_keep_as_fallback() -> None:
    text = POLICY.read_text(encoding="utf-8")
    assert 'id="org.mxmaster.cfg.helper"' in text
    assert "<allow_active>auth_admin_keep</allow_active>" in text
    assert (
        "org.freedesktop.policykit.exec.path"
        in text
        and "/usr/libexec/mxmaster-cfg-helper" in text
    )


def test_deb_install_ships_rules_and_policy() -> None:
    text = DEB_INSTALL.read_text(encoding="utf-8")
    assert "polkit/org.mxmaster.cfg.policy usr/share/polkit-1/actions/" in text
    assert "polkit/10-mxmaster-cfg.rules usr/share/polkit-1/rules.d/" in text


def test_install_helper_installs_rules() -> None:
    text = INSTALL_HELPER.read_text(encoding="utf-8")
    assert "10-mxmaster-cfg.rules" in text
    assert "/usr/share/polkit-1/rules.d/10-mxmaster-cfg.rules" in text
