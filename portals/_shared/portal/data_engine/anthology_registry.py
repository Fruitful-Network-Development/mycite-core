from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .anthology_schema import NormalizedDatum, normalize_compact_row, sort_key


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def default_base_registry_path() -> Path:
    # .../repo/mycite-core/portals/_shared/portal/data_engine/anthology_registry.py
    # parents[4] => /srv/repo/mycite-core
    return Path(__file__).resolve().parents[4] / "anthology-base.json"


def load_compact_payload(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


@dataclass(frozen=True)
class BaseRegistry:
    path: str
    compact_payload: dict[str, Any]
    normalized: dict[str, NormalizedDatum]
    warnings: list[str]

    @property
    def reserved_ids(self) -> set[str]:
        return set(self.normalized.keys())


def load_base_registry(
    *,
    base_path: Path | None = None,
    strict: bool = False,
) -> BaseRegistry:
    path = Path(base_path) if isinstance(base_path, Path) else default_base_registry_path()
    payload = load_compact_payload(path)
    normalized: dict[str, NormalizedDatum] = {}
    warnings: list[str] = []
    for row_id, raw in payload.items():
        datum, row_warnings = normalize_compact_row(str(row_id), raw, source_scope="base", strict=strict)
        warnings.extend(list(row_warnings or []))
        if datum is None:
            continue
        normalized[datum.datum_id] = datum
    ordered_payload = {
        key: payload[key]
        for key in sorted(payload.keys(), key=lambda token: sort_key(token, token))
        if key in payload
    }
    return BaseRegistry(
        path=str(path),
        compact_payload=ordered_payload,
        normalized=normalized,
        warnings=warnings,
    )


def validate_registry_collisions(base_registry: BaseRegistry, overlay_payload: dict[str, Any]) -> list[str]:
    collisions: list[str] = []
    if not isinstance(overlay_payload, dict):
        return collisions
    for row_id, raw in overlay_payload.items():
        token = _as_text(row_id)
        if token not in base_registry.compact_payload:
            continue
        if base_registry.compact_payload.get(token) == raw:
            continue
        collisions.append(f"overlay collision on reserved base id: {token}")
    return collisions
