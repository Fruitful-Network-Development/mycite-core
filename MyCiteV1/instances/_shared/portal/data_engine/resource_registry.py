from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..data_contract import compact_payload_to_rows, rows_to_compact_payload
from mycite_core.mss_resolution import compile_mss_payload, decode_mss_payload
from mycite_core.mss_resolution.storage import (
    decoded_payload_cache_path,
    ensure_payload_layout,
    payload_bin_path,
    payload_cache_root as mss_payload_cache_root,
    payloads_root as mss_payloads_root,
)
from ..samras import InvalidSamrasStructure, decode_structure
from .anthology_normalization import datum_sort_key


LOCAL_SCOPE = "resource"
INHERITED_SCOPE = "reference"
RESOURCE_SCOPE = LOCAL_SCOPE
REFERENCE_SCOPE = INHERITED_SCOPE
SCOPES = {LOCAL_SCOPE, INHERITED_SCOPE}
RESOURCE_PREFIX = "rc"
REFERENCE_PREFIX = "rf"
_BIN_RE = re.compile(r"^[01]+$")
_NUMERIC_HYPHEN_RE = re.compile(r"^[0-9]+(?:-[0-9]+)*$")
_CANONICAL_FILE_RE = re.compile(
    r"^(?P<prefix>rc|rf)\.(?P<msn>[0-9]+(?:-[0-9]+)*)\.(?P<name>[A-Za-z0-9_.-]+)\.(?P<ext>json|bin)$",
    re.IGNORECASE,
)


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _safe_token(value: object) -> str:
    token = _as_text(value).lower()
    out = []
    for ch in token:
        if ch.isalnum() or ch in {"-", "_", "."}:
            out.append(ch)
        else:
            out.append("_")
    return "".join(out).strip("._") or "resource"


def _safe_name(value: object) -> str:
    token = _safe_token(value)
    return token.replace("..", ".") or "resource"


def _normalize_scope(scope: str) -> str:
    token = _as_text(scope).lower()
    if token in {LOCAL_SCOPE, "local", "resources", "resource", RESOURCE_PREFIX}:
        return LOCAL_SCOPE
    if token in {INHERITED_SCOPE, "inherited", "references", "reference", "foreign", REFERENCE_PREFIX}:
        return INHERITED_SCOPE
    raise ValueError(f"Unsupported resource scope: {scope}")


def resources_root(data_root: Path) -> Path:
    return Path(data_root) / "resources"


def references_root(data_root: Path) -> Path:
    return Path(data_root) / "references"


def local_resources_dir(data_root: Path) -> Path:
    return resources_root(data_root) / "local"


def inherited_resources_dir(data_root: Path) -> Path:
    return references_root(data_root)


def cache_root(data_root: Path) -> Path:
    return mss_payloads_root(data_root)


def cache_scope_dir(data_root: Path, *, scope: str) -> Path:
    _normalize_scope(scope)
    return cache_root(data_root)


def payloads_root(data_root: Path) -> Path:
    return mss_payloads_root(data_root)


def payload_cache_root(data_root: Path) -> Path:
    return mss_payload_cache_root(data_root)


def ensure_layout(data_root: Path) -> None:
    local_resources_dir(data_root).mkdir(parents=True, exist_ok=True)
    references_root(data_root).mkdir(parents=True, exist_ok=True)
    ensure_payload_layout(data_root)


def _resource_data_root(path: Path) -> Path:
    current = Path(path).resolve()
    for candidate in (current, *current.parents):
        name = candidate.name.lower()
        if name in {"resources", "references"}:
            return candidate.parent
    return current.parent


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    raw_text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(raw_text)
    except Exception:
        cleaned = re.sub(r",(\s*[}\]])", r"\1", raw_text)
        try:
            payload = json.loads(cleaned)
        except Exception:
            return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _parse_canonical_filename(name: str) -> dict[str, str]:
    match = _CANONICAL_FILE_RE.fullmatch(_as_text(name))
    if match is None:
        return {"prefix": "", "msn_id": "", "name": "", "ext": ""}
    return {
        "prefix": _as_text(match.group("prefix")).lower(),
        "msn_id": _as_text(match.group("msn")),
        "name": _as_text(match.group("name")),
        "ext": _as_text(match.group("ext")).lower(),
    }


