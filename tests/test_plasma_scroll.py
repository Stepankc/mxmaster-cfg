# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from pathlib import Path

from mxmaster_cfg.adapter.plasma_scroll import (
    SCROLL_FACTOR_DEFAULT,
    ScrollTarget,
    _parse_gdbus_string_list,
    _parse_gdbus_variant,
    _read_scroll_factor_file,
    _write_scroll_factor_file,
    apply_scroll_factor,
    primary_scroll_factor,
    write_scroll_factor_file,
)


def test_parse_gdbus_variants() -> None:
    assert _parse_gdbus_variant("(<0.3>,)") == "0.3"
    assert _parse_gdbus_variant("(<1.5>,)") == "1.5"
    assert _parse_gdbus_variant("(<'Logitech USB Receiver Mouse'>,)") == (
        "'Logitech USB Receiver Mouse'"
    )
    assert _parse_gdbus_variant("(<uint32 50504>,)") == "uint32 50504"
    assert _parse_gdbus_string_list("(['event4', 'event8'],)") == [
        "event4",
        "event8",
    ]


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
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    target = ScrollTarget(
        vendor=1133, product=50504, name="Logitech USB Receiver Mouse"
    )
    monkeypatch.setattr(
        "mxmaster_cfg.adapter.plasma_scroll._kwriteconfig_bin",
        lambda: None,
    )
    monkeypatch.setattr(
        "mxmaster_cfg.adapter.plasma_scroll._kreadconfig_bin",
        lambda: None,
    )
    # No event_node → no KWin attempt; file-only path.
    written = apply_scroll_factor(0.01, targets=[target], notify=False)
    assert written == [target]
    cfg = tmp_path / "kcminputrc"
    assert _read_scroll_factor_file(cfg, target) == 0.1


def test_apply_raises_when_kwin_live_fails(monkeypatch) -> None:
    target = ScrollTarget(
        vendor=1133,
        product=50504,
        name="Logitech USB Receiver Mouse",
        event_node="event8",
    )
    monkeypatch.setattr(
        "mxmaster_cfg.adapter.plasma_scroll.write_scroll_factor_file",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "mxmaster_cfg.adapter.plasma_scroll.write_kwin_scroll_factor",
        lambda *a, **k: False,
    )
    try:
        apply_scroll_factor(0.4, targets=[target], notify=False)
        raised = False
    except RuntimeError as exc:
        raised = True
        assert "KWin scrollFactor" in str(exc)
    assert raised


def test_primary_defaults_when_unset() -> None:
    target = ScrollTarget(vendor=1133, product=1, name="Fake Mouse")
    t, factor = primary_scroll_factor(targets=[])
    assert t is None and factor is None
    import mxmaster_cfg.adapter.plasma_scroll as ps

    old = ps.read_scroll_factor
    try:
        ps.read_scroll_factor = lambda _t: None  # type: ignore[assignment]
        got, factor = primary_scroll_factor(targets=[target])
        assert got == target
        assert factor == SCROLL_FACTOR_DEFAULT
    finally:
        ps.read_scroll_factor = old  # type: ignore[assignment]


def test_write_scroll_factor_file_helper(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(
        "mxmaster_cfg.adapter.plasma_scroll._kwriteconfig_bin",
        lambda: None,
    )
    target = ScrollTarget(
        vendor=1133, product=50504, name="Logitech USB Receiver Mouse"
    )
    write_scroll_factor_file(target, 0.45, notify=False)
    assert _read_scroll_factor_file(tmp_path / "kcminputrc", target) == 0.45
