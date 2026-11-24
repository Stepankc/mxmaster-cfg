# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from pathlib import Path

from mxmaster_cfg.adapter.plasma_scroll import (
    SCROLL_FACTOR_DEFAULT,
    ScrollTarget,
    _read_scroll_factor_file,
    _write_scroll_factor_file,
    apply_scroll_factor,
    primary_scroll_factor,
)


def test_write_read_scroll_factor_file(tmp_path: Path) -> None:
    path = tmp_path / "kcminputrc"
    target = ScrollTarget(
        vendor=1133, product=50504, name="Logitech USB Receiver Mouse"
    )
    _write_scroll_factor_file(path, target, 0.3)
    assert _read_scroll_factor_file(path, target) == 0.3
    text = path.read_text(encoding="utf-8")
    assert "[Libinput][1133][50504][Logitech USB Receiver Mouse]" in text
    assert "ScrollFactor=0.3" in text

    _write_scroll_factor_file(path, target, 0.15)
    assert _read_scroll_factor_file(path, target) == 0.15


def test_write_preserves_other_keys(tmp_path: Path) -> None:
    path = tmp_path / "kcminputrc"
    path.write_text(
        "[Libinput][1133][50504][Logitech USB Receiver Mouse]\n"
        "PointerAccelerationProfile=1\n"
        "ScrollFactor=0.9\n",
        encoding="utf-8",
    )
    target = ScrollTarget(
        vendor=1133, product=50504, name="Logitech USB Receiver Mouse"
    )
    _write_scroll_factor_file(path, target, 0.25)
    text = path.read_text(encoding="utf-8")
    assert "PointerAccelerationProfile=1" in text
    assert "ScrollFactor=0.25" in text


def test_apply_scroll_factor_clamps(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "kcminputrc"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    # Point kcminputrc at tmp via XDG — file lives at tmp/kcminputrc only if
    # home/.config is XDG; our helper uses xdg_config_home()/kcminputrc.
    # With XDG_CONFIG_HOME=tmp, path is tmp/kcminputrc.
    target = ScrollTarget(
        vendor=1133, product=50504, name="Logitech USB Receiver Mouse"
    )
    # Force file backend by hiding kwriteconfig binaries.
    monkeypatch.setattr(
        "mxmaster_cfg.adapter.plasma_scroll._kwriteconfig_bin",
        lambda: None,
    )
    monkeypatch.setattr(
        "mxmaster_cfg.adapter.plasma_scroll._kreadconfig_bin",
        lambda: None,
    )
    written = apply_scroll_factor(0.01, targets=[target], notify=False)
    assert written == [target]
    assert path.is_file() or (tmp_path / "kcminputrc").is_file()
    cfg = path if path.is_file() else tmp_path / "kcminputrc"
    # Clamped to SCROLL_FACTOR_MIN (0.10).
    assert _read_scroll_factor_file(cfg, target) == 0.1


def test_primary_defaults_when_unset() -> None:
    target = ScrollTarget(vendor=1133, product=1, name="Fake Mouse")
    # No file / no kread → default 1.0 from primary_scroll_factor logic when
    # read returns None — exercise with empty targets list.
    t, factor = primary_scroll_factor(targets=[])
    assert t is None and factor is None
    # With a target but unreadable factor, primary uses DEFAULT.
    # Simulate by passing target and patching read.
    import mxmaster_cfg.adapter.plasma_scroll as ps

    old = ps.read_scroll_factor
    try:
        ps.read_scroll_factor = lambda _t: None  # type: ignore[assignment]
        got, factor = primary_scroll_factor(targets=[target])
        assert got == target
        assert factor == SCROLL_FACTOR_DEFAULT
    finally:
        ps.read_scroll_factor = old  # type: ignore[assignment]
