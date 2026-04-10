from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

_LOG = logging.getLogger("mycite.core_services.config")
_CONTRACT_FILE_RE = re.compile(
    r"^(?:contract\.(?P<left>[0-9-]+)\.(?P<right>[0-9-]+)|contract-(?P<contract_id>[A-Za-z0-9._:-]+))\.json$",
    re.IGNORECASE,
)
_REFERENCE_FILE_RE = re.compile(
    r"^(?P<prefix>rf|ref)\.(?P<source>[A-Za-z0-9._:-]+)\.(?P<name>[A-Za-z0-9_.-]+)\.(?P<ext>json|bin)$",
    re.IGNORECASE,
)


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


def _reference_file_parts(token: str) -> tuple[str, str]:
    match = _REFERENCE_FILE_RE.fullmatch(str(token or "").strip())
    if not match:
        return ("", "")
    return (str(match.group("source") or "").strip(), str(match.group("name") or "").strip())


def _reference_file_payload(token: str) -> dict[str, str]:
    match = _REFERENCE_FILE_RE.fullmatch(str(token or "").strip())
    if not match:
        return {"prefix": "", "source": "", "name": "", "ext": ""}
    return {
        "prefix": str(match.group("prefix") or "").strip().lower(),
        "source": str(match.group("source") or "").strip(),
        "name": str(match.group("name") or "").strip(),
        "ext": str(match.group("ext") or "").strip().lower(),
    }


def _infer_reference_source_msn(item: dict[str, Any], *, local_msn_id: str) -> str:
    explicit = str(item.get("source_msn_id") or "").strip()
    if explicit:
        return explicit
    contract = str(item.get("managing_contract") or "").strip()
    contract_name = Path(contract).name
    match = _CONTRACT_FILE_RE.fullmatch(contract_name)
    if match:
        left = str(match.group("left") or "").strip()
        right = str(match.group("right") or "").strip()
        if left and right:
            if local_msn_id and left == local_msn_id:
                return right
            if local_msn_id and right == local_msn_id:
                return left
    title_source, _ = _reference_file_parts(str(item.get("title") or ""))
    form_source, _ = _reference_file_parts(str(item.get("mss_form") or ""))
    if title_source and (not local_msn_id or title_source != local_msn_id):
        return title_source
    if form_source and (not local_msn_id or form_source != local_msn_id):
        return form_source
    return title_source or form_source


def _normalize_reference_entries(raw: Any, *, local_msn_id: str) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        title_source, title_name = _reference_file_parts(str(item.get("title") or ""))
        form_source, form_name = _reference_file_parts(str(item.get("mss_form") or ""))
        name = str(item.get("name") or form_name or title_name).strip().lower()
        if not name:
            _LOG.warning("Ignoring malformed reference without name: %s", item)
            continue
        source_msn_id = _infer_reference_source_msn(item, local_msn_id=local_msn_id)
        source_msn_id = str(source_msn_id or form_source or title_source).strip()
        if not source_msn_id:
            _LOG.warning("Ignoring malformed reference without source_msn_id: %s", item)
            continue
        if local_msn_id and source_msn_id == local_msn_id:
            fallback = form_source or title_source
            if fallback and fallback != local_msn_id:
                source_msn_id = fallback
        marker = (source_msn_id, name)
        if marker in seen:
            continue
        seen.add(marker)
        canonical_mss_form = f"rf.{source_msn_id}.{name}.bin"
        normalized = dict(item)
        normalized["name"] = name
        normalized["source_msn_id"] = source_msn_id
        normalized["title"] = f"rf.{source_msn_id}.{name}"
        normalized["mss_form"] = canonical_mss_form
        legacy_mss_form = str(item.get("mss_form") or "").strip()
        legacy_title = str(item.get("title") or "").strip()
        if legacy_title and legacy_title != normalized["title"]:
            normalized["legacy_title"] = legacy_title
        if legacy_mss_form and legacy_mss_form != canonical_mss_form:
            normalized["legacy_mss_form"] = legacy_mss_form
        legacy_payload = _reference_file_payload(legacy_mss_form)
        if legacy_payload["prefix"] == "ref" or legacy_payload["ext"] == "json":
            normalized["compatibility_warning"] = "legacy reference form normalized to canonical rf.<source>.<name>.bin"
        out.append(normalized)
    return out


def normalize_private_config_contract(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload or {})
    local_msn_id = str(out.get("msn_id") or "").strip()
    references_raw = out.get("references")
    if not isinstance(references_raw, list):
        references_raw = out.get("refferences")
    out["references"] = _normalize_reference_entries(references_raw, local_msn_id=local_msn_id)
    out.pop("refferences", None)
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
