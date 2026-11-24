# SPDX-License-Identifier: GPL-3.0-or-later
"""Named on-disk profiles under XDG config (not app-specific).

Default directory: ``$XDG_CONFIG_HOME/mxmaster-cfg/profiles/``
(fallback ``~/.config/mxmaster-cfg/profiles/``).

Files are YAML (``.yaml`` / ``.yml``) or JSON (``.json``). Names are the
stem of the file (filesystem-safe). Schema: ``schema/profile.schema.json``.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from mxmaster_cfg.adapter.logiops_cfg import load_profile

Format = Literal["yaml", "json"]

APP_CONFIG_DIRNAME = "mxmaster-cfg"
PROFILES_SUBDIR = "profiles"
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._()-]{0,80}$")
_UNSAFE = re.compile(r"[^\w .\-()]+", re.UNICODE)


@dataclass(frozen=True)
class ProfileEntry:
    """One named profile on disk."""

    name: str
    path: Path
    format: Format


class ProfileError(ValueError):
    """Invalid profile name, missing file, or schema failure."""


def xdg_config_home() -> Path:
    raw = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".config"


def profiles_dir() -> Path:
    return xdg_config_home() / APP_CONFIG_DIRNAME / PROFILES_SUBDIR


def ensure_profiles_dir() -> Path:
    path = profiles_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitize_profile_name(name: str) -> str:
    """Normalize a display name into a filesystem-safe stem."""
    cleaned = (name or "").strip()
    cleaned = cleaned.replace("/", "-").replace("\\", "-")
    cleaned = _UNSAFE.sub("-", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .-_")
    if not cleaned or not _SAFE_NAME.match(cleaned):
        raise ProfileError(
            f"Invalid profile name: {name!r} "
            "(use letters, digits, spaces, ._-() )"
        )
    return cleaned


def _format_of(path: Path) -> Format:
    suf = path.suffix.lower()
    if suf in {".yaml", ".yml"}:
        return "yaml"
    if suf == ".json":
        return "json"
    raise ProfileError(f"Unsupported profile suffix: {path.suffix}")


def _path_for(name: str, fmt: Format = "yaml") -> Path:
    stem = sanitize_profile_name(name)
    ext = ".yaml" if fmt == "yaml" else ".json"
    return profiles_dir() / f"{stem}{ext}"


def _existing_paths(name: str) -> list[Path]:
    stem = sanitize_profile_name(name)
    base = profiles_dir()
    found: list[Path] = []
    for ext in (".yaml", ".yml", ".json"):
        candidate = base / f"{stem}{ext}"
        if candidate.is_file():
            found.append(candidate)
    return found


def list_profiles() -> list[ProfileEntry]:
    """Return sorted profile entries (by name)."""
    base = profiles_dir()
    if not base.is_dir():
        return []
    entries: list[ProfileEntry] = []
    seen: set[str] = set()
    for path in sorted(base.iterdir()):
        if not path.is_file():
            continue
        try:
            fmt = _format_of(path)
        except ProfileError:
            continue
        name = path.stem
        if name in seen:
            continue
        seen.add(name)
        entries.append(ProfileEntry(name=name, path=path, format=fmt))
    return sorted(entries, key=lambda e: e.name.lower())


def validate_profile(data: dict[str, Any]) -> dict[str, Any]:
    """Validate against JSON Schema when jsonschema is available."""
    if not isinstance(data, dict):
        raise ProfileError("Profile root must be a mapping")
    if data.get("schema_version") != 1:
        raise ProfileError(
            f"Unsupported schema_version: {data.get('schema_version')!r} "
            "(expected 1)"
        )
    if not isinstance(data.get("device"), dict) or not data["device"].get("name"):
        raise ProfileError("Profile requires device.name")
    try:
        import jsonschema
    except ImportError:
        return data

    schema_path = (
        Path(__file__).resolve().parent / "schema" / "profile.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as exc:
        raise ProfileError(f"Schema validation failed: {exc.message}") from exc
    return data


def save_named_profile(
    name: str,
    data: dict[str, Any],
    *,
    fmt: Format = "yaml",
    overwrite: bool = True,
) -> Path:
    """Write a named profile under the XDG profiles directory."""
    ensure_profiles_dir()
    stem = sanitize_profile_name(name)
    payload = dict(data)
    payload.setdefault("schema_version", 1)
    meta = dict(payload.get("meta") or {})
    meta.setdefault("name", stem)
    payload["meta"] = meta
    validate_profile(payload)

    path = _path_for(stem, fmt)
    # Drop alternate-format duplicates so the list stays unique by stem.
    for other in _existing_paths(stem):
        if other.resolve() != path.resolve():
            if not overwrite:
                raise ProfileError(f"Profile already exists: {other.name}")
            other.unlink()
    if path.exists() and not overwrite:
        raise ProfileError(f"Profile already exists: {path.name}")

    if fmt == "yaml":
        text = yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
    else:
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")
    return path


def load_named_profile(name: str) -> dict[str, Any]:
    paths = _existing_paths(name)
    if not paths:
        raise ProfileError(f"Profile not found: {name}")
    data = load_profile(paths[0])
    return validate_profile(data)


def delete_named_profile(name: str) -> list[Path]:
    paths = _existing_paths(name)
    if not paths:
        raise ProfileError(f"Profile not found: {name}")
    removed: list[Path] = []
    for path in paths:
        path.unlink()
        removed.append(path)
    return removed


def resolve_named_path(name: str) -> Path:
    paths = _existing_paths(name)
    if not paths:
        raise ProfileError(f"Profile not found: {name}")
    return paths[0]
