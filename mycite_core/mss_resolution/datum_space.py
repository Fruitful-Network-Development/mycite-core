from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_anchor_path() -> Path:
    legacy = repo_root() / "anthology-base.json"
    if legacy.exists():
        return legacy
    return repo_root() / "instances" / "convention" / "data" / "system" / "anthology.json"


def source_dir(root: str | Path) -> Path:
    return Path(root) / "sources"


def anchor_datum_path(root: str | Path) -> Path:
    root_path = Path(root)
    anthology = root_path / "anthology.json"
    if anthology.exists():
        return anthology
    candidates = sorted(
        [
            path
            for path in root_path.glob("*.json")
            if path.name != "spec.json" and path.is_file()
        ],
        key=lambda item: item.name,
    )
    if candidates:
        return candidates[0]
    return anthology


def datum_origin_from_name(name: str) -> str:
    token = _as_text(name)
    if token.startswith("rf."):
        return "external"
    if token.startswith("rc."):
        return "local"
    if token.startswith("sc."):
        return "portal"
    return "anchor"


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def load_datum_file(path: str | Path) -> dict[str, Any]:
    payload = _read_json_object(Path(path))
    anthology_payload = payload.get("anthology_compatible_payload")
    if isinstance(anthology_payload, dict):
        return dict(anthology_payload)
    return dict(payload)


def _sorted_payload(payload: dict[str, Any], *, sort_key) -> dict[str, Any]:
    return {key: payload[key] for key in sorted(payload.keys(), key=lambda token: sort_key(token, token))}


@dataclass(frozen=True)
class LoadedDatumSpace:
    anchor_path: Path
    anchor_payload: dict[str, Any]
    merged_payload: dict[str, Any]
    source_payloads: dict[str, dict[str, Any]]
    source_scope_by_id: dict[str, str]
    warnings: list[str]
    ok: bool


def minimize_source_overlay(anchor_payload: dict[str, Any], source_payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in dict(source_payload or {}).items():
        if key not in anchor_payload or anchor_payload.get(key) != value:
            out[str(key)] = value
    return out


def merge_anchor_and_sources(
    anchor_payload: dict[str, Any],
    source_payloads: dict[str, dict[str, Any]],
    *,
    sort_key,
) -> LoadedDatumSpace:
    merged = dict(anchor_payload or {})
    source_scope_by_id: dict[str, str] = {str(key): "anchor" for key in merged.keys()}
    warnings: list[str] = []

    for source_name in sorted(source_payloads.keys()):
        source_payload = dict(source_payloads.get(source_name) or {})
        origin = datum_origin_from_name(source_name)
        for key, value in source_payload.items():
            merged[str(key)] = value
            source_scope_by_id[str(key)] = origin

    return LoadedDatumSpace(
        anchor_path=Path(),
        anchor_payload=_sorted_payload(dict(anchor_payload or {}), sort_key=sort_key),
        merged_payload=_sorted_payload(merged, sort_key=sort_key),
        source_payloads={name: _sorted_payload(payload, sort_key=sort_key) for name, payload in source_payloads.items()},
        source_scope_by_id=source_scope_by_id,
        warnings=warnings,
        ok=True,
    )


def load_datum_space(root: str | Path, *, sort_key) -> LoadedDatumSpace:
    root_path = Path(root)
    anchor_path = anchor_datum_path(root_path)
    anchor_payload = load_datum_file(anchor_path) if anchor_path.exists() else {}
    sources_root = source_dir(root_path)
    source_payloads: dict[str, dict[str, Any]] = {}
    if sources_root.exists() and sources_root.is_dir():
        for path in sorted(sources_root.glob("*.json"), key=lambda item: item.name):
            source_payloads[path.name] = load_datum_file(path)
    merged = merge_anchor_and_sources(anchor_payload, source_payloads, sort_key=sort_key)
    return LoadedDatumSpace(
        anchor_path=anchor_path,
        anchor_payload=merged.anchor_payload,
        merged_payload=merged.merged_payload,
        source_payloads=merged.source_payloads,
        source_scope_by_id=merged.source_scope_by_id,
        warnings=merged.warnings,
        ok=merged.ok,
    )


def load_portal_anthology_payload(overlay_path: str | Path, *, sort_key) -> LoadedDatumSpace:
    anchor_path = default_anchor_path()
    anchor_payload = load_datum_file(anchor_path)
    overlay_payload = load_datum_file(overlay_path)
    merged = merge_anchor_and_sources(anchor_payload, {Path(overlay_path).name: overlay_payload}, sort_key=sort_key)
    return LoadedDatumSpace(
        anchor_path=anchor_path,
        anchor_payload=merged.anchor_payload,
        merged_payload=merged.merged_payload,
        source_payloads=merged.source_payloads,
        source_scope_by_id=merged.source_scope_by_id,
        warnings=merged.warnings,
        ok=merged.ok,
    )
