from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

_LOG = logging.getLogger("mycite.core_services.config")


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


def load_active_private_config(private_dir: Path, msn_id: str | None = None) -> dict[str, Any]:
    for path in _candidate_paths(private_dir, msn_id):
        if not path.exists() or not path.is_file():
            continue
        payload = _read_json(path)
        if payload is None:
            continue
        return payload
    return {}
