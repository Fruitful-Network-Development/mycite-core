from __future__ import annotations

from datetime import datetime, timezone
from functools import cmp_to_key
import hashlib
import json
from pathlib import Path
from typing import Any

from MyCiteV2.packages.core.structures.hops.chronology import (
    ChronologyAuthority,
    build_chronology_authority,
    encode_utc_datetime_as_hops,
)
from MyCiteV2.packages.core.structures.hops.time_address import compare_time_addresses
from MyCiteV2.packages.core.structures.hops.time_address_schema import (
    schema_from_anchor_payload,
    validate_address_with_schema,
)
from MyCiteV2.packages.ports.network_root_read_model import (
    NetworkRootReadModelPort,
    NetworkRootReadModelRequest,
    NetworkRootReadModelResult,
    NetworkRootReadModelSource,
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_read_json(path: Path, *, warnings: list[str], label: str) -> dict[str, Any]:
    if not path.exists():
        return {}
    if not path.is_file():
        warnings.append(f"{label} is not a file: {path}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        warnings.append(f"Failed to read {label}: {path.name} ({exc})")
        return {}
    if not isinstance(payload, dict):
        warnings.append(f"{label} must contain a JSON object: {path.name}")
        return {}
    return payload


def _datum_space(payload: dict[str, Any]) -> dict[str, Any]:
    source = payload.get("datum_addressing_abstraction_space")
    if isinstance(source, dict):
        return source
    return payload if isinstance(payload, dict) else {}


def _parse_any_timestamp(value: object) -> datetime | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if number <= 0:
            return None
        if number > 10_000_000_000:
            number = number / 1000.0
        try:
            return datetime.fromtimestamp(number, tz=timezone.utc)
        except Exception:
            return None
    token = _as_text(value)
    if not token:
        return None
    if token.isdigit():
        return _parse_any_timestamp(int(token))
    try:
        if token.endswith("Z"):
            token = token[:-1] + "+00:00"
        parsed = datetime.fromisoformat(token)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _format_timestamp(value: object) -> str:
    parsed = _parse_any_timestamp(value)
    if parsed is None:
        return ""
    return parsed.isoformat().replace("+00:00", "Z")


def _iter_json_files(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    out: list[Path] = []
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            children = sorted(current.iterdir(), key=lambda item: item.name)
        except Exception:
            continue
        for child in children:
            if child.name.startswith("."):
                continue
            if child.is_dir():
                stack.append(child)
                continue
            if child.suffix.lower() == ".json":
                out.append(child)
    return sorted(out, key=lambda item: str(item))


def _iter_ndjson_files(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    out: list[Path] = []
    for child in sorted(root.iterdir(), key=lambda item: item.name):
        if child.name.startswith(".") or not child.is_file():
            continue
        if child.suffix.lower() == ".ndjson":
            out.append(child)
    return out


def _line_count(path: Path) -> int:
    if not path.exists() or not path.is_file():
        return 0
    try:
        return len(path.read_text(encoding="utf-8").splitlines())
    except Exception:
        return 0


def _normalize_surface_query(query: dict[str, str] | None) -> dict[str, str]:
    normalized = {key: _as_text(value) for key, value in dict(query or {}).items() if _as_text(key)}
    view = normalized.get("view") or "system_logs"
    if view != "system_logs":
        view = "system_logs"
    out = {"view": view}
    if normalized.get("contract"):
        out["contract"] = normalized["contract"]
    if normalized.get("type"):
        out["type"] = normalized["type"]
    if normalized.get("record"):
        out["record"] = normalized["record"]
    return out


def _json_key(value: object) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    except Exception:
        return _as_text(value)


def _make_source_key(*parts: object) -> str:
    digest = hashlib.sha1("|".join(_json_key(part) for part in parts).encode("utf-8")).hexdigest()
    return digest[:16]


def _encode_name_bits(value: object) -> str:
    text = _as_text(value)
    return "".join(f"{byte:08b}" for byte in text.encode("utf-8"))


def _event_title(event_type: str, payload: dict[str, Any]) -> str:
    for key in ("title", "label", "name"):
        token = _as_text(payload.get(key))
        if token:
            return token
    details = payload.get("details")
    if isinstance(details, dict):
        proposal = details.get("proposal")
        if isinstance(proposal, dict):
            proposal_id = _as_text(proposal.get("proposal_id"))
            if proposal_id:
                return proposal_id
        confirmation = details.get("confirmation")
        if isinstance(confirmation, dict):
            proposal_id = _as_text(confirmation.get("proposal_id"))
            if proposal_id:
                return proposal_id
    contract_id = _derive_contract_id(payload)
    if contract_id:
        return contract_id
    return event_type or "system_log_event"


def _request_log_counterparty(payload: dict[str, Any], *, local_msn_id: str) -> str:
    for key in ("counterparty_msn_id", "client_msn_id", "company_msn_id", "receiver", "transmitter"):
        token = _as_text(payload.get(key))
        if token and token != local_msn_id and token != f"msn-{local_msn_id}":
            return token.removeprefix("msn-")
    details = payload.get("details")
    if isinstance(details, dict):
        proposal = details.get("proposal")
        if isinstance(proposal, dict):
            for key in ("receiver_msn_id", "sender_msn_id"):
                token = _as_text(proposal.get(key))
                if token and token != local_msn_id:
                    return token
        confirmation = details.get("confirmation")
        if isinstance(confirmation, dict):
            for key in ("receiver_msn_id", "sender_msn_id"):
                token = _as_text(confirmation.get(key))
                if token and token != local_msn_id:
                    return token
    return ""


def _derive_contract_id(payload: dict[str, Any]) -> str:
    direct = _as_text(payload.get("contract_id"))
    if direct:
        return direct
    details = payload.get("details")
    if isinstance(details, dict):
        for key in ("proposal", "confirmation"):
            nested = details.get(key)
            if isinstance(nested, dict):
                token = _as_text(nested.get("contract_id"))
                if token:
                    return token
    return ""


def _contract_summary(payload: dict[str, Any], *, path: Path | None = None) -> dict[str, Any]:
    contract_id = _as_text(payload.get("contract_id")) or (_as_text(path.stem) if path is not None else "")
    relationship_kind = _as_text(payload.get("relationship_kind") or payload.get("contract_type")) or "unknown"
    return {
        "contract_id": contract_id,
        "relationship_kind": relationship_kind,
        "enforcement_state": _as_text(payload.get("status")) or "unknown",
        "counterparty_msn_id": _as_text(payload.get("counterparty_msn_id")),
        "owner_selected_refs": list(payload.get("owner_selected_refs") or []),
        "owner_mss": payload.get("owner_mss"),
        "counterparty_mss": payload.get("counterparty_mss"),
        "tracked_resource_ids": list(payload.get("tracked_resource_ids") or []),
        "created_unix_ms": payload.get("created_unix_ms"),
        "updated_unix_ms": payload.get("updated_unix_ms"),
        "source_path": "" if path is None else str(path),
        "raw": payload,
    }


def _read_contract_catalog(private_dir: Path | None, *, warnings: list[str]) -> dict[str, dict[str, Any]]:
    if private_dir is None:
        return {}
    contracts: dict[str, dict[str, Any]] = {}
    for path in _iter_json_files(private_dir / "contracts"):
        payload = _safe_read_json(path, warnings=warnings, label=f"contract file {path.name}")
        summary = _contract_summary(payload, path=path)
        if summary["contract_id"]:
            contracts[summary["contract_id"]] = summary
    return contracts


def _preserved_event_types(payload: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for datum_address, raw in _datum_space(payload).items():
        if not str(datum_address).startswith("4-2-"):
            continue
        labels = raw[1] if isinstance(raw, list) and len(raw) > 1 and isinstance(raw[1], list) else []
        metadata = raw[2] if isinstance(raw, list) and len(raw) > 2 and isinstance(raw[2], dict) else {}
        slug = _as_text(metadata.get("slug") or (labels[0] if labels else datum_address))
        label = _as_text(metadata.get("label") or (labels[0] if labels else slug))
        if slug and slug not in out:
            out[slug] = label or slug
    return out


def _parse_event_types(payload: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    by_local_id: dict[str, dict[str, Any]] = {}
    for datum_address, raw in _datum_space(payload).items():
        if not str(datum_address).startswith("4-2-"):
            continue
        header = raw[0] if isinstance(raw, list) and raw and isinstance(raw[0], list) else []
        labels = raw[1] if isinstance(raw, list) and len(raw) > 1 and isinstance(raw[1], list) else []
        metadata = raw[2] if isinstance(raw, list) and len(raw) > 2 and isinstance(raw[2], dict) else {}
        local_event_type_id = _as_text(metadata.get("local_event_type_id") or (header[2] if len(header) > 2 else ""))
        label = _as_text(metadata.get("label") or (labels[0] if labels else datum_address))
        slug = _as_text(metadata.get("slug") or label or datum_address)
        entry = {
            "event_type_id": _as_text(metadata.get("event_type_id") or datum_address),
            "local_event_type_id": local_event_type_id,
            "label": label or slug,
            "slug": slug or label or datum_address,
        }
        by_id[entry["event_type_id"]] = entry
        if local_event_type_id:
            by_local_id[local_event_type_id] = entry
    return by_id, by_local_id


def _parse_canonical_records(
    *,
    payload: dict[str, Any],
    schema_payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    event_types_by_id, event_types_by_local = _parse_event_types(payload)
    records: list[dict[str, Any]] = []
    for datum_address, raw in _datum_space(payload).items():
        if not str(datum_address).startswith("7-3-"):
            continue
        header = raw[0] if isinstance(raw, list) and raw and isinstance(raw[0], list) else []
        labels = raw[1] if isinstance(raw, list) and len(raw) > 1 and isinstance(raw[1], list) else []
        metadata = raw[2] if isinstance(raw, list) and len(raw) > 2 and isinstance(raw[2], dict) else {}
        event_type = event_types_by_id.get(_as_text(metadata.get("event_type_id") or (header[1] if len(header) > 1 else "")))
        if event_type is None and len(header) > 2:
            event_type = event_types_by_local.get(_as_text(header[2]))
        hops_timestamp = _as_text(metadata.get("hops_timestamp") or (header[4] if len(header) > 4 else ""))
        validation = validate_address_with_schema(hops_timestamp, schema_payload) if hops_timestamp else {"ok": False}
        chronology_state = "valid" if bool(validation.get("ok")) else "invalid"
        contract_id = _as_text(metadata.get("contract_id"))
        records.append(
            {
                "datum_address": _as_text(datum_address),
                "source_key": _as_text(metadata.get("source_key") or datum_address),
                "source_kind": _as_text(metadata.get("source_kind") or "canonical"),
                "source_timestamp": _as_text(metadata.get("source_timestamp")),
                "title": _as_text(metadata.get("title") or (labels[0] if labels else datum_address)),
                "label": _as_text(metadata.get("label") or (labels[0] if labels else datum_address)),
                "event_type_id": _as_text(event_type["event_type_id"] if event_type else metadata.get("event_type_id")),
                "event_type_label": _as_text(event_type["label"] if event_type else metadata.get("event_type_label")),
                "event_type_slug": _as_text(event_type["slug"] if event_type else metadata.get("event_type_slug")),
                "status": _as_text(metadata.get("status")),
                "counterparty": _as_text(metadata.get("counterparty")),
                "contract_id": contract_id,
                "hops_timestamp": hops_timestamp,
                "chronology_state": chronology_state,
                "raw": metadata.get("raw") if isinstance(metadata.get("raw"), dict) else metadata,
            }
        )
    preserved_types = _preserved_event_types(payload)
    return records, preserved_types


def _sort_records_desc(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def _compare(left: dict[str, Any], right: dict[str, Any]) -> int:
        hops_left = _as_text(left.get("hops_timestamp"))
        hops_right = _as_text(right.get("hops_timestamp"))
        if hops_left and hops_right:
            timestamp_cmp = compare_time_addresses(hops_left, hops_right)
            if timestamp_cmp != 0:
                return -timestamp_cmp
        title_left = _as_text(left.get("title"))
        title_right = _as_text(right.get("title"))
        if title_left < title_right:
            return -1
        if title_left > title_right:
            return 1
        key_left = _as_text(left.get("source_key"))
        key_right = _as_text(right.get("source_key"))
        if key_left < key_right:
            return -1
        if key_left > key_right:
            return 1
        return 0

    return sorted(records, key=cmp_to_key(_compare))


def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for record in records:
        key = _as_text(record.get("source_key")) or _make_source_key(
            record.get("hops_timestamp"),
            record.get("event_type_slug"),
            record.get("contract_id"),
            record.get("title"),
        )
        if key not in seen or seen[key].get("chronology_state") != "valid":
            normalized = dict(record)
            normalized["source_key"] = key
            seen[key] = normalized
    return list(seen.values())


def _load_chronology_authority(
    *,
    data_dir: Path | None,
    warnings: list[str],
) -> tuple[ChronologyAuthority | None, dict[str, Any], str]:
    if data_dir is None:
        return None, {"ok": False, "error": "data_dir not configured", "schema": {}}, ""
    anthology_path = data_dir / "system" / "anthology.json"
    anthology_payload = _safe_read_json(anthology_path, warnings=warnings, label="data/system/anthology.json")
    schema_payload = schema_from_anchor_payload(_datum_space(anthology_payload))
    if not bool(schema_payload.get("ok")):
        warnings.append(f"Chronology authority is unavailable: {schema_payload.get('error') or 'missing 1-1-1'}")
    sources_dir = data_dir / "system" / "sources"
    quadrennium_path = ""
    quadrennium_payload: dict[str, Any] = {}
    for path in sorted(sources_dir.glob("*.quadrennium_cycle.json")) if sources_dir.exists() else []:
        quadrennium_payload = _safe_read_json(path, warnings=warnings, label=path.name)
        quadrennium_path = str(path)
        if quadrennium_payload:
            break
    if not quadrennium_payload:
        warnings.append("Quadrennium chronology source is unavailable under data/system/sources.")
        return None, schema_payload, quadrennium_path
    try:
        authority = build_chronology_authority(
            schema_payload=schema_payload,
            quadrennium_payload=_datum_space(quadrennium_payload),
        )
    except Exception as exc:
        warnings.append(f"Chronology authority could not be built: {exc}")
        return None, schema_payload, quadrennium_path
    return authority, schema_payload, quadrennium_path


def _request_log_import_records(
    *,
    private_dir: Path | None,
    local_msn_id: str,
    authority: ChronologyAuthority | None,
    warnings: list[str],
) -> list[dict[str, Any]]:
    if private_dir is None:
        return []
    out: list[dict[str, Any]] = []
    for path in _iter_ndjson_files(private_dir / "network" / "request_log"):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception as exc:
            warnings.append(f"Failed to read request-log file {path.name}: {exc}")
            continue
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except Exception:
                warnings.append(f"Skipping invalid JSON line in {path.name}:{line_number}")
                continue
            if not isinstance(payload, dict):
                continue
            event_type_slug = _as_text(payload.get("type") or payload.get("event_type") or payload.get("schema")) or "unknown"
            timestamp = (
                _parse_any_timestamp(payload.get("hops_timestamp"))
                or _parse_any_timestamp(payload.get("ts_unix_ms"))
                or _parse_any_timestamp(payload.get("received_at_unix_ms"))
                or _parse_any_timestamp(payload.get("timestamp"))
                or _parse_any_timestamp(payload.get("ts"))
                or _parse_any_timestamp(payload.get("created_unix_ms"))
            )
            if timestamp is None:
                warnings.append(f"Skipping request-log entry without timestamp in {path.name}:{line_number}")
                continue
            if authority is None:
                warnings.append(f"Skipping request-log entry without chronology authority in {path.name}:{line_number}")
                continue
            existing_hops = _as_text(payload.get("hops_timestamp"))
            if existing_hops and bool(validate_address_with_schema(existing_hops, authority.schema_payload).get("ok")):
                hops_timestamp = existing_hops
            else:
                hops_timestamp = encode_utc_datetime_as_hops(timestamp, authority=authority)
            title = _event_title(event_type_slug, payload)
            out.append(
                {
                    "source_key": _make_source_key(path.name, line_number, payload),
                    "source_kind": "request_log",
                    "source_timestamp": _format_timestamp(timestamp),
                    "title": title,
                    "label": title,
                    "event_type_slug": event_type_slug,
                    "status": _as_text(payload.get("status")),
                    "counterparty": _request_log_counterparty(payload, local_msn_id=local_msn_id),
                    "contract_id": _derive_contract_id(payload),
                    "hops_timestamp": hops_timestamp,
                    "chronology_state": "valid",
                    "raw": payload,
                }
            )
    return out


def _contract_history_records(
    *,
    contracts_by_id: dict[str, dict[str, Any]],
    authority: ChronologyAuthority | None,
    warnings: list[str],
) -> list[dict[str, Any]]:
    if authority is None:
        return []
    out: list[dict[str, Any]] = []
    for contract_id, summary in contracts_by_id.items():
        raw = summary.get("raw") if isinstance(summary.get("raw"), dict) else {}
        created = _parse_any_timestamp(summary.get("created_unix_ms"))
        updated = _parse_any_timestamp(summary.get("updated_unix_ms"))
        for phase, timestamp in (("created", created), ("updated", updated)):
            if timestamp is None:
                continue
            if phase == "updated" and created is not None and int(timestamp.timestamp()) == int(created.timestamp()):
                continue
            out.append(
                {
                    "source_key": _make_source_key("contract_file", contract_id, phase, summary.get("source_path")),
                    "source_kind": "contract_file",
                    "source_timestamp": _format_timestamp(timestamp),
                    "title": contract_id,
                    "label": contract_id,
                    "event_type_slug": f"contract_record.{phase}",
                    "status": _as_text(summary.get("enforcement_state")),
                    "counterparty": _as_text(summary.get("counterparty_msn_id")),
                    "contract_id": contract_id,
                    "hops_timestamp": encode_utc_datetime_as_hops(timestamp, authority=authority),
                    "chronology_state": "valid",
                    "raw": raw,
                }
            )
    return out


def build_system_log_document(
    *,
    records: list[dict[str, Any]],
    preserved_event_types: dict[str, str] | None = None,
) -> dict[str, Any]:
    preserved = dict(preserved_event_types or {})
    for record in records:
        slug = _as_text(record.get("event_type_slug"))
        if slug and slug not in preserved:
            preserved[slug] = _as_text(record.get("event_type_label") or slug)
    event_type_entries: list[dict[str, str]] = []
    for index, slug in enumerate(sorted(preserved), start=1):
        event_type_entries.append(
            {
                "event_type_id": f"4-2-{index}",
                "local_event_type_id": str(index),
                "slug": slug,
                "label": preserved[slug],
            }
        )
    type_by_slug = {entry["slug"]: entry for entry in event_type_entries}
    space: dict[str, Any] = {}
    for entry in event_type_entries:
        space[entry["event_type_id"]] = [
            [
                entry["event_type_id"],
                "ref.2-1-10",
                entry["local_event_type_id"],
                "ref.3-1-4",
                _encode_name_bits(entry["slug"]),
            ],
            [entry["label"]],
            dict(entry),
        ]
    collection_members = ["5-0-1", "~", *[entry["event_type_id"] for entry in event_type_entries]]
    space["5-0-1"] = [collection_members, ["event_type_collection"]]
    space["6-1-1"] = [["6-1-1", "5-0-1", "0"], ["event_type_babelette"]]
    ordered_records = sorted(
        records,
        key=cmp_to_key(
            lambda left, right: (
                compare_time_addresses(_as_text(left.get("hops_timestamp")), _as_text(right.get("hops_timestamp")))
                if _as_text(left.get("hops_timestamp")) and _as_text(right.get("hops_timestamp"))
                else (
                    -1
                    if _as_text(left.get("hops_timestamp")) < _as_text(right.get("hops_timestamp"))
                    else (1 if _as_text(left.get("hops_timestamp")) > _as_text(right.get("hops_timestamp")) else 0)
                )
            )
            or (
                -1
                if _as_text(left.get("source_key")) < _as_text(right.get("source_key"))
                else (1 if _as_text(left.get("source_key")) > _as_text(right.get("source_key")) else 0)
            )
            or (
                -1
                if _as_text(left.get("title")) < _as_text(right.get("title"))
                else (1 if _as_text(left.get("title")) > _as_text(right.get("title")) else 0)
            )
        ),
    )
    for index, record in enumerate(ordered_records, start=1):
        type_entry = type_by_slug[_as_text(record.get("event_type_slug"))]
        datum_address = f"7-3-{index}"
        title = _as_text(record.get("title") or record.get("label") or datum_address)
        metadata = {
            "source_key": _as_text(record.get("source_key")),
            "source_kind": _as_text(record.get("source_kind")),
            "source_timestamp": _as_text(record.get("source_timestamp")),
            "title": title,
            "label": _as_text(record.get("label") or title),
            "event_type_id": type_entry["event_type_id"],
            "event_type_label": type_entry["label"],
            "event_type_slug": type_entry["slug"],
            "status": _as_text(record.get("status")),
            "counterparty": _as_text(record.get("counterparty")),
            "contract_id": _as_text(record.get("contract_id")),
            "hops_timestamp": _as_text(record.get("hops_timestamp")),
            "raw": record.get("raw"),
        }
        space[datum_address] = [
            [
                datum_address,
                type_entry["event_type_id"],
                type_entry["local_event_type_id"],
                "ref.3-1-1",
                metadata["hops_timestamp"],
                "ref.3-1-4",
                _encode_name_bits(title),
            ],
            [title],
            metadata,
        ]
    return {
        "anchor_file_version": "mycite.v2.network_system_log.v1",
        "generated_at_utc": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        "generated_by": "mycite.v2.network_system_log_rebuild.v1",
        "datum_addressing_abstraction_space": space,
    }


def rebuild_network_system_log_document(
    *,
    data_dir: str | Path | None,
    private_dir: str | Path | None,
    portal_tenant_id: str,
    portal_domain: str = "",
) -> dict[str, Any]:
    warnings: list[str] = []
    data_root = None if data_dir is None else Path(data_dir)
    private_root = None if private_dir is None else Path(private_dir)
    authority, schema_payload, quadrennium_path = _load_chronology_authority(data_dir=data_root, warnings=warnings)
    config = _safe_read_json(private_root / "config.json", warnings=warnings, label="private/config.json") if private_root else {}
    local_msn_id = _as_text(config.get("msn_id"))
    contracts_by_id = _read_contract_catalog(private_root, warnings=warnings)
    current_payload = _safe_read_json(
        data_root / "system" / "system_log.json",
        warnings=warnings,
        label="data/system/system_log.json",
    ) if data_root else {}
    preserved_event_types = _preserved_event_types(current_payload)
    records = _dedupe_records(
        _request_log_import_records(
            private_dir=private_root,
            local_msn_id=local_msn_id,
            authority=authority,
            warnings=warnings,
        )
        + _contract_history_records(
            contracts_by_id=contracts_by_id,
            authority=authority,
            warnings=warnings,
        )
    )
    document = build_system_log_document(records=records, preserved_event_types=preserved_event_types)
    return {
        "portal_instance": {
            "portal_instance_id": portal_tenant_id,
            "domain": portal_domain,
            "msn_id": local_msn_id,
        },
        "system_log_document": document,
        "record_count": len(records),
        "contract_count": len(contracts_by_id),
        "schema_payload": schema_payload,
        "quadrennium_path": quadrennium_path,
        "warnings": warnings,
    }


def _merge_records(
    *,
    canonical_records: list[dict[str, Any]],
    transition_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    valid_canonical = [record for record in canonical_records if _as_text(record.get("chronology_state")) == "valid"]
    return _dedupe_records(valid_canonical + transition_records)


def _record_counts(records: list[dict[str, Any]]) -> tuple[dict[str, int], dict[str, int]]:
    event_type_counts: dict[str, int] = {}
    contract_counts: dict[str, int] = {}
    for record in records:
        event_type_id = _as_text(record.get("event_type_id"))
        if event_type_id:
            event_type_counts[event_type_id] = int(event_type_counts.get(event_type_id) or 0) + 1
        contract_id = _as_text(record.get("contract_id"))
        if contract_id:
            contract_counts[contract_id] = int(contract_counts.get(contract_id) or 0) + 1
    return event_type_counts, contract_counts


class FilesystemNetworkRootReadModelAdapter(NetworkRootReadModelPort):
    def __init__(
        self,
        *,
        data_dir: str | Path | None,
        private_dir: str | Path | None,
        local_audit_file: str | Path | None = None,
    ) -> None:
        self._data_dir = None if data_dir is None else Path(data_dir)
        self._private_dir = None if private_dir is None else Path(private_dir)
        self._local_audit_file = None if local_audit_file is None else Path(local_audit_file)

    def read_network_root_model(self, request: NetworkRootReadModelRequest) -> NetworkRootReadModelResult:
        warnings: list[str] = []
        data_dir = self._data_dir
        private_dir = self._private_dir
        surface_query = _normalize_surface_query(request.surface_query)
        if data_dir is None:
            payload = {
                "portal_instance": {
                    "portal_instance_id": request.portal_tenant_id,
                    "surface_model": "one_shell_portal",
                    "runtime_flavor": "v2_native",
                    "domain": request.portal_domain,
                    "deployment_state": "runtime_only",
                    "msn_id": "",
                },
                "system_log_workbench": {
                    "state": "not_configured",
                    "document_path": "",
                    "active_filters": {
                        "view": "system_logs",
                        "contract_id": "",
                        "event_type_id": "",
                        "record_id": "",
                    },
                    "summary": {
                        "record_count": 0,
                        "event_type_count": 0,
                        "contract_count": 0,
                        "latest_hops_timestamp": "",
                    },
                    "event_type_filters": [],
                    "contract_filters": [],
                    "records": [],
                    "selected_record": None,
                    "selected_contract": None,
                    "chronology": {"state": "unavailable", "schema": {}, "quadrennium_path": ""},
                    "audit_summary": {"path": "", "state": "not_configured", "line_count": 0},
                    "warnings": ["data_dir was not configured for the network root read model."],
                },
                "warnings": ["data_dir was not configured for the network root read model."],
            }
            return NetworkRootReadModelResult(source=NetworkRootReadModelSource(payload=payload))

        authority, schema_payload, quadrennium_path = _load_chronology_authority(data_dir=data_dir, warnings=warnings)
        config = _safe_read_json(private_dir / "config.json", warnings=warnings, label="private/config.json") if private_dir else {}
        local_msn_id = _as_text(config.get("msn_id"))
        contracts_by_id = _read_contract_catalog(private_dir, warnings=warnings)
        canonical_payload = _safe_read_json(
            data_dir / "system" / "system_log.json",
            warnings=warnings,
            label="data/system/system_log.json",
        )
        canonical_records, preserved_event_types = _parse_canonical_records(
            payload=canonical_payload,
            schema_payload=schema_payload,
        )
        transition_records = _dedupe_records(
            _request_log_import_records(
                private_dir=private_dir,
                local_msn_id=local_msn_id,
                authority=authority,
                warnings=warnings,
            )
            + _contract_history_records(
                contracts_by_id=contracts_by_id,
                authority=authority,
                warnings=warnings,
            )
        )
        merged_records = _merge_records(
            canonical_records=canonical_records,
            transition_records=transition_records,
        )
        rebuilt_document = build_system_log_document(records=merged_records, preserved_event_types=preserved_event_types)
        rebuilt_records, _ = _parse_canonical_records(payload=rebuilt_document, schema_payload=schema_payload)
        records = _sort_records_desc(rebuilt_records)

        contract_id_filter = _as_text(surface_query.get("contract"))
        event_type_id_filter = _as_text(surface_query.get("type"))
        record_id_filter = _as_text(surface_query.get("record"))
        filtered_records = [
            record
            for record in records
            if (not contract_id_filter or _as_text(record.get("contract_id")) == contract_id_filter)
            and (not event_type_id_filter or _as_text(record.get("event_type_id")) == event_type_id_filter)
        ]
        selected_record = None
        for record in filtered_records:
            if _as_text(record.get("datum_address")) == record_id_filter:
                selected_record = dict(record)
                break
        if selected_record is not None:
            contract_id = _as_text(selected_record.get("contract_id"))
            if contract_id and contract_id in contracts_by_id:
                selected_record["linked_contract"] = contracts_by_id[contract_id]

        event_type_counts, contract_counts = _record_counts(records)
        event_types_by_id, _ = _parse_event_types(rebuilt_document)
        event_type_filters = [
            {
                "event_type_id": event_type_id,
                "label": _as_text(entry.get("label") or entry.get("slug") or event_type_id),
                "slug": _as_text(entry.get("slug")),
                "count": int(event_type_counts.get(event_type_id) or 0),
                "active": event_type_id == event_type_id_filter,
            }
            for event_type_id, entry in sorted(
                event_types_by_id.items(),
                key=lambda item: (_as_text(item[1].get("label")), _as_text(item[0])),
            )
        ]
        contract_filters = [
            {
                "contract_id": contract_id,
                "label": contract_id,
                "relationship_kind": _as_text(summary.get("relationship_kind")),
                "count": int(contract_counts.get(contract_id) or 0),
                "active": contract_id == contract_id_filter,
            }
            for contract_id, summary in sorted(contracts_by_id.items(), key=lambda item: item[0])
        ]

        latest_hops_timestamp = _as_text(records[0].get("hops_timestamp")) if records else ""
        chronology_state = "ready" if authority is not None and bool(schema_payload.get("ok")) else "unavailable"
        invalid_rows = len([record for record in canonical_records if _as_text(record.get("chronology_state")) != "valid"])
        if invalid_rows:
            warnings.append(
                f"Ignored {invalid_rows} invalid canonical system-log row(s) whose HOPS timestamps do not satisfy the live chronology authority."
            )
        selected_contract_id = contract_id_filter
        if not selected_contract_id and selected_record is not None:
            selected_contract_id = _as_text(selected_record.get("contract_id"))

        payload = {
            "portal_instance": {
                "portal_instance_id": request.portal_tenant_id,
                "surface_model": "one_shell_portal",
                "runtime_flavor": "v2_native",
                "domain": request.portal_domain,
                "deployment_state": "live_state_present" if data_dir.exists() else "not_configured",
                "msn_id": local_msn_id,
            },
            "system_log_workbench": {
                "state": "ready" if records else "empty",
                "document_path": str(data_dir / "system" / "system_log.json"),
                "active_filters": {
                    "view": "system_logs",
                    "contract_id": contract_id_filter,
                    "event_type_id": event_type_id_filter,
                    "record_id": record_id_filter,
                },
                "summary": {
                    "record_count": len(records),
                    "event_type_count": len(event_types_by_id),
                    "contract_count": len(contracts_by_id),
                    "latest_hops_timestamp": latest_hops_timestamp,
                },
                "event_type_filters": event_type_filters,
                "contract_filters": contract_filters,
                "records": filtered_records,
                "selected_record": selected_record,
                "selected_contract": contracts_by_id.get(selected_contract_id),
                "chronology": {
                    "state": chronology_state,
                    "schema": schema_payload.get("schema") if isinstance(schema_payload.get("schema"), dict) else {},
                    "quadrennium_path": quadrennium_path,
                },
                "audit_summary": _local_audit_summary(self._local_audit_file),
                "warnings": warnings,
            },
            "warnings": warnings,
        }
        return NetworkRootReadModelResult(source=NetworkRootReadModelSource(payload=payload))


def _local_audit_summary(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "path": "",
            "state": "not_configured",
            "line_count": 0,
        }
    if not path.exists():
        return {
            "path": str(path),
            "state": "missing_or_empty",
            "line_count": 0,
        }
    return {
        "path": str(path),
        "state": "present",
        "line_count": _line_count(path),
    }


__all__ = [
    "FilesystemNetworkRootReadModelAdapter",
    "build_system_log_document",
    "rebuild_network_system_log_document",
]
