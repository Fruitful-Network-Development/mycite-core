from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

_LOG = logging.getLogger("mycite.core_services.config")


def _normalize_tools_configuration(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        token = str(item.get("name") or item.get("tool_id") or item.get("id") or "").strip().lower()
        if not token:
            continue
        if token in seen:
            continue
        seen.add(token)
        normalized = dict(item)
        normalized["name"] = token
        normalized["status"] = str(item.get("status") or "enabled").strip().lower() or "enabled"
        normalized["mount_target"] = str(item.get("mount_target") or "peripherals.tools").strip().lower() or "peripherals.tools"
        normalized["anchor"] = str(item.get("anchor") or "").strip()
        out.append(normalized)
    return out


def normalize_private_config_contract(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload or {})
    # Preserve instance-authored typo while exposing canonical spelling.
    if isinstance(out.get("refferences"), list) and not isinstance(out.get("references"), list):
        out["references"] = list(out.get("refferences") or [])
    out["tools_configuration"] = _normalize_tools_configuration(out.get("tools_configuration"))
    return out


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        _LOG.warning("Failed to parse config %s: %s", path, exc)
        return None
    if not isinstance(payload, dict):
        _LOG.warning("Ignoring non-object config payload at %s", path)
        return None
    return payload


def _candidate_paths(private_dir: Path, msn_id: str | None) -> list[Path]:
    out: list[Path] = []

    # Canonical runtime config file for active portal state.
    canonical = private_dir / "config.json"
    if canonical.exists() and canonical.is_file():
        out.append(canonical)

    token = str(msn_id or "").strip()
    if token:
        out.append(private_dir / f"mycite-config-{token}.json")

    env_token = str(os.environ.get("MSN_ID") or "").strip()
    if env_token:
        out.append(private_dir / f"mycite-config-{env_token}.json")

    legacy = private_dir / "fnd-config.json"
    if legacy.exists() and legacy.is_file():
        out.append(legacy)

    out.extend(sorted(private_dir.glob("mycite-config-*.json")))

    seen: set[Path] = set()
    unique: list[Path] = []
    for path in out:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique


def resolve_active_private_config_path(private_dir: Path, msn_id: str | None = None) -> Path | None:
    for path in _candidate_paths(private_dir, msn_id):
        if not path.exists() or not path.is_file():
            continue
        payload = _read_json(path)
        if payload is None:
            continue
        return path
    return None


def active_private_config_filename(private_dir: Path, msn_id: str | None = None) -> str:
    path = resolve_active_private_config_path(private_dir, msn_id)
    if path is None:
        return ""
    return path.name


def load_active_private_config(private_dir: Path, msn_id: str | None = None) -> dict[str, Any]:
    path = resolve_active_private_config_path(private_dir, msn_id)
    if path is None:
        return {}
    payload = _read_json(path)
    if payload is None:
        return {}
    return normalize_private_config_contract(payload)
