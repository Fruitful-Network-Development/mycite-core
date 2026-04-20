from __future__ import annotations

import argparse
from collections import Counter
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.modules.cross_domain.cts_gis import CtsGisReadOnlyService
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentCatalogResult,
    AuthoritativeDatumDocumentRequest,
    AuthoritativeDatumDocumentRow,
)
from MyCiteV2.scripts.cts_gis_geojson_hops_utils import (
    as_text as _shared_as_text,
    encode_hops_coordinate as _shared_encode_hops_coordinate,
    normalize_ring_open as _shared_normalize_ring_open,
    read_json as _shared_read_json,
    reference_polygons_from_geojson as _shared_reference_polygons_from_geojson,
    write_json as _shared_write_json,
)

DEFAULT_DATA_ROOTS = [
    REPO_ROOT / "deployed" / "fnd" / "data",
    Path("/srv/mycite-state/instances/fnd/data"),
]
ANCHOR_NAME = "tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json"
PROJECTION_GLOB = "sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77*.json"
SWAPPED_SUFFIXES = frozenset(("3-2-3-17-77-3-8", "3-2-3-17-77-3-9"))
STAGE_B_SUFFIXES = frozenset(
    (
        "3-2-3-17-77-1-1",
        "3-2-3-17-77-1-2",
        "3-2-3-17-77-1-10",
    )
)
REFERENCE_KEYS = (
    "reference_geojson",
    "reference_geojson_source",
    "reference_geojson_node_id",
)
REF_PATTERN = re.compile(r"^[4567]-\d+-\d+$")
ROW_ADDRESS_PATTERN = re.compile(r"\b[4567]-\d+-\d+\b")
REFERENCE_MISMATCH_ISSUES = frozenset(
    (
        "polygon_count_mismatch",
        "ring_count_mismatch",
        "ring_ordering",
        "stale_hops_data",
        "declared_count_mismatch",
    )
)
CONTRACT_DRIFT_ISSUES = frozenset(("contract_violation", "row_address_defect"))
ACTION_PRIORITY = {
    "needs_full_hops_regeneration_from_geojson": 0,
    "needs_deterministic_repair": 1,
    "needs_repo_state_reconciliation": 2,
    "safe_to_leave_as_is": 3,
}
CLASSIFICATION_PRIORITY = {
    "reference_mismatch": 0,
    "contract_drift": 1,
    "repo_state_drift_only": 2,
    "clean": 3,
}


class _SingleDocumentStore:
    def __init__(self, document: AuthoritativeDatumDocument) -> None:
        self._document = document

    def read_authoritative_datum_documents(
        self,
        request: AuthoritativeDatumDocumentRequest | dict[str, Any],
    ) -> AuthoritativeDatumDocumentCatalogResult:
        normalized_request = (
            request
            if isinstance(request, AuthoritativeDatumDocumentRequest)
            else AuthoritativeDatumDocumentRequest.from_dict(request)
        )
        return AuthoritativeDatumDocumentCatalogResult(
            tenant_id=normalized_request.tenant_id,
            documents=(self._document,),
            source_files={},
            readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
        )


def _as_text(value: object) -> str:
    return _shared_as_text(value)


