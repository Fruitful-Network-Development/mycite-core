from __future__ import annotations

import argparse
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

DEFAULT_DATA_ROOTS = [
    REPO_ROOT / "deployed" / "fnd" / "data",
    Path("/srv/mycite-state/instances/fnd/data"),
]
ANCHOR_NAME = "tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json"
PROJECTION_GLOB = "sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77*.json"
SWAPPED_SUFFIXES = frozenset(("3-2-3-17-77-3-8", "3-2-3-17-77-3-9"))
REFERENCE_KEYS = (
    "reference_geojson",
    "reference_geojson_source",
    "reference_geojson_node_id",
)
REF_PATTERN = re.compile(r"^[4567]-\d+-\d+$")


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
    if value is None:
        return ""
    return str(value).strip()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


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
            head[secondary_index + 1] = suffix + secondary_value[len(old_primary) :]
            notes.append("7-3-1 secondary node id prefix aligned to suffix")

    row[0] = head
    space["7-3-1"] = row
    payload["datum_addressing_abstraction_space"] = space

    ref_node_id = _as_text(payload.get("reference_geojson_node_id"))
    if ref_node_id != suffix:
        payload["reference_geojson_node_id"] = suffix
        notes.append(f"reference_geojson_node_id set to {suffix}")

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


def _is_stage_a_safe(contract_violations: list[str], without_ref: dict[str, Any]) -> bool:
    if contract_violations:
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
    lines.append("# CTS-GIS HOPS-First Stage-A Audit")
    lines.append("")
    lines.append(f"Data root: `{_as_text(report.get('data_root'))}`")
    lines.append("")
    lines.append("## Totals")
    lines.append("")
    lines.append(f"- Projection documents audited: {int(report.get('document_count') or 0)}")
    lines.append(f"- Stage-A safe to strip: {int(report.get('safe_to_strip_count') or 0)}")
    lines.append(f"- Stage-A stripped this run: {int(report.get('stage_a_stripped_count') or 0)}")
    lines.append(f"- Deterministic fixes applied: {int(report.get('deterministic_fix_count') or 0)}")
    lines.append("")
    lines.append("## Stage-A Safe Documents")
    lines.append("")
    safe_docs = list(report.get("safe_to_strip_documents") or [])
    if not safe_docs:
        lines.append("- None")
    else:
        for name in safe_docs:
            lines.append(f"- `{name}`")
    lines.append("")
    lines.append("## Needs Repair / Blocked")
    lines.append("")
    rows = list(report.get("documents") or [])
    blocked = [row for row in rows if not bool(row.get("safe_to_strip"))]
    if not blocked:
        lines.append("- None")
    else:
        for row in blocked:
            lines.append(f"- `{_as_text(row.get('document_name'))}`")
            violations = list(row.get("contract_violations") or [])
            if violations:
                for violation in violations:
                    lines.append(f"  - contract: {violation}")
            without_ref = dict(row.get("projection_without_reference") or {})
            lines.append(
                "  - projection_without_reference: "
                + f"{_as_text(without_ref.get('projection_state'))}/"
                + f"{_as_text(without_ref.get('projection_source'))}/"
                + f"features={int(without_ref.get('feature_count') or 0)}"
            )
    lines.append("")
    lines.append("## Before/After Projection Snapshots")
    lines.append("")
    lines.append("| Document | With Reference | Without Reference |")
    lines.append("| --- | --- | --- |")
    for row in rows:
        before = dict(row.get("projection_with_reference") or {})
        after = dict(row.get("projection_without_reference") or {})
        before_text = (
            f"{_as_text(before.get('projection_state'))}/"
            f"{_as_text(before.get('projection_source'))}/"
            f"f{int(before.get('feature_count') or 0)}/"
            f"w{len(before.get('warnings') or [])}"
        )
        after_text = (
            f"{_as_text(after.get('projection_state'))}/"
            f"{_as_text(after.get('projection_source'))}/"
            f"f{int(after.get('feature_count') or 0)}/"
            f"w{len(after.get('warnings') or [])}"
        )
        lines.append(
            f"| `{_as_text(row.get('document_name'))}` | `{before_text}` | `{after_text}` |"
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
        deterministic_notes = _align_swapped_node_bindings(path, payload)
        if deterministic_notes:
            deterministic_fixed.append(path.name)

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

        safe_to_strip = _is_stage_a_safe(violations, without_ref)
        if safe_to_strip:
            safe_docs.append(path.name)

        wrote_file = False
        stripped = False
        if apply_deterministic_fixes and deterministic_notes:
            _write_json(path, payload)
            wrote_file = True

        if strip_stage_a and safe_to_strip:
            strip_payload = payload if wrote_file else _read_json(path)
            if _strip_reference_metadata(strip_payload):
                _write_json(path, strip_payload)
                stripped = True
                stage_a_stripped.append(path.name)

        document_rows.append(
            {
                "document_name": path.name,
                "node_suffix": _node_suffix_from_path(path),
                "deterministic_fix_notes": deterministic_notes,
                "contract_violations": violations,
                "safe_to_strip": safe_to_strip,
                "stage_a_stripped": stripped,
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
        help="Write machine-readable report JSON to this path (single data-root runs).",
    )
    parser.add_argument(
        "--report-markdown",
        default="",
        help="Write markdown summary to this path (single data-root runs).",
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

    if len(reports) == 1:
        report = reports[0]
        if _as_text(args.report_json):
            _write_report_file(Path(args.report_json), json.dumps(report, indent=2, sort_keys=False) + "\n")
            print(f"Wrote JSON report: {args.report_json}")
        if _as_text(args.report_markdown):
            _write_report_file(Path(args.report_markdown), _markdown_summary(report))
            print(f"Wrote markdown report: {args.report_markdown}")
    elif _as_text(args.report_json) or _as_text(args.report_markdown):
        print("WARNING: --report-json/--report-markdown are only emitted automatically for single data-root runs.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