def _canonical_filename(prefix: str, msn_id: str, name: str, *, ext: str = "json") -> str:
    return f"{prefix}.{_safe_token(msn_id)}.{_safe_name(name)}.{ext}"


def build_canonical_resource_filename(local_msn_id: str, name: str) -> str:
    return _canonical_filename(RESOURCE_PREFIX, local_msn_id, _strip_resource_suffix(name), ext="json")


def build_canonical_reference_filename(source_msn_id: str, name: str) -> str:
    return _canonical_filename(REFERENCE_PREFIX, source_msn_id, _strip_resource_suffix(name), ext="json")


def _canonical_cache_name_from_json(filename: str) -> str:
    parsed = _parse_canonical_filename(filename)
    if not parsed["prefix"] or parsed["ext"] != "json":
        raise ValueError(f"Unsupported canonical datum filename: {filename}")
    return _canonical_filename(parsed["prefix"], parsed["msn_id"], parsed["name"], ext="bin")


def cache_file_path(
    data_root: Path,
    *,
    scope: str,
    resource_name: str,
    source_msn_id: str = "",
) -> Path:
    resource_path = resource_file_path(
        data_root,
        scope=scope,
        resource_name=resource_name,
        source_msn_id=source_msn_id,
    )
    parsed = _parse_canonical_filename(resource_path.name)
    return payload_bin_path(
        data_root,
        resource_path.stem,
        default_prefix=parsed["prefix"] or (RESOURCE_PREFIX if _normalize_scope(scope) == LOCAL_SCOPE else REFERENCE_PREFIX),
        source_msn_id=parsed["msn_id"] or source_msn_id,
    )


def _strip_resource_suffix(resource_name: str) -> str:
    token = _as_text(resource_name)
    parsed = _parse_canonical_filename(token)
    if parsed["name"]:
        return parsed["name"]
    if token.endswith(".json"):
        token = token[: -len(".json")]
    if token.endswith(".bin"):
        token = token[: -len(".bin")]
    for prefix in ("rec.", "ref.", "rc.", "rf."):
        if token.startswith(prefix):
            remainder = token[len(prefix) :]
            parts = remainder.split(".", 1)
            if len(parts) == 2:
                return _safe_name(parts[1])
            return _safe_name(remainder)
    return _safe_name(token)


def resource_file_path(
    data_root: Path,
    *,
    scope: str,
    resource_name: str,
    source_msn_id: str = "",
) -> Path:
    token_scope = _normalize_scope(scope)
    name = _as_text(resource_name)
    parsed = _parse_canonical_filename(name)
    if parsed["prefix"] and parsed["ext"] == "json":
        filename = _canonical_filename(parsed["prefix"], parsed["msn_id"], parsed["name"], ext="json")
    else:
        source = _safe_token(source_msn_id)
        if not source:
            raise ValueError(f"source_msn_id is required for canonical {token_scope} filenames")
        if token_scope == LOCAL_SCOPE:
            filename = build_canonical_resource_filename(source, name)
        else:
            filename = build_canonical_reference_filename(source, name)
    if token_scope == LOCAL_SCOPE:
        return local_resources_dir(data_root) / filename
    return references_root(data_root) / _safe_token(source_msn_id or parsed["msn_id"]) / filename


def _default_index(schema: str) -> dict[str, Any]:
    return {
        "schema": schema,
        "generated_unix_ms": int(time.time() * 1000),
        "resources": [],
    }


