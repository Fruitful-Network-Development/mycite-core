from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NOTES_DIR = REPO_ROOT / "docs" / "personal_notes" / "CTS-GIS-prototype-mockup"
DEFAULT_DATA_ROOTS = [
    REPO_ROOT / "deployed" / "fnd" / "data",
    Path("/srv/mycite-state/instances/fnd/data"),
]
COUNTY_NODE_ID = "3-2-3-17-77"
COUNTY_ROOT_PREFIX = f"{COUNTY_NODE_ID}-"
ANCHOR_NAME = "tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json"
ADMIN_NAME = "sc.3-2-3-17-77-1-6-4-1-4.msn-administrative.json"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _address_sort_key(token: str) -> tuple[tuple[int, ...], str]:
    parts = str(token or "").split("-")
    if all(part.isdigit() for part in parts):
        return tuple(int(part) for part in parts), str(token)
    return (10**9,), str(token)


def _text_bits(value: str) -> str:
    return "".join(f"{byte:08b}" for byte in value.encode("utf-8"))


def _decode_text_bits(value: str) -> str:
    token = str(value or "").strip()
    if not token or any(ch not in {"0", "1"} for ch in token) or (len(token) % 8) != 0:
        return ""
    data = bytearray(int(token[index : index + 8], 2) for index in range(0, len(token), 8))
    while data and data[-1] == 0:
        data.pop()
    if not data:
        return ""
    try:
        return bytes(data).decode("utf-8").strip()
    except UnicodeDecodeError:
        return ""


def _normalize_name(value: str) -> str:
    lowered = value.lower().replace("_", " ").replace("-", " ")
    cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in lowered)
    tokens = [token for token in cleaned.split() if token]
    stopwords = {"city", "village", "township", "county", "of"}
    return " ".join(token for token in tokens if token not in stopwords)


def _primary_samras_node_id(space: dict[str, Any]) -> str:
    row = space.get("7-3-1")
    if not isinstance(row, list) or not row or not isinstance(row[0], list):
        return ""
    head = row[0]
    for index, token in enumerate(head[:-1]):
        if token == "rf.3-1-2":
            value = str(head[index + 1] or "").strip()
            if value:
                return value
    return ""


def _primary_label(space: dict[str, Any]) -> str:
    row = space.get("7-3-1")
    if not isinstance(row, list) or len(row) < 2 or not isinstance(row[1], list):
        return ""
    return str(row[1][0] or "").strip() if row[1] else ""