def _dedupe_texts(values: list[object] | tuple[object, ...]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _as_text(value)
        if not text or text in seen:
            continue
        out.append(text)
        seen.add(text)
    return out


def _first_non_empty(values: list[object] | tuple[object, ...]) -> str:
    for value in values:
        text = _as_text(value)
        if text:
            return text
    return ""


def _read_json(path: Path) -> dict[str, Any]:
    return _shared_read_json(path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _shared_write_json(path, payload)


def _address_sort_key(token: str) -> tuple[tuple[int, ...], str]:
    parts = str(token or "").split("-")
    if parts and all(part.isdigit() for part in parts):
        return tuple(int(part) for part in parts), str(token)
    return (10**9,), str(token)


def _node_suffix_from_path(path: Path) -> str:
    name = _as_text(path.name)
    if ".fnd." not in name or not name.endswith(".json"):
        return ""
    return name.split(".fnd.", 1)[1][:-5]


def _row_family(row_address: str) -> str:
    parts = _as_text(row_address).split("-")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return ""
    return parts[0]


def _datum_space(payload: dict[str, Any]) -> dict[str, Any]:
    space = payload.get("datum_addressing_abstraction_space")
    return dict(space) if isinstance(space, dict) else {}


def _row_tokens(space: dict[str, Any], row_address: str) -> list[Any]:
    row = space.get(row_address)
    if not isinstance(row, list) or not row:
        return []
    if isinstance(row[0], list):
        return list(row[0])
    return list(row)


def _set_row_tokens(space: dict[str, Any], row_address: str, tokens: list[Any]) -> bool:
    row = space.get(row_address)
    if isinstance(row, list) and row and isinstance(row[0], list):
        row[0] = list(tokens)
        space[row_address] = row
        return True
    if isinstance(row, list):
        space[row_address] = list(tokens)
        return True
    return False


def _row_hops_tokens(space: dict[str, Any], row_address: str) -> list[str]:
    tokens = _row_tokens(space, row_address)
    out: list[str] = []
    for index, token in enumerate(tokens[:-1]):
        if _as_text(token) != "rf.3-1-1":
            continue
        hops_token = _as_text(tokens[index + 1])
        if hops_token:
            out.append(hops_token)
    return out


def _linked_row_addresses(space: dict[str, Any], row_address: str) -> list[str]:
    tokens = _row_tokens(space, row_address)
    seen: set[str] = set()
    out: list[str] = []
    for token in tokens:
        address = _as_text(token)
        if address == row_address or address in seen or address not in space:
            continue
        if not _row_family(address):
            continue
        out.append(address)
        seen.add(address)
    return out


def _row_polygon_groups(space: dict[str, Any], row_address: str) -> list[dict[str, Any]]:
    family = _row_family(row_address)
    linked = _linked_row_addresses(space, row_address)
    if family == "4":
        return [{"polygon_row_address": row_address, "ring_row_addresses": [row_address]}]
    if family == "5":
        rings = [address for address in linked if _row_family(address) == "4"]
        return [{"polygon_row_address": row_address, "ring_row_addresses": rings}] if rings else []
    if family in {"6", "7"}:
        polygons: list[dict[str, Any]] = []
        for address in linked:
            if _row_family(address) not in {"6", "5", "4"}:
                continue
            polygons.extend(_row_polygon_groups(space, address))
        return polygons
    return []


def _normalize_reference_ring(ring: Any) -> list[list[float]]:
    return _shared_normalize_ring_open(ring)


def _reference_polygons(payload: dict[str, Any]) -> list[list[list[list[float]]]]:
    return _shared_reference_polygons_from_geojson(payload)


def _encode_hops_coordinate(longitude: float, latitude: float) -> str:
    return _shared_encode_hops_coordinate(longitude, latitude)


def _issue_sort_key(issue_type: str) -> tuple[int, str]:
    priorities = {
        "polygon_count_mismatch": 0,
        "ring_count_mismatch": 1,
        "ring_ordering": 2,
        "stale_hops_data": 3,
        "declared_count_mismatch": 4,
        "row_address_defect": 5,
        "contract_violation": 6,
        "repo_state_desync": 7,
    }
    return priorities.get(issue_type, 10**6), issue_type


def _finding_sort_key(finding: dict[str, Any]) -> tuple[int, str]:
    return _issue_sort_key(_as_text(finding.get("issue_type"))) + (_as_text(finding.get("detail")),)


def _sort_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(list(findings), key=_finding_sort_key)


def _recommended_action(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "safe_to_leave_as_is"
    actions = [_as_text(finding.get("recommended_action")) for finding in findings]
    ranked = sorted(
        (action for action in actions if action),
        key=lambda action: (ACTION_PRIORITY.get(action, 10**6), action),
    )
    return ranked[0] if ranked else "safe_to_leave_as_is"


def _classification_for_findings(findings: list[dict[str, Any]]) -> str:
    issue_types = {_as_text(finding.get("issue_type")) for finding in findings if _as_text(finding.get("issue_type"))}
    if issue_types & REFERENCE_MISMATCH_ISSUES:
        return "reference_mismatch"
    if issue_types & CONTRACT_DRIFT_ISSUES:
        return "contract_drift"
    if "repo_state_desync" in issue_types:
        return "repo_state_drift_only"
    return "clean"


def _rows_from_text(text: str) -> list[str]:
    return _dedupe_texts(ROW_ADDRESS_PATTERN.findall(_as_text(text)))


def _replace_reference_token(space: dict[str, Any], *, row_address: str, old: str, new: str) -> bool:
    tokens = _row_tokens(space, row_address)
    if not tokens:
        return False
    changed = False
    out: list[Any] = []
    for token in tokens:
        if _as_text(token) == old:
            out.append(new)
            changed = True
        else:
            out.append(token)
    if changed:
        _set_row_tokens(space, row_address, out)
    return changed


def _dedupe_row_references(space: dict[str, Any], row_address: str) -> int:
    tokens = _row_tokens(space, row_address)
    if len(tokens) < 3:
        return 0
    seen: set[str] = set()
    out = list(tokens[:2])
    removed = 0
    for token in tokens[2:]:
        ref = _as_text(token)
        if ref and REF_PATTERN.match(ref):
            if ref in seen:
                removed += 1
                continue
            seen.add(ref)
        out.append(token)
    if removed:
        _set_row_tokens(space, row_address, out)
    return removed


def _rename_row_address(
    payload: dict[str, Any],
    *,
    old_address: str,
    new_address: str,
) -> bool:
    space = _datum_space(payload)
    if old_address not in space or new_address in space:
        return False
    row = space.get(old_address)
    tokens = _row_tokens(space, old_address)
    if not tokens:
        return False
    tokens[0] = new_address
    if isinstance(row, list) and row and isinstance(row[0], list):
        row[0] = tokens
    elif isinstance(row, list):
        row = tokens
    remapped: dict[str, Any] = {}
    for address, value in space.items():
        if address == old_address:
            remapped[new_address] = row
        else:
            remapped[address] = value
    payload["datum_addressing_abstraction_space"] = remapped
    return True


def _first_primary_node_id(tokens: list[Any]) -> str:
    for index, token in enumerate(tokens[:-1]):
        if _as_text(token) == "rf.3-1-2":
            return _as_text(tokens[index + 1])
    return ""


def _hops_token_count(tokens: list[Any]) -> int:
    out = 0
    for index, token in enumerate(tokens[:-1]):
        if _as_text(token) == "rf.3-1-1" and _as_text(tokens[index + 1]):
            out += 1
    return out


def _contract_violations(path: Path, payload: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    suffix = _node_suffix_from_path(path)
    space = _datum_space(payload)

    row7 = _row_tokens(space, "7-3-1")
    if not row7:
        violations.append("missing 7-3-1 row")
    else:
        primary_node_id = _first_primary_node_id(row7)
        if not primary_node_id:
            violations.append("7-3-1 missing primary rf.3-1-2 binding")
        elif suffix and primary_node_id != suffix:
            violations.append(f"suffix/7-3-1 primary mismatch ({suffix} != {primary_node_id})")

    ref_node_id = _as_text(payload.get("reference_geojson_node_id"))
    if ref_node_id and suffix and ref_node_id != suffix:
        violations.append(f"suffix/reference_geojson_node_id mismatch ({suffix} != {ref_node_id})")

    for row_address in sorted(space.keys(), key=_address_sort_key):
        tokens = _row_tokens(space, row_address)
        if not tokens:
            continue
        parts = row_address.split("-")
        if len(parts) != 3 or not all(piece.isdigit() for piece in parts):
            continue

        family = parts[0]
        if family == "4":
            declared = int(parts[1])
            observed = _hops_token_count(tokens)
            if declared != observed:
                violations.append(f"{row_address} declares {declared} HOPS tokens but carries {observed}")
            continue

        if family in {"5", "6"}:
            references = [
                _as_text(token)
                for token in tokens[2:]
                if _as_text(token) and REF_PATTERN.match(_as_text(token))
            ]
            if len(references) != len(set(references)):
                violations.append(f"{row_address} has duplicate references")
            expected_prefix = "4-" if family == "5" else "5-"
            for ref in references:
                if not ref.startswith(expected_prefix):
                    violations.append(f"{row_address} references wrong family ({ref})")
                if ref not in space:
                    violations.append(f"{row_address} references missing row ({ref})")

    deduped: list[str] = []
    seen: set[str] = set()
    for item in violations:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _finding(
    *,
    issue_type: str,
    detail: str,
    rows_involved: list[str] | tuple[str, ...] = (),
    recommended_action: str,
    reference_geojson_source: str = "",
    roots_involved: list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "issue_type": _as_text(issue_type),
        "detail": _as_text(detail),
        "rows_involved": _dedupe_texts(list(rows_involved)),
        "recommended_action": _as_text(recommended_action),
        "reference_geojson_source": _as_text(reference_geojson_source),
        "roots_involved": _dedupe_texts(list(roots_involved)),
    }


def _deterministic_findings(
    notes: list[str],
    *,
    reference_geojson_source: str = "",
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for note in list(notes or []):
        issue_type = "row_address_defect"
        if "duplicate references removed" in note:
            issue_type = "contract_violation"
        findings.append(
            _finding(
                issue_type=issue_type,
                detail=note,
                rows_involved=_rows_from_text(note),
                recommended_action="needs_deterministic_repair",
                reference_geojson_source=reference_geojson_source,
            )
        )
    return findings


def _contract_findings(
    violations: list[str],
    *,
    reference_geojson_source: str = "",
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for violation in list(violations or []):
        issue_type = "contract_violation"
        if "declares" in violation and "HOPS tokens but carries" in violation:
            issue_type = "declared_count_mismatch"
        elif "references missing row" in violation or "references wrong family" in violation:
            issue_type = "row_address_defect"
        findings.append(
            _finding(
                issue_type=issue_type,
                detail=violation,
                rows_involved=_rows_from_text(violation),
                recommended_action="needs_deterministic_repair",
                reference_geojson_source=reference_geojson_source,
            )
        )
    return findings


def _reference_owner_row_address(path: Path, payload: dict[str, Any]) -> str:
    suffix = _node_suffix_from_path(path)
    expected_node_id = _as_text(payload.get("reference_geojson_node_id")) or suffix
    space = _datum_space(payload)
    for row_address in sorted(space.keys(), key=_address_sort_key):
        if _row_family(row_address) != "7":
            continue
        tokens = _row_tokens(space, row_address)
        if _first_primary_node_id(tokens) == expected_node_id:
            return row_address
    return "7-3-1" if "7-3-1" in space else ""


def _reference_geometry_findings(path: Path, payload: dict[str, Any]) -> list[dict[str, Any]]:
    reference_geojson_source = _as_text(payload.get("reference_geojson_source"))
    reference_payload = payload.get("reference_geojson")
    if not isinstance(reference_payload, dict):
        return []

    space = _datum_space(payload)
    owner_row_address = _reference_owner_row_address(path, payload)
    if not owner_row_address:
        return []

    polygon_groups = _row_polygon_groups(space, owner_row_address)
    reference_polygons = _reference_polygons(reference_payload)
    findings: list[dict[str, Any]] = []

    if len(reference_polygons) != len(polygon_groups):
        findings.append(
            _finding(
                issue_type="polygon_count_mismatch",
                detail=(
                    f"{path.name} reference GeoJSON carries {len(reference_polygons)} polygon members, "
                    f"but the HOPS row chain resolves {len(polygon_groups)}."
                ),
                rows_involved=[owner_row_address, *[entry.get("polygon_row_address", "") for entry in polygon_groups]],
                recommended_action="needs_full_hops_regeneration_from_geojson",
                reference_geojson_source=reference_geojson_source,
            )
        )

    for polygon_index, (polygon_entry, reference_polygon) in enumerate(
        zip(polygon_groups, reference_polygons),
        start=1,
    ):
        polygon_row_address = _as_text(polygon_entry.get("polygon_row_address"))
        ring_row_addresses = _dedupe_texts(list(polygon_entry.get("ring_row_addresses") or []))
        if len(ring_row_addresses) != len(reference_polygon):
            findings.append(
                _finding(
                    issue_type="ring_count_mismatch",
                    detail=(
                        f"{path.name} polygon {polygon_index} carries {len(reference_polygon)} rings, "
                        f"but the HOPS row chain resolves {len(ring_row_addresses)}."
                    ),
                    rows_involved=[polygon_row_address, *ring_row_addresses],
                    recommended_action="needs_full_hops_regeneration_from_geojson",
                    reference_geojson_source=reference_geojson_source,
                )
            )
            continue

        expected_token_rows = [
            [_encode_hops_coordinate(longitude, latitude) for longitude, latitude in _normalize_reference_ring(ring)]
            for ring in reference_polygon
        ]
        actual_token_rows = [_row_hops_tokens(space, row_address) for row_address in ring_row_addresses]
        if actual_token_rows == expected_token_rows:
            continue

        expected_counter = Counter(tuple(row) for row in expected_token_rows)
        actual_counter = Counter(tuple(row) for row in actual_token_rows)
        if expected_counter == actual_counter:
            findings.append(
                _finding(
                    issue_type="ring_ordering",
                    detail=(
                        f"{path.name} polygon {polygon_index} links the correct rings, "
                        "but the shell/hole ordering does not match the reference GeoJSON."
                    ),
                    rows_involved=[polygon_row_address, *ring_row_addresses],
                    recommended_action="needs_deterministic_repair",
                    reference_geojson_source=reference_geojson_source,
                )
            )
            continue

        for ring_index, (row_address, actual_tokens, expected_tokens) in enumerate(
            zip(ring_row_addresses, actual_token_rows, expected_token_rows),
            start=1,
        ):
            if len(actual_tokens) != len(expected_tokens):
                findings.append(
                    _finding(
                        issue_type="declared_count_mismatch",
                        detail=(
                            f"{path.name} ring {polygon_index}.{ring_index} expected {len(expected_tokens)} "
                            f"HOPS vertices from reference GeoJSON, but {row_address} carries {len(actual_tokens)}."
                        ),
                        rows_involved=[row_address],
                        recommended_action="needs_full_hops_regeneration_from_geojson",
                        reference_geojson_source=reference_geojson_source,
                    )
                )
                continue
            if actual_tokens != expected_tokens:
                findings.append(
                    _finding(
                        issue_type="stale_hops_data",
                        detail=(
                            f"{path.name} ring {polygon_index}.{ring_index} HOPS tokens do not match the "
                            f"canonical reference geometry for {row_address}."
                        ),
                        rows_involved=[row_address],
                        recommended_action="needs_full_hops_regeneration_from_geojson",
                        reference_geojson_source=reference_geojson_source,
                    )
                )

    return _sort_findings(findings)


def _normalized_core_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in dict(payload).items()
        if key not in REFERENCE_KEYS
    }


def _repo_state_drift_finding(
    *,
    document_name: str,
    baseline_root: str,
    comparison_root: str,
    baseline_payload: dict[str, Any] | None,
    comparison_payload: dict[str, Any] | None,
    reference_geojson_source: str = "",
) -> dict[str, Any] | None:
    if baseline_payload is None and comparison_payload is None:
        return None
    if baseline_payload is None:
        return _finding(
            issue_type="repo_state_desync",
            detail=f"{document_name} is missing from baseline root {baseline_root}.",
            recommended_action="needs_repo_state_reconciliation",
            reference_geojson_source=reference_geojson_source,
            roots_involved=[baseline_root, comparison_root],
        )
    if comparison_payload is None:
        return _finding(
            issue_type="repo_state_desync",
            detail=f"{document_name} is missing from comparison root {comparison_root}.",
            recommended_action="needs_repo_state_reconciliation",
            reference_geojson_source=reference_geojson_source,
            roots_involved=[baseline_root, comparison_root],
        )

    baseline_core = _normalized_core_payload(baseline_payload)
    comparison_core = _normalized_core_payload(comparison_payload)
    if baseline_core == comparison_core:
        return None

    baseline_space = _datum_space(baseline_core)
    comparison_space = _datum_space(comparison_core)
    changed_rows = sorted(
        {
            address
            for address in set(baseline_space) | set(comparison_space)
            if baseline_space.get(address) != comparison_space.get(address)
        },
        key=_address_sort_key,
    )
    changed_top_level_keys = sorted(
        {
            key
            for key in set(baseline_core) | set(comparison_core)
            if key != "datum_addressing_abstraction_space"
            and baseline_core.get(key) != comparison_core.get(key)
        }
    )
    detail_parts: list[str] = []
    if changed_top_level_keys:
        detail_parts.append(f"top-level keys differ: {', '.join(changed_top_level_keys)}")
    if changed_rows:
        detail_parts.append(f"rows differ: {', '.join(changed_rows)}")
    return _finding(
        issue_type="repo_state_desync",
        detail=(
            f"{document_name} differs between {comparison_root} and baseline {baseline_root}"
            + (f" ({'; '.join(detail_parts)})" if detail_parts else ".")
        ),
        rows_involved=changed_rows,
        recommended_action="needs_repo_state_reconciliation",
        reference_geojson_source=reference_geojson_source,
        roots_involved=[baseline_root, comparison_root],
    )


def _align_swapped_node_bindings(path: Path, payload: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    suffix = _node_suffix_from_path(path)
    if suffix not in SWAPPED_SUFFIXES:
        return notes

    space = _datum_space(payload)
    row = space.get("7-3-1")
    if not isinstance(row, list) or not row or not isinstance(row[0], list):
        return notes

    head = list(row[0])
    rf_indexes = [index for index, token in enumerate(head[:-1]) if _as_text(token) == "rf.3-1-2"]
    if not rf_indexes:
        return notes

    primary_index = rf_indexes[0]
    old_primary = _as_text(head[primary_index + 1])
    if old_primary and old_primary != suffix:
        head[primary_index + 1] = suffix
        notes.append(f"7-3-1 primary node id set to {suffix}")

    if len(rf_indexes) > 1:
        secondary_index = rf_indexes[1]
        secondary_value = _as_text(head[secondary_index + 1])
        if old_primary and secondary_value.startswith(old_primary + "-"):
            remapped_secondary = suffix + secondary_value[len(old_primary) :]
            if remapped_secondary != secondary_value:
                head[secondary_index + 1] = remapped_secondary
                notes.append("7-3-1 secondary node id prefix aligned to suffix")

    row[0] = head
    space["7-3-1"] = row
    payload["datum_addressing_abstraction_space"] = space

    has_reference_metadata = any(key in payload for key in REFERENCE_KEYS)
    if has_reference_metadata:
        ref_node_id = _as_text(payload.get("reference_geojson_node_id"))
        if ref_node_id != suffix:
            payload["reference_geojson_node_id"] = suffix
            notes.append(f"reference_geojson_node_id set to {suffix}")

    return notes


def _repair_stage_b_contract_defects(path: Path, payload: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    suffix = _node_suffix_from_path(path)
    if suffix not in STAGE_B_SUFFIXES:
        return notes

    space = _datum_space(payload)
    if suffix == "3-2-3-17-77-1-1":
        removed = _dedupe_row_references(space, "5-0-1")
        if removed:
            notes.append(f"5-0-1 duplicate references removed ({removed})")

    if suffix == "3-2-3-17-77-1-2":
        if "4-1505-1" in space and "4-1505-2" not in space:
            if _replace_reference_token(
                space,
                row_address="5-0-1",
                old="4-1505-2",
                new="4-1505-1",
            ):
                notes.append("5-0-1 missing row reference 4-1505-2 aligned to 4-1505-1")

    if suffix == "3-2-3-17-77-1-10":
        tokens = _row_tokens(space, "4-21-1")
        observed = _hops_token_count(tokens)
        if observed == 20 and "4-20-1" not in space:
            if _rename_row_address(payload, old_address="4-21-1", new_address="4-20-1"):
                space = _datum_space(payload)
                if _replace_reference_token(
                    space,
                    row_address="5-0-1",
                    old="4-21-1",
                    new="4-20-1",
                ):
                    notes.append("4-21-1 row address aligned to observed 20-token declaration")
                    notes.append("5-0-1 reference updated from 4-21-1 to 4-20-1")
                else:
                    notes.append("4-21-1 row address aligned to observed 20-token declaration")

    if notes:
        payload["datum_addressing_abstraction_space"] = space
    return notes


def _repair_known_label_typos(path: Path, payload: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    suffix = _node_suffix_from_path(path)
    if suffix != "3-2-3-17-77-3-8":
        return notes

    space = _datum_space(payload)
    row = space.get("5-0-1")
    if not isinstance(row, list) or len(row) < 2 or not isinstance(row[1], list):
        return notes
    labels = list(row[1])
    if labels == ["silver_lake_boundar"]:
        row[1] = ["silver_lake_boundary"]
        space["5-0-1"] = row
        payload["datum_addressing_abstraction_space"] = space
        notes.append("5-0-1 label normalized from silver_lake_boundar to silver_lake_boundary")
    return notes


def _load_anchor_rows(anchor_path: Path) -> tuple[AuthoritativeDatumDocumentRow, ...]:
    payload = _read_json(anchor_path)
    space = payload.get("datum_addressing_abstraction_space")
    row_source = space if isinstance(space, dict) else payload
    rows = [
        AuthoritativeDatumDocumentRow(datum_address=address, raw=raw)
        for address, raw in sorted(dict(row_source).items(), key=lambda item: _address_sort_key(item[0]))
    ]
    return tuple(rows)


def _build_document(
    *,
    path: Path,
    payload: dict[str, Any],
    anchor_rows: tuple[AuthoritativeDatumDocumentRow, ...],
    drop_reference_metadata: bool,
) -> AuthoritativeDatumDocument:
    metadata = {
        key: value
        for key, value in payload.items()
        if key != "datum_addressing_abstraction_space"
    }
    if drop_reference_metadata:
        for key in REFERENCE_KEYS:
            metadata.pop(key, None)

    space = _datum_space(payload)
    rows = tuple(
        AuthoritativeDatumDocumentRow(datum_address=address, raw=raw)
        for address, raw in sorted(space.items(), key=lambda item: _address_sort_key(item[0]))
    )

    return AuthoritativeDatumDocument(
        document_id=f"sandbox:cts_gis:{path.name}",
        source_kind="sandbox_source",
        document_name=path.name,
        relative_path=f"sandbox/cts-gis/sources/{path.name}",
        tool_id="cts_gis",
        anchor_document_name=ANCHOR_NAME,
        anchor_document_path=f"sandbox/cts-gis/{ANCHOR_NAME}",
        anchor_rows=anchor_rows,
        document_metadata=metadata,
        rows=rows,
    )


def _projection_snapshot(
    *,
    path: Path,
    payload: dict[str, Any],
    anchor_rows: tuple[AuthoritativeDatumDocumentRow, ...],
    drop_reference_metadata: bool,
) -> dict[str, Any]:
    document = _build_document(
        path=path,
        payload=payload,
        anchor_rows=anchor_rows,
        drop_reference_metadata=drop_reference_metadata,
    )
    service = CtsGisReadOnlyService(_SingleDocumentStore(document))
    node_id = _node_suffix_from_path(path)
    doc_id = f"sandbox:cts_gis:{path.name}"
    surface = service.read_surface(
        "fnd",
        selected_document_id=doc_id,
        mediation_state={
            "attention_document_id": doc_id,
            "attention_node_id": node_id,
            "intention_token": "0",
        },
    )
    map_projection = dict(surface.get("map_projection") or {})
    decode_summary = dict(map_projection.get("decode_summary") or {})
    return {
        "projection_state": _as_text(map_projection.get("projection_state")),
        "projection_source": _as_text(map_projection.get("projection_source")),
        "feature_count": int(map_projection.get("feature_count") or 0),
        "reference_binding_count": int(decode_summary.get("reference_binding_count") or 0),
        "decoded_coordinate_count": int(decode_summary.get("decoded_coordinate_count") or 0),
        "failed_token_count": int(decode_summary.get("failed_token_count") or 0),
        "warnings": list(map_projection.get("warnings") or []),
    }


def _is_stage_a_safe(
    contract_violations: list[str],
    *,
    with_ref: dict[str, Any],
    without_ref: dict[str, Any],
    pending_deterministic_fixes: bool,
) -> bool:
    del with_ref
    if contract_violations:
        return False
    if pending_deterministic_fixes:
        return False
    if _as_text(without_ref.get("projection_source")) != "hops":
        return False
    if _as_text(without_ref.get("projection_state")) not in {"projectable", "projectable_degraded"}:
        return False
    if int(without_ref.get("feature_count") or 0) <= 0:
        return False
    if int(without_ref.get("failed_token_count") or 0) != 0:
        return False
    return True


def _strip_reference_metadata(payload: dict[str, Any]) -> bool:
    changed = False
    for key in REFERENCE_KEYS:
        if key in payload:
            del payload[key]
            changed = True
    return changed


def _markdown_summary(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# CTS-GIS Summit Source Review")
    lines.append("")
    lines.append(f"Reference baseline: `{_as_text(report.get('baseline_data_root'))}`")
    comparison_roots = list(report.get("comparison_data_roots") or [])
    if comparison_roots:
        lines.append(
            "Comparison roots: " + ", ".join(f"`{_as_text(root)}`" for root in comparison_roots if _as_text(root))
        )
    lines.append("")
    lines.append("## Totals")
    lines.append("")
    lines.append(f"- Unique projection documents reviewed: {int(report.get('document_count') or 0)}")
    lines.append(f"- Flagged documents: {int(report.get('flagged_count') or 0)}")
    lines.append(f"- Clean documents: {int(report.get('clean_count') or 0)}")
    counts = dict(report.get("classification_counts") or {})
    for key in ("reference_mismatch", "contract_drift", "repo_state_drift_only", "clean"):
        if key in counts:
            lines.append(f"- `{key}`: {int(counts.get(key) or 0)}")
    lines.append("")
    lines.append("## Root Passes")
    lines.append("")
    lines.append("| Data Root | Documents | Safe To Strip | Deterministic Fixes |")
    lines.append("| --- | --- | --- | --- |")
    for root_report in list(report.get("root_reports") or []):
        lines.append(
            f"| `{_as_text(root_report.get('data_root'))}` | "
            f"{int(root_report.get('document_count') or 0)} | "
            f"{int(root_report.get('safe_to_strip_count') or 0)} | "
            f"{int(root_report.get('deterministic_fix_count') or 0)} |"
        )
    lines.append("")
    lines.append("## Flagged Documents")
    lines.append("")
    flagged = [row for row in list(report.get("documents") or []) if _as_text(row.get("review_bucket")) == "flagged"]
    if not flagged:
        lines.append("- None")
    else:
        lines.append("| Document | Classification | Action | Issues | Reference |")
        lines.append("| --- | --- | --- | --- | --- |")
        for row in flagged:
            lines.append(
                f"| `{_as_text(row.get('document_name'))}` | "
                f"`{_as_text(row.get('classification'))}` | "
                f"`{_as_text(row.get('recommended_action'))}` | "
                f"`{', '.join(list(row.get('finding_types') or []))}` | "
                f"`{_as_text(row.get('reference_geojson_source'))}` |"
            )
        lines.append("")
        lines.append("## Findings")
        lines.append("")
        for row in flagged:
            lines.append(f"- `{_as_text(row.get('document_name'))}`")
            lines.append(
                f"  classification: `{_as_text(row.get('classification'))}` | "
                f"action: `{_as_text(row.get('recommended_action'))}`"
            )
            for finding in list(row.get("findings") or []):
                rows_text = ", ".join(list(finding.get("rows_involved") or [])) or "n/a"
                lines.append(
                    f"  - `{_as_text(finding.get('issue_type'))}`: {_as_text(finding.get('detail'))} "
                    f"(rows: {rows_text})"
                )
    lines.append("")
    return "\n".join(lines) + "\n"


def _audit_and_repair_data_root(
    *,
    data_root: Path,
    apply_deterministic_fixes: bool,
    strip_stage_a: bool,
) -> dict[str, Any]:
    source_dir = data_root / "sandbox" / "cts-gis" / "sources"
    anchor_path = data_root / "sandbox" / "cts-gis" / ANCHOR_NAME
    if not source_dir.exists() or not source_dir.is_dir():
        return {
            "data_root": str(data_root),
            "document_count": 0,
            "documents": [],
            "warnings": [f"Missing source directory: {source_dir}"],
        }
    if not anchor_path.exists() or not anchor_path.is_file():
        return {
            "data_root": str(data_root),
            "document_count": 0,
            "documents": [],
            "warnings": [f"Missing anchor document: {anchor_path}"],
        }

    anchor_rows = _load_anchor_rows(anchor_path)
    document_rows: list[dict[str, Any]] = []
    safe_docs: list[str] = []
    stage_a_stripped: list[str] = []
    deterministic_fixed: list[str] = []

    for path in sorted(source_dir.glob(PROJECTION_GLOB)):
        payload = _read_json(path)
        reference_geojson_source = _as_text(payload.get("reference_geojson_source"))
        deterministic_notes = _align_swapped_node_bindings(path, payload)
        deterministic_notes.extend(_repair_stage_b_contract_defects(path, payload))
        deterministic_notes.extend(_repair_known_label_typos(path, payload))

        violations = _contract_violations(path, payload)
        with_ref = _projection_snapshot(
            path=path,
            payload=payload,
            anchor_rows=anchor_rows,
            drop_reference_metadata=False,
        )
        without_ref = _projection_snapshot(
            path=path,
            payload=payload,
            anchor_rows=anchor_rows,
            drop_reference_metadata=True,
        )

        pending_deterministic_fixes = bool(deterministic_notes) and not apply_deterministic_fixes
        reference_findings = _reference_geometry_findings(path, payload) if list(with_ref.get("warnings") or []) else []
        local_findings = _sort_findings(
            _deterministic_findings(
                deterministic_notes if pending_deterministic_fixes else [],
                reference_geojson_source=reference_geojson_source,
            )
            + _contract_findings(violations, reference_geojson_source=reference_geojson_source)
            + reference_findings
        )
        root_classification = _classification_for_findings(local_findings)
        review_bucket = "clean" if root_classification == "clean" else "flagged"

        safe_to_strip = _is_stage_a_safe(
            violations,
            with_ref=with_ref,
            without_ref=without_ref,
            pending_deterministic_fixes=pending_deterministic_fixes,
        )
        if safe_to_strip:
            safe_docs.append(path.name)

        wrote_file = False
        stripped = False
        if apply_deterministic_fixes and deterministic_notes:
            _write_json(path, payload)
            wrote_file = True
            deterministic_fixed.append(path.name)

        if strip_stage_a and safe_to_strip:
            strip_payload = payload if wrote_file else _read_json(path)
            if _strip_reference_metadata(strip_payload):
                _write_json(path, strip_payload)
                stripped = True
                stage_a_stripped.append(path.name)

        document_rows.append(
            {
                "document_name": path.name,
                "document_path": str(path),
                "node_suffix": _node_suffix_from_path(path),
                "reference_geojson_source": reference_geojson_source,
                "deterministic_fix_notes": deterministic_notes,
                "pending_deterministic_fixes": pending_deterministic_fixes,
                "contract_violations": violations,
                "local_findings": local_findings,
                "finding_types": _dedupe_texts([finding.get("issue_type") for finding in local_findings]),
                "root_classification": root_classification,
                "review_bucket": review_bucket,
                "recommended_action": _recommended_action(local_findings),
                "safe_to_strip": safe_to_strip,
                "stage_a_stripped": stripped,
                "reference_warning_count": len(list(with_ref.get("warnings") or [])),
                "projection_with_reference": with_ref,
                "projection_without_reference": without_ref,
            }
        )

    return {
        "data_root": str(data_root),
        "document_count": len(document_rows),
        "safe_to_strip_count": len(safe_docs),
        "safe_to_strip_documents": sorted(safe_docs),
        "stage_a_stripped_count": len(stage_a_stripped),
        "stage_a_stripped_documents": sorted(stage_a_stripped),
        "deterministic_fix_count": len(deterministic_fixed),
        "deterministic_fix_documents": sorted(deterministic_fixed),
        "documents": document_rows,
        "warnings": [],
    }


def _select_reference_baseline_report(reports: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not reports:
        return None

    def _score(report: dict[str, Any]) -> tuple[int, str]:
        documents = list(report.get("documents") or [])
        ref_count = sum(1 for row in documents if _as_text(row.get("reference_geojson_source")))
        return ref_count, _as_text(report.get("data_root"))

    return max(reports, key=_score)


def _build_review_report(reports: list[dict[str, Any]]) -> dict[str, Any]:
    baseline_report = _select_reference_baseline_report(reports)
    baseline_root = _as_text((baseline_report or {}).get("data_root"))
    comparison_roots = [
        _as_text(report.get("data_root"))
        for report in reports
        if _as_text(report.get("data_root")) and _as_text(report.get("data_root")) != baseline_root
    ]
    report_indexes = {
        _as_text(report.get("data_root")): {
            _as_text(row.get("document_name")): row
            for row in list(report.get("documents") or [])
            if _as_text(row.get("document_name"))
        }
        for report in reports
    }
    document_names = sorted(
        {
            name
            for index in report_indexes.values()
            for name in index.keys()
        }
    )

    documents: list[dict[str, Any]] = []
    finding_type_counts: Counter[str] = Counter()
    classification_counts: Counter[str] = Counter()

    for document_name in document_names:
        baseline_row = (report_indexes.get(baseline_root) or {}).get(document_name)
        source_row = baseline_row
        if source_row is None:
            for index in report_indexes.values():
                source_row = index.get(document_name)
                if source_row is not None:
                    break
        if source_row is None:
            continue

        reference_geojson_source = _first_non_empty(
            [row.get("reference_geojson_source") for index in report_indexes.values() for row in [index.get(document_name)] if row]
        )
        findings = list((source_row or {}).get("local_findings") or [])

        baseline_payload = None
        baseline_document_path = _as_text((baseline_row or {}).get("document_path"))
        if baseline_document_path:
            baseline_payload = _read_json(Path(baseline_document_path))

        for comparison_root in comparison_roots:
            comparison_row = (report_indexes.get(comparison_root) or {}).get(document_name)
            comparison_payload = None
            comparison_document_path = _as_text((comparison_row or {}).get("document_path"))
            if comparison_document_path:
                comparison_payload = _read_json(Path(comparison_document_path))
            drift_finding = _repo_state_drift_finding(
                document_name=document_name,
                baseline_root=baseline_root,
                comparison_root=comparison_root,
                baseline_payload=baseline_payload,
                comparison_payload=comparison_payload,
                reference_geojson_source=reference_geojson_source,
            )
            if drift_finding is not None:
                findings.append(drift_finding)

        findings = _sort_findings(findings)
        finding_types = _dedupe_texts([finding.get("issue_type") for finding in findings])
        classification = _classification_for_findings(findings)
        review_bucket = "clean" if classification == "clean" else "flagged"
        recommended_action = _recommended_action(findings)
        classification_counts[classification] += 1
        for issue_type in finding_types:
            finding_type_counts[issue_type] += 1

        root_status = {
            root: {
                "present": document_name in index,
                "root_classification": _as_text((index.get(document_name) or {}).get("root_classification")),
                "safe_to_strip": bool((index.get(document_name) or {}).get("safe_to_strip")),
                "reference_warning_count": int((index.get(document_name) or {}).get("reference_warning_count") or 0),
            }
            for root, index in report_indexes.items()
        }

        documents.append(
            {
                "document_name": document_name,
                "node_suffix": _as_text((source_row or {}).get("node_suffix")),
                "reference_geojson_source": reference_geojson_source,
                "classification": classification,
                "review_bucket": review_bucket,
                "recommended_action": recommended_action,
                "finding_types": finding_types,
                "finding_count": len(findings),
                "findings": findings,
                "root_status": root_status,
            }
        )

    documents = sorted(
        documents,
        key=lambda row: (
            0 if _as_text(row.get("review_bucket")) == "flagged" else 1,
            CLASSIFICATION_PRIORITY.get(_as_text(row.get("classification")), 10**6),
            _as_text(row.get("document_name")),
        ),
    )
    flagged_count = sum(1 for row in documents if _as_text(row.get("review_bucket")) == "flagged")
    clean_count = sum(1 for row in documents if _as_text(row.get("review_bucket")) == "clean")
    return {
        "report_type": "cts_gis_summit_review",
        "baseline_data_root": baseline_root,
        "comparison_data_roots": comparison_roots,
        "root_reports": reports,
        "document_count": len(documents),
        "flagged_count": flagged_count,
        "clean_count": clean_count,
        "classification_counts": dict(classification_counts),
        "finding_type_counts": dict(finding_type_counts),
        "documents": documents,
        "warnings": [],
    }


def _write_report_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit and repair CTS-GIS Summit projection sources with contract checks, "
            "before/after projection snapshots, and staged reference metadata stripping."
        )
    )
    parser.add_argument(
        "--data-root",
        action="append",
        default=[],
        help="One or more authoritative data roots. Defaults to repo deployed data and /srv/mycite-state.",
    )
    parser.add_argument(
        "--apply-deterministic-fixes",
        action="store_true",
        help="Apply deterministic internal fixes (currently the 3-8/3-9 node/ref binding alignment).",
    )
    parser.add_argument(
        "--strip-stage-a",
        action="store_true",
        help="Strip reference_geojson metadata only from Stage-A safe documents.",
    )
    parser.add_argument(
        "--report-json",
        default="",
        help="Write machine-readable combined review JSON to this path.",
    )
    parser.add_argument(
        "--report-markdown",
        default="",
        help="Write combined markdown review summary to this path.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    data_roots = [Path(item) for item in (args.data_root or [])] or list(DEFAULT_DATA_ROOTS)
    reports: list[dict[str, Any]] = []

    for data_root in data_roots:
        report = _audit_and_repair_data_root(
            data_root=data_root,
            apply_deterministic_fixes=bool(args.apply_deterministic_fixes),
            strip_stage_a=bool(args.strip_stage_a),
        )
        reports.append(report)
        print(f"Data root: {report['data_root']}")
        print(f"  Projection documents audited: {int(report.get('document_count') or 0)}")
        print(f"  Stage-A safe to strip: {int(report.get('safe_to_strip_count') or 0)}")
        print(f"  Stage-A stripped: {int(report.get('stage_a_stripped_count') or 0)}")
        print(f"  Deterministic fixes applied: {int(report.get('deterministic_fix_count') or 0)}")
        for warning in list(report.get("warnings") or []):
            print(f"  WARNING: {warning}")

    review_report = _build_review_report(reports)
    print(f"Review summary: {int(review_report.get('flagged_count') or 0)} flagged / {int(review_report.get('clean_count') or 0)} clean")
    classification_counts = dict(review_report.get("classification_counts") or {})
    for key in ("reference_mismatch", "contract_drift", "repo_state_drift_only"):
        if key in classification_counts:
            print(f"  {key}: {int(classification_counts.get(key) or 0)}")

    if _as_text(args.report_json):
        _write_report_file(Path(args.report_json), json.dumps(review_report, indent=2, sort_keys=False) + "\n")
        print(f"Wrote JSON report: {args.report_json}")
    if _as_text(args.report_markdown):
        _write_report_file(Path(args.report_markdown), _markdown_summary(review_report))
        print(f"Wrote markdown report: {args.report_markdown}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