def _normalize_index_entry(entry: dict[str, Any], *, scope: str) -> dict[str, Any]:
    token_scope = _normalize_scope(scope)
    resource_name = _as_text(entry.get("resource_name"))
    parsed = _parse_canonical_filename(resource_name)
    if not resource_name and _as_text(entry.get("resource_id")).endswith(".json"):
        resource_name = _as_text(entry.get("resource_id"))
        parsed = _parse_canonical_filename(resource_name)
    source_msn_id = _as_text(entry.get("source_msn_id")) or (parsed["msn_id"] if token_scope == INHERITED_SCOPE else "")
    resource_id = _as_text(entry.get("resource_id"))
    if not resource_id and parsed["prefix"]:
        resource_id = f"{parsed['prefix']}.{parsed['msn_id']}.{parsed['name']}"
    if not resource_id and resource_name.endswith(".json"):
        resource_id = resource_name[: -len(".json")]
    return {
        "resource_id": resource_id,
        "resource_name": resource_name,
        "resource_kind": _as_text(entry.get("resource_kind")) or parsed["name"] or "resource",
        "scope": token_scope,
        "source_msn_id": source_msn_id,
        "path": _as_text(entry.get("path")),
        "version_hash": _as_text(entry.get("version_hash")),
        "updated_at": int(entry.get("updated_at") or 0),
        "status": _as_text(entry.get("status")) or "ready",
    }


def _normalize_row_iterations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, int], list[dict[str, Any]]] = {}
    passthrough: list[dict[str, Any]] = []
    for row in rows:
        identifier = _as_text(row.get("identifier") or row.get("row_id"))
        try:
            layer_s, value_group_s, _iteration_s = identifier.split("-", 2)
            layer = int(layer_s)
            value_group = int(value_group_s)
        except Exception:
            passthrough.append(dict(row))
            continue
        grouped.setdefault((layer, value_group), []).append(dict(row))

    out: list[dict[str, Any]] = []
    for (layer, value_group), members in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])):
        def _member_key(item: dict[str, Any]) -> tuple[int, str]:
            identifier = _as_text(item.get("identifier") or item.get("row_id"))
            try:
                _layer_s, _value_group_s, iteration_s = identifier.split("-", 2)
                return (int(iteration_s), identifier)
            except Exception:
                return (10**9, identifier)

        members.sort(key=_member_key)
        for index, row in enumerate(members, start=1):
            identifier = f"{layer}-{value_group}-{index}"
            row["identifier"] = identifier
            row["row_id"] = identifier
            out.append(row)
    out.extend(passthrough)
    out.sort(key=lambda item: datum_sort_key(item.get("identifier"), item.get("row_id")))
    return out


def _normalize_samras_magnitude_if_needed(reference: str, magnitude: str) -> tuple[str, str]:
    if _as_text(reference) != "0-0-5":
        return magnitude, ""
    token = _as_text(magnitude)
    if not token:
        return token, ""
    if _BIN_RE.fullmatch(token) or _NUMERIC_HYPHEN_RE.fullmatch(token):
        try:
            structure = decode_structure(token, root_ref="0-0-5")
            status = "already_canonical" if structure.source_format == "canonical" else structure.source_format
            return structure.bitstream, status
        except (InvalidSamrasStructure, ValueError):
            return token, "unsupported_legacy"
    return token, "unsupported_legacy"