def _reference_geojson_lookup(notes_dir: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    lookup: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []

    county_path = notes_dir / "3-2-3-17-77.geojson"
    if county_path.exists():
        lookup[f"{_normalize_name('summit')}:county"] = {
            "node_id": COUNTY_NODE_ID,
            "path": county_path,
            "payload": _read_json(county_path),
        }
    else:
        warnings.append(f"Missing county reference GeoJSON: {county_path}")

    state_path = notes_dir / "3-2-3-17.geojson"
    if state_path.exists():
        warnings.append(
            "Reference GeoJSON 3-2-3-17.geojson is present, but no matching CTS-GIS source document exists under sandbox/cts-gis/sources."
        )

    community_dir = notes_dir / "Summit-County-Communities"
    if not community_dir.exists():
        warnings.append(f"Missing community reference directory: {community_dir}")
        return lookup, warnings

    for path in sorted(community_dir.glob("*.geojson")):
        payload = _read_json(path)
        feature = next(iter(payload.get("features") or []), {})
        properties = dict(feature.get("properties") or {})
        community_type = str(properties.get("community_type") or "").strip().lower()
        name_candidates = [
            str(properties.get("source_query_name") or "").strip(),
            str(properties.get("municipality") or "").strip(),
            str(properties.get("twp_name") or "").strip(),
            str(properties.get("community_name") or "").strip(),
            path.stem,
        ]
        base_name = next((_normalize_name(candidate) for candidate in name_candidates if _normalize_name(candidate)), "")
        if not base_name or not community_type:
            warnings.append(f"Could not infer reference key for {path}")
            continue
        lookup[f"{base_name}:{community_type}"] = {
            "node_id": "",
            "path": path,
            "payload": payload,
        }
    return lookup, warnings


def _reference_key_for_source(node_id: str, label: str) -> str:
    if node_id == COUNTY_NODE_ID:
        return f"{_normalize_name('summit')}:county"
    normalized_label = _normalize_name(label)
    if label.endswith("_city"):
        return f"{normalized_label}:city"
    if label.endswith("_township"):
        return f"{normalized_label}:township"
    if label.endswith("_village"):
        return f"{normalized_label}:village"
    return ""


def _rebuild_anchor_source_rows(anchor_payload: dict[str, Any], source_dir: Path) -> dict[str, Any]:
    source_files = sorted(path.name for path in source_dir.glob("*.json"))
    rebuilt: dict[str, Any] = {}
    for address, row in sorted(anchor_payload.items(), key=lambda item: _address_sort_key(item[0])):
        if not address.startswith("1-0-"):
            rebuilt[address] = row
    for index, source_name in enumerate(source_files, start=1):
        rebuilt[f"1-0-{index}"] = [[f"1-0-{index}", "~", "0-0-11"], [source_name]]
    return dict(sorted(rebuilt.items(), key=lambda item: _address_sort_key(item[0])))


def _replace_title_here_tokens(space: dict[str, Any]) -> int:
    replacements = 0
    for row in space.values():
        if not isinstance(row, list) or len(row) < 2 or not isinstance(row[0], list) or not isinstance(row[1], list):
            continue
        head = row[0]
        labels = row[1]
        title_bits = _text_bits(str(labels[0] or "").strip()) if labels else ""
        if not title_bits:
            continue
        for index, token in enumerate(head[:-1]):
            if token == "rf.3-1-3" and str(head[index + 1]).strip() == "HERE":
                head[index + 1] = title_bits
                replacements += 1
    return replacements


def _replace_first_samras_binding(row: list[Any], node_id: str) -> bool:
    if not isinstance(row, list) or not row or not isinstance(row[0], list):
        return False
    head = row[0]
    for index, token in enumerate(head[:-1]):
        if token == "rf.3-1-2":
            head[index + 1] = node_id
            return True
    return False


def _repair_admin_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    space = dict(payload.get("datum_addressing_abstraction_space") or {})
    stats = {
        "title_placeholders_repaired": 0,
        "summit_admin_rows_regenerated": 0,
        "reminderville_rebound": 0,
        "boston_heights_renamed": 0,
        "adm2_typo_fixed": 0,
        "adm3_collection_fixed": 0,
        "collection_chain_fixed": 0,
    }

    boston_renames = {
        "4-2-213": "boston_heights_village",
        "4-2-216": "village_of_boston_heights",
    }
    for address, label in boston_renames.items():
        row = space.get(address)
        if isinstance(row, list) and len(row) >= 2 and isinstance(row[1], list):
            if not row[1] or row[1][0] != label:
                row[1] = [label]
                stats["boston_heights_renamed"] += 1

    reminderville_bindings = {
        "4-2-245": "3-2-3-17-77-3-9",
        "4-2-246": "3-2-3-17-77-3-9-1",
        "4-2-247": "3-2-3-17-77-3-9-1-1",
        "4-2-248": "3-2-3-17-77-3-9-1-1-1",
    }
    for address, node_id in reminderville_bindings.items():
        row = space.get(address)
        if row is not None and _replace_first_samras_binding(row, node_id):
            stats["reminderville_rebound"] += 1

    ohio_adm2 = space.get("5-0-3")
    if isinstance(ohio_adm2, list) and ohio_adm2 and isinstance(ohio_adm2[0], list):
        head = ohio_adm2[0]
        changed = False
        for index, token in enumerate(head):
            if token == "4-2-10":
                head[index] = "4-2-106"
                changed = True
        if changed:
            stats["adm2_typo_fixed"] += 1

    summit_admin3_rows: list[str] = []
    for address, row in sorted(space.items(), key=lambda item: _address_sort_key(item[0])):
        if not address.startswith("4-2-"):
            continue
        if not isinstance(row, list) or not row or not isinstance(row[0], list):
            continue
        head = row[0]
        first_samras = ""
        for index, token in enumerate(head[:-1]):
            if token == "rf.3-1-2":
                first_samras = str(head[index + 1] or "").strip()
                break
        if first_samras.startswith(f"{COUNTY_ROOT_PREFIX}1") or first_samras.startswith(f"{COUNTY_ROOT_PREFIX}2") or first_samras.startswith(f"{COUNTY_ROOT_PREFIX}3"):
            summit_admin3_rows.append(address)
    if summit_admin3_rows:
        space["5-0-4"] = [["5-0-4", "~", *summit_admin3_rows], ["ohio_summit_county_adm3"]]
        stats["summit_admin_rows_regenerated"] = len(summit_admin3_rows)
        stats["adm3_collection_fixed"] = 1

    admin_collection = space.get("6-0-1")
    if isinstance(admin_collection, list) and admin_collection and isinstance(admin_collection[0], list):
        head = [token for token in admin_collection[0] if token not in {"5-0-1", "5-0-2", "5-0-3", "5-0-4"}]
        admin_collection[0] = [head[0], head[1], "5-0-1", "5-0-2", "5-0-3", "5-0-4"]
        stats["collection_chain_fixed"] = 1

    stats["title_placeholders_repaired"] = _replace_title_here_tokens(space)

    repaired = dict(payload)
    repaired["datum_addressing_abstraction_space"] = space
    return repaired, stats


def _audit_admin_payload(payload: dict[str, Any]) -> dict[str, Any]:
    space = dict(payload.get("datum_addressing_abstraction_space") or {})
    bindings_by_node: dict[str, list[str]] = {}
    blank_title_nodes: list[str] = []
    missing_title_rows: list[str] = []
    for address, row in sorted(space.items(), key=lambda item: _address_sort_key(item[0])):
        if not address.startswith("4-2-"):
            continue
        if not isinstance(row, list) or len(row) < 2 or not isinstance(row[0], list):
            continue
        head = row[0]
        node_id = ""
        title_bits = ""
        for index, token in enumerate(head[:-1]):
            if token == "rf.3-1-2":
                node_id = str(head[index + 1] or "").strip()
            if token == "rf.3-1-3":
                title_bits = str(head[index + 1] or "").strip()
        if node_id:
            bindings_by_node.setdefault(node_id, []).append(address)
        if title_bits:
            if not _decode_text_bits(title_bits):
                blank_title_nodes.append(node_id or address)
        else:
            missing_title_rows.append(address)
    duplicate_node_ids = sorted(
        [node_id for node_id, addresses in bindings_by_node.items() if len(addresses) > 1],
        key=_address_sort_key,
    )
    return {
        "duplicate_node_ids": duplicate_node_ids,
        "blank_title_nodes": sorted(blank_title_nodes, key=_address_sort_key),
        "missing_title_rows": sorted(missing_title_rows, key=_address_sort_key),
    }


def _audit_source_profile_document(space: dict[str, Any]) -> dict[str, bool]:
    row = space.get("7-3-1")
    if not isinstance(row, list) or not row or not isinstance(row[0], list):
        return {
            "missing_primary_samras_node": True,
            "missing_primary_title_binding": True,
        }
    head = row[0]
    has_samras = False
    has_title = False
    for index, token in enumerate(head[:-1]):
        if token == "rf.3-1-2" and str(head[index + 1] or "").strip():
            has_samras = True
        if token == "rf.3-1-3" and str(head[index + 1] or "").strip():
            has_title = True
    return {
        "missing_primary_samras_node": not has_samras,
        "missing_primary_title_binding": not has_title,
    }


def _repair_source_documents(data_root: Path, notes_dir: Path) -> dict[str, Any]:
    source_dir = data_root / "sandbox" / "cts-gis" / "sources"
    anchor_path = data_root / "sandbox" / "cts-gis" / ANCHOR_NAME
    if not source_dir.exists():
        return {"data_root": str(data_root), "warnings": [f"Missing source directory: {source_dir}"]}

    reference_lookup, warnings = _reference_geojson_lookup(notes_dir)
    patched_sources = 0
    missing_references: list[str] = []
    title_repairs = 0
    patched_documents: list[str] = []
    source_audit = {
        "missing_primary_samras_node": [],
        "missing_primary_title_binding": [],
    }

    for path in sorted(source_dir.glob("*.fnd.*.json")):
        payload = _read_json(path)
        space = dict(payload.get("datum_addressing_abstraction_space") or {})
        node_id = _primary_samras_node_id(space)
        label = _primary_label(space)
        ref_key = _reference_key_for_source(node_id, label)
        metadata_changed = False
        if ref_key and ref_key in reference_lookup:
            reference = reference_lookup[ref_key]
            payload["reference_geojson_node_id"] = node_id
            try:
                reference_source = str(reference["path"].relative_to(REPO_ROOT))
            except ValueError:
                reference_source = str(reference["path"])
            payload["reference_geojson_source"] = reference_source
            payload["reference_geojson"] = reference["payload"]
            patched_sources += 1
            metadata_changed = True
            patched_documents.append(path.name)
        else:
            missing_references.append(path.name)

        file_title_repairs = _replace_title_here_tokens(space)
        title_repairs += file_title_repairs
        profile_audit = _audit_source_profile_document(space)
        if profile_audit["missing_primary_samras_node"]:
            source_audit["missing_primary_samras_node"].append(path.name)
        if profile_audit["missing_primary_title_binding"]:
            source_audit["missing_primary_title_binding"].append(path.name)
        payload["datum_addressing_abstraction_space"] = space
        if metadata_changed or file_title_repairs:
            ordered_payload = {
                key: value
                for key, value in payload.items()
                if key != "datum_addressing_abstraction_space"
            }
            ordered_payload["datum_addressing_abstraction_space"] = space
            _write_json(path, ordered_payload)

    admin_stats: dict[str, int] = {}
    admin_audit: dict[str, Any] = {}
    admin_path = source_dir / ADMIN_NAME
    if admin_path.exists():
        repaired_admin, admin_stats = _repair_admin_payload(_read_json(admin_path))
        admin_audit = _audit_admin_payload(repaired_admin)
        _write_json(admin_path, repaired_admin)

    anchor_updated = False
    if anchor_path.exists():
        anchor_payload = _read_json(anchor_path)
        rebuilt_anchor = _rebuild_anchor_source_rows(anchor_payload, source_dir)
        _write_json(anchor_path, rebuilt_anchor)
        anchor_updated = True
    else:
        warnings.append(f"Missing CTS-GIS anchor file: {anchor_path}")

    return {
        "data_root": str(data_root),
        "patched_sources": patched_sources,
        "patched_documents": patched_documents,
        "missing_references": missing_references,
        "title_repairs": title_repairs,
        "admin_stats": admin_stats,
        "admin_audit": admin_audit,
        "source_audit": source_audit,
        "anchor_updated": anchor_updated,
        "warnings": warnings,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Repair Summit CTS-GIS sandbox source metadata and catalog rows.")
    parser.add_argument(
        "--notes-dir",
        default=str(DEFAULT_NOTES_DIR),
        help="Path to the Summit reference GeoJSON notes directory.",
    )
    parser.add_argument(
        "--data-root",
        action="append",
        default=[],
        help="One or more authoritative data roots. Defaults to the repo deployed data and the live mycite-state data.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    notes_dir = Path(args.notes_dir)
    data_roots = [Path(item) for item in (args.data_root or [])] or list(DEFAULT_DATA_ROOTS)
    for data_root in data_roots:
        result = _repair_source_documents(data_root, notes_dir)
        print(f"Data root: {result['data_root']}")
        print(f"  Patched reference-backed source docs: {result.get('patched_sources', 0)}")
        print(f"  Repaired title placeholders: {result.get('title_repairs', 0)}")
        print(f"  Anchor updated: {result.get('anchor_updated', False)}")
        admin_stats = result.get("admin_stats") or {}
        if admin_stats:
            print(f"  Summit adm3 rows regenerated: {admin_stats.get('summit_admin_rows_regenerated', 0)}")
            print(f"  Reminderville rebound rows: {admin_stats.get('reminderville_rebound', 0)}")
            print(f"  Boston Heights renames: {admin_stats.get('boston_heights_renamed', 0)}")
        admin_audit = result.get("admin_audit") or {}
        if admin_audit:
            print(f"  Duplicate administrative node bindings: {len(admin_audit.get('duplicate_node_ids', []))}")
            print(f"  Blank administrative ASCII titles: {len(admin_audit.get('blank_title_nodes', []))}")
            print(f"  Missing administrative title bindings: {len(admin_audit.get('missing_title_rows', []))}")
        source_audit = result.get("source_audit") or {}
        if source_audit:
            print(f"  Source docs missing primary SAMRAS node: {len(source_audit.get('missing_primary_samras_node', []))}")
            print(f"  Source docs missing primary title binding: {len(source_audit.get('missing_primary_title_binding', []))}")
        missing_references = result.get("missing_references") or []
        if missing_references:
            print(f"  WARNING: Missing reference matches for {len(missing_references)} document(s).")
            for item in missing_references:
                print(f"    - {item}")
        for warning in result.get("warnings") or []:
            print(f"  WARNING: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
