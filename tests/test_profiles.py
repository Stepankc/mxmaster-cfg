# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from mxmaster_cfg.adapter.logiops_cfg import CfgWriter, load_profile
from mxmaster_cfg.profiles import (
    ProfileError,
    delete_named_profile,
    list_profiles,
    load_named_profile,
    profiles_dir,
    save_named_profile,
    sanitize_profile_name,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "profiles" / "mx-master-3s-default.yaml"


@pytest.fixture()
def xdg_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    return tmp_path


def test_sanitize_rejects_empty() -> None:
    with pytest.raises(ProfileError):
        sanitize_profile_name("   ")


def test_save_load_delete_roundtrip(xdg_tmp: Path) -> None:
    _ = xdg_tmp
    profile = load_profile(EXAMPLE)
    path = save_named_profile("demo-3s", profile, fmt="yaml")
    assert path.parent == profiles_dir()
    assert path.suffix == ".yaml"
    assert path.is_file()

    names = [e.name for e in list_profiles()]
    assert "demo-3s" in names

    loaded = load_named_profile("demo-3s")
    assert loaded["schema_version"] == 1
    assert loaded["device"]["name"] == "MX Master 3S"
    assert loaded["dpi"] == profile["dpi"]

    # Reload → cfg still renders.
    text = CfgWriter(loaded).render()
    assert 'name: "MX Master 3S"' in text

    deleted = delete_named_profile("demo-3s")
    assert deleted
    assert "demo-3s" not in [e.name for e in list_profiles()]


def test_json_format_and_overwrite(xdg_tmp: Path) -> None:
    _ = xdg_tmp
    profile = {
        "schema_version": 1,
        "device": {"name": "MX Master 3S"},
        "dpi": 1200,
    }
    path = save_named_profile("json-demo", profile, fmt="json")
    assert path.suffix == ".json"
    loaded = load_named_profile("json-demo")
    assert loaded["dpi"] == 1200

    # Switching format replaces the previous file for the same stem.
    path2 = save_named_profile(
        "json-demo", {**profile, "dpi": 1400}, fmt="yaml"
    )
    assert path2.suffix == ".yaml"
    assert not path.exists()
    assert load_named_profile("json-demo")["dpi"] == 1400


def test_yaml_contains_meta_name(xdg_tmp: Path) -> None:
    _ = xdg_tmp
    profile = {
        "schema_version": 1,
        "device": {"name": "MX Master 3S"},
        "dpi": 1000,
    }
    path = save_named_profile("named", profile)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["meta"]["name"] == "named"