def normalize_anthology_compatible_payload(raw_payload: dict[str, Any]) -> dict[str, Any]:
    rows = compact_payload_to_rows(raw_payload if isinstance(raw_payload, dict) else {}, strict=False)
    for row in rows:
        reference = _as_text(row.get("reference"))
        magnitude = _as_text(row.get("magnitude"))
        normalized, status = _normalize_samras_magnitude_if_needed(reference, magnitude)
        if status == "unsupported_legacy":
            continue
        if normalized != magnitude:
            row["magnitude"] = normalized
            pairs = row.get("pairs")
            if isinstance(pairs, list) and pairs:
                first = pairs[0] if isinstance(pairs[0], dict) else {}
                first_ref = _as_text(first.get("reference"))
                if first_ref == "0-0-5":
                    first["magnitude"] = normalized
                pairs[0] = first
                row["pairs"] = pairs
            labels = row.get("labels")
            labels_list = list(labels) if isinstance(labels, list) else []
            if "samras_canonical_binary" not in [str(item) for item in labels_list]:
                labels_list.append("samras_canonical_binary")
            row["labels"] = labels_list
    normalized_rows = _normalize_row_iterations(rows)
    return rows_to_compact_payload(normalized_rows)


def compute_version_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload if isinstance(payload, dict) else {}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def read_resource_file(path: Path) -> dict[str, Any]:
    return _read_json(path)


def _looks_like_compact_payload(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict) or not payload:
        return False
    rows = payload.get("rows")
    if isinstance(rows, dict):
        return True
    return any(re.fullmatch(r"[0-9]+-[0-9]+-[0-9]+", str(key or "").strip()) for key in payload.keys())


def _compact_payload_from_resource_body(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    candidate = payload.get("anthology_compatible_payload")
    if isinstance(candidate, dict) and candidate:
        return normalize_anthology_compatible_payload(candidate)
    if _looks_like_compact_payload(payload):
        return normalize_anthology_compatible_payload(payload)
    return {}


def _selected_refs_for_payload(compact_payload: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for row in compact_payload_to_rows(compact_payload, strict=False):
        identifier = _as_text(row.get("identifier") or row.get("row_id"))
        if not identifier or identifier in seen:
            continue
        seen.add(identifier)
        refs.append(identifier)
    return refs


def _extract_bitstring(payload: dict[str, Any], *, source_msn_id: str) -> str:
    if not isinstance(payload, dict):
        return ""
    mss_form = payload.get("mss_form") if isinstance(payload.get("mss_form"), dict) else {}
    published_value = payload.get("published_value") if isinstance(payload.get("published_value"), dict) else {}
    compile_metadata = payload.get("compile_metadata") if isinstance(payload.get("compile_metadata"), dict) else {}
    legacy_bits = payload.get("mss_bit_string_array")
    candidates = [
        _as_text(mss_form.get("bitstring")),
        _as_text(published_value.get("mss_form_bitstring")),
        _as_text(compile_metadata.get("mss_form_bitstring")),
    ]
    if isinstance(legacy_bits, list) and legacy_bits:
        candidates.append(_as_text(legacy_bits[0]))
    for token in candidates:
        if _BIN_RE.fullmatch(token):
            return token
    compact_payload = _compact_payload_from_resource_body(payload)
    selected_refs = _selected_refs_for_payload(compact_payload)
    if compact_payload and selected_refs:
        try:
            compiled = compile_mss_payload(
                compact_payload,
                selected_refs,
                local_msn_id=_as_text(source_msn_id),
                include_selection_root=True,
            )
            bitstring = _as_text(compiled.get("bitstring"))
            if _BIN_RE.fullmatch(bitstring):
                return bitstring
        except Exception:
            pass
    if compact_payload:
        for row in compact_payload_to_rows(compact_payload, strict=False):
            magnitude = _as_text(row.get("magnitude"))
            if _BIN_RE.fullmatch(magnitude):
                return magnitude
            pairs = row.get("pairs") if isinstance(row.get("pairs"), list) else []
            for item in pairs:
                if not isinstance(item, dict):
                    continue
                pair_magnitude = _as_text(item.get("magnitude"))
                if _BIN_RE.fullmatch(pair_magnitude):
                    return pair_magnitude
    return ""


def _materialize_cache_for_path(path: Path, payload: dict[str, Any]) -> str:
    parsed = _parse_canonical_filename(path.name)
    if not parsed["prefix"] or parsed["ext"] != "json":
        return ""
    data_root = _resource_data_root(path)
    bitstring = _extract_bitstring(payload, source_msn_id=parsed["msn_id"])
    cache_path = payload_bin_path(
        data_root,
        path.stem,
        default_prefix=parsed["prefix"],
        source_msn_id=parsed["msn_id"],
    )
    decoded_cache_path = decoded_payload_cache_path(
        data_root,
        path.stem,
        default_prefix=parsed["prefix"],
        source_msn_id=parsed["msn_id"],
    )
    if not bitstring:
        try:
            cache_path.unlink()
        except FileNotFoundError:
            pass
        try:
            decoded_cache_path.unlink()
        except FileNotFoundError:
            pass
        return ""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(bitstring, encoding="utf-8")
    try:
        decoded_payload = decode_mss_payload(bitstring)
    except Exception:
        decoded_payload = {}
    if decoded_payload:
        decoded_cache_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(decoded_cache_path, decoded_payload)
    else:
        try:
            decoded_cache_path.unlink()
        except FileNotFoundError:
            pass
    return str(cache_path)


def write_resource_file(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    body = dict(payload if isinstance(payload, dict) else {})
    if _looks_like_compact_payload(body) and "schema" not in body and "resource_id" not in body:
        compact_payload = normalize_anthology_compatible_payload(body)
        _write_json(path, compact_payload)
        _materialize_cache_for_path(path, compact_payload)
        return compact_payload
    anthology_payload = body.get("anthology_compatible_payload")
    if isinstance(anthology_payload, dict):
        body["anthology_compatible_payload"] = normalize_anthology_compatible_payload(anthology_payload)
    body["updated_at"] = int(body.get("updated_at") or time.time() * 1000)
    body["version_hash"] = _as_text(body.get("version_hash")) or compute_version_hash(
        body.get("anthology_compatible_payload") if isinstance(body.get("anthology_compatible_payload"), dict) else body
    )
    _write_json(path, body)
    _materialize_cache_for_path(path, body)
    return body


def _entry_from_file(path: Path, *, scope: str) -> dict[str, Any]:
    payload = read_resource_file(path)
    parsed = _parse_canonical_filename(path.name)
    compact_payload = _compact_payload_from_resource_body(payload)
    version_hash = _as_text(payload.get("version_hash"))
    if not version_hash:
        if compact_payload:
            version_hash = compute_version_hash(compact_payload)
        else:
            version_hash = compute_version_hash(payload)
    resource_kind = _as_text(payload.get("resource_kind") or payload.get("kind") or parsed["name"] or "resource")
    updated_at = int(payload.get("updated_at") or int(path.stat().st_mtime * 1000))
    source_msn_id = _as_text(payload.get("source_msn_id"))
    if _normalize_scope(scope) == INHERITED_SCOPE and not source_msn_id:
        source_msn_id = parsed["msn_id"]
    return _normalize_index_entry(
        {
            "resource_id": _as_text(payload.get("resource_id")) or path.stem,
            "resource_name": path.name,
            "resource_kind": resource_kind,
            "scope": scope,
            "source_msn_id": source_msn_id,
            "path": str(path),
            "version_hash": version_hash,
            "updated_at": updated_at,
            "status": _as_text(payload.get("status")) or "ready",
        },
        scope=scope,
    )


def _legacy_root_entry(path: Path, *, scope: str) -> dict[str, Any]:
    payload = read_resource_file(path)
    version_hash = _as_text(payload.get("version_hash")) or compute_version_hash(payload)
    parsed = _parse_canonical_filename(path.name)
    return _normalize_index_entry(
        {
            "resource_id": _as_text(payload.get("resource_id")) or path.stem,
            "resource_name": path.name,
            "resource_kind": _as_text(payload.get("resource_kind") or payload.get("kind") or parsed["name"] or "resource"),
            "scope": scope,
            "source_msn_id": _as_text(payload.get("source_msn_id")) or parsed["msn_id"],
            "path": str(path),
            "version_hash": version_hash,
            "updated_at": int(payload.get("updated_at") or int(path.stat().st_mtime * 1000)),
            "status": "legacy_root",
        },
        scope=scope,
    )


def load_index(data_root: Path, *, scope: str) -> dict[str, Any]:
    ensure_layout(data_root)
    token_scope = _normalize_scope(scope)
    payload = _default_index(
        "mycite.portal.resources.index.local.v1"
        if token_scope == LOCAL_SCOPE
        else "mycite.portal.references.index.inherited.v1"
    )
    resources: list[dict[str, Any]] = []
    canonical_paths: list[Path] = []
    legacy_paths: list[Path] = []
    if token_scope == LOCAL_SCOPE:
        canonical_paths.extend(sorted(local_resources_dir(data_root).glob("*.json"), key=lambda item: item.name))
        legacy_paths.extend(sorted(resources_root(data_root).glob("*.json"), key=lambda item: item.name))
    else:
        for directory in sorted(references_root(data_root).iterdir(), key=lambda item: item.name.lower()) if references_root(data_root).exists() else []:
            if directory.is_dir():
                canonical_paths.extend(sorted(directory.glob("*.json"), key=lambda item: (directory.name, item.name)))
        legacy_paths.extend(sorted(references_root(data_root).glob("*.json"), key=lambda item: item.name))
    for path in canonical_paths:
        resources.append(_entry_from_file(path, scope=token_scope))
    for path in legacy_paths:
        resources.append(_legacy_root_entry(path, scope=token_scope))
    resources.sort(
        key=lambda item: (
            1 if _as_text(item.get("status")) == "legacy_root" else 0,
            _as_text(item.get("source_msn_id")),
            _as_text(item.get("resource_name")),
            _as_text(item.get("resource_id")),
        )
    )
    payload["resources"] = resources
    payload["catalog_mode"] = "filesystem_enumeration"
    payload["compatibility"] = {
        "legacy_root_mode": "read_only_compat",
        "migration_recommended": bool(legacy_paths),
    }
    return payload


def save_index(data_root: Path, *, scope: str, payload: dict[str, Any]) -> dict[str, Any]:
    token_scope = _normalize_scope(scope)
    resources = payload.get("resources") if isinstance(payload.get("resources"), list) else []
    normalized = [_normalize_index_entry(item, scope=token_scope) for item in resources if isinstance(item, dict)]
    normalized.sort(
        key=lambda item: (
            _as_text(item.get("source_msn_id")),
            _as_text(item.get("resource_name")),
            _as_text(item.get("resource_id")),
        )
    )
    out = _default_index(
        "mycite.portal.resources.index.local.v1"
        if token_scope == LOCAL_SCOPE
        else "mycite.portal.references.index.inherited.v1"
    )
    out["resources"] = normalized
    out["catalog_mode"] = "filesystem_enumeration"
    out["compatibility"] = {
        "legacy_root_mode": "read_only_compat",
        "migration_recommended": False,
    }
    return out


def upsert_index_entry(
    data_root: Path,
    *,
    scope: str,
    entry: dict[str, Any],
) -> dict[str, Any]:
    ensure_layout(data_root)
    return _normalize_index_entry(entry, scope=scope)


def remove_inherited_source(data_root: Path, *, source_msn_id: str) -> dict[str, Any]:
    ensure_layout(data_root)
    token = _safe_token(source_msn_id)
    removed_count = 0
    for root in (references_root(data_root), payloads_root(data_root), payload_cache_root(data_root)):
        for path in sorted(root.glob(f"**/rf.{token}.*")):
            try:
                path.unlink()
                removed_count += 1
            except Exception:
                continue
        for path in sorted(root.glob(f"**/ref.{token}.*")):
            try:
                path.unlink()
                removed_count += 1
            except Exception:
                continue
    return {"removed_count": removed_count, "source_msn_id": token}


@dataclass(frozen=True)
class LegacySamrasMigrationReport:
    ok: bool
    migrated: list[dict[str, Any]]
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "migrated": [dict(item) for item in self.migrated],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


def _infer_local_msn_id(data_root: Path) -> str:
    candidates = []
    for pattern in ("rc.*.json", "rec.*.json"):
        candidates.extend(sorted(resources_root(data_root).glob(pattern)))
        candidates.extend(sorted(local_resources_dir(data_root).glob(pattern)))
    for path in candidates:
        match = re.match(r"^(?:rc|rec)\.(?P<msn>[0-9]+(?:-[0-9]+)*)\.", path.name)
        if match is not None:
            return _as_text(match.group("msn"))
    return ""


def migrate_legacy_samras_root_files(
    data_root: Path,
    *,
    local_msn_id: str = "",
    apply_changes: bool = True,
) -> LegacySamrasMigrationReport:
    ensure_layout(data_root)
    targets = [
        (["samras-msn.json", "samras-msn.legacy.json"], "msn"),
        (["samras-txa.json", "samras-txa.legacy.json"], "txa"),
    ]
    migrated: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []
    msn_id = _as_text(local_msn_id) or _infer_local_msn_id(data_root)
    if not msn_id:
        errors.append("unable to infer local_msn_id for legacy samras migration")
        return LegacySamrasMigrationReport(ok=False, migrated=[], warnings=warnings, errors=errors)

    for legacy_candidates, canonical_name in targets:
        legacy_path = None
        for candidate in legacy_candidates:
            candidate_path = Path(data_root) / candidate
            if candidate_path.exists() and candidate_path.is_file():
                legacy_path = candidate_path
                break
        if legacy_path is None:
            continue
        raw_payload = _read_json(legacy_path)
        if not raw_payload:
            warnings.append(f"legacy file empty: {legacy_path.name}")
            raw_payload = {}
        normalized_payload = normalize_anthology_compatible_payload(raw_payload)
        target_path = resource_file_path(
            data_root,
            scope=LOCAL_SCOPE,
            source_msn_id=msn_id,
            resource_name=canonical_name,
        )
        if apply_changes:
            _write_json(target_path, normalized_payload)
            _materialize_cache_for_path(target_path, normalized_payload)
        migrated.append(
            {
                "legacy_path": str(legacy_path),
                "resource_path": str(target_path),
                "resource_id": target_path.stem,
                "resource_name": target_path.name,
                "version_hash": compute_version_hash(normalized_payload),
            }
        )

    return LegacySamrasMigrationReport(ok=not errors, migrated=migrated, warnings=warnings, errors=errors)


def migrate_legacy_root_rec_files(
    data_root: Path,
    *,
    local_msn_id: str = "",
    apply_changes: bool = True,
) -> dict[str, Any]:
    ensure_layout(data_root)
    migrated: list[dict[str, Any]] = []
    msn_id = _as_text(local_msn_id) or _infer_local_msn_id(data_root)
    for root in (resources_root(data_root), local_resources_dir(data_root)):
        if not root.exists():
            continue
        for path in sorted(root.glob("rec.*.json")):
            if path.parent == local_resources_dir(data_root):
                continue
            payload = _read_json(path)
            match = re.match(r"^rec\.(?P<msn>[0-9]+(?:-[0-9]+)*)\.(?P<name>.+)\.json$", path.name)
            token_msn = _as_text(match.group("msn")) if match is not None else msn_id
            _token_name = _as_text(match.group("name")) if match is not None else _strip_resource_suffix(path.name)
            target = local_resources_dir(data_root) / path.name
            if apply_changes:
                _write_json(target, payload)
                _materialize_cache_for_path(target, payload)
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
            migrated.append({"legacy_path": str(path), "resource_path": str(target), "resource_id": target.stem})
    return {"ok": True, "migrated": migrated, "count": len(migrated)}
