from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.scripts import repair_cts_gis_summit_sources as summit_repair
from MyCiteV2.scripts.cts_gis_geojson_hops_utils import (
    as_text,
    encode_hops_coordinate,
    read_json,
    reference_polygons_from_geojson,
    sha256_file,
    write_json,
)

DEFAULT_REFERENCE_ROOT = REPO_ROOT / "docs" / "personal_notes" / "CTS-GIS-prototype-mockup"
DEFAULT_MANIFEST_PATH = REPO_ROOT / "docs" / "audits" / "cts_gis_reference_manifest.json"
DEFAULT_REPORT_JSON = REPO_ROOT / "docs" / "audits" / "cts_gis_reference_repair_report.json"
DEFAULT_REPORT_MARKDOWN = REPO_ROOT / "docs" / "audits" / "cts_gis_reference_repair_report.md"
DEFAULT_DATA_ROOTS = [REPO_ROOT / "deployed" / "fnd" / "data"]
PROJECTION_GLOB = "sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77*.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "manifest_type": "cts_gis_reference_geojson_manifest",
            "generated_at_utc": _utc_now(),
            "entries": [],
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        entries = list(payload.get("entries") or [])
        payload["entries"] = [entry for entry in entries if isinstance(entry, dict)]
        return payload
    if isinstance(payload, list):
        return {
            "manifest_type": "cts_gis_reference_geojson_manifest",
            "generated_at_utc": _utc_now(),
            "entries": [entry for entry in payload if isinstance(entry, dict)],
        }
    raise ValueError(f"Unsupported manifest structure in {path}")


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _target_documents(data_roots: list[Path], *, node_filters: set[str] | None = None) -> list[Path]:
    documents: list[Path] = []
    for root in data_roots:
        source_dir = root / "sandbox" / "cts-gis" / "sources"
        if not source_dir.exists():
            continue
        documents.extend(path for path in sorted(source_dir.glob(PROJECTION_GLOB)) if path.is_file())
    deduped: dict[str, Path] = {}
    for path in documents:
        if node_filters:
            node_id = _node_id_from_source_name(path.name)
            if node_id not in node_filters:
                continue
        deduped[str(path)] = path
    return list(deduped.values())


def _node_id_from_source_name(name: str) -> str:
    if ".fnd." not in name or not name.endswith(".json"):
        return ""
    return name.split(".fnd.", 1)[1][:-5]


def _pick_reference_geojson(
    *,
    source_payload: dict[str, Any],
    node_id: str,
    reference_root: Path,
    manifest_entries: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str, str]:
    embedded = source_payload.get("reference_geojson")
    if isinstance(embedded, dict):
        return embedded, as_text(source_payload.get("reference_geojson_source")), ""

    for entry in manifest_entries:
        if as_text(entry.get("node_id")) != node_id:
            continue
        candidate = as_text(entry.get("reference_geojson_path"))
        if not candidate:
            continue
        path = Path(candidate)
        if not path.is_absolute():
            path = REPO_ROOT / candidate
        if path.exists():
            return read_json(path), as_text(entry.get("reference_geojson_source")) or str(path), str(path)

    direct = reference_root / f"{node_id}.geojson"
    if direct.exists():
        return read_json(direct), str(direct), str(direct)
    return None, "", ""


def _encode_reference_rows(reference_geojson: dict[str, Any]) -> dict[str, list[Any]]:
    polygons = reference_polygons_from_geojson(reference_geojson)
    if not polygons:
        raise ValueError("Reference GeoJSON does not carry Polygon or MultiPolygon geometry")

    row_space: dict[str, list[Any]] = {}
    ring_sequence = 0
    polygon_addresses: list[str] = []
    for polygon_index, polygon in enumerate(polygons, start=1):
        ring_addresses: list[str] = []
        for ring in polygon:
            ring_sequence += 1
            row_address = f"4-{len(ring)}-{ring_sequence}"
            row_tokens: list[str] = [row_address]
            for longitude, latitude in ring:
                row_tokens.extend(["rf.3-1-1", encode_hops_coordinate(longitude, latitude)])
            row_space[row_address] = [row_tokens, [f"polygon_{polygon_index}_ring_{ring_sequence}"]]
            ring_addresses.append(row_address)
        polygon_address = f"5-0-{polygon_index}"
        row_space[polygon_address] = [[polygon_address, "~", *ring_addresses], [f"polygon_{polygon_index}"]]
        polygon_addresses.append(polygon_address)

    row_space["6-0-1"] = [["6-0-1", "~", *polygon_addresses], ["boundary_collection"]]
    return row_space


def _update_seven_row(tokens: list[Any], node_id: str) -> list[Any]:
    updated = list(tokens)
    if not updated:
        return ["7-3-1", "rf.3-1-2", node_id, "6-0-1", "1"]
    updated[0] = "7-3-1"

    rf_indexes = [idx for idx, token in enumerate(updated[:-1]) if as_text(token) == "rf.3-1-2"]
    if rf_indexes:
        updated[rf_indexes[0] + 1] = node_id
    else:
        updated.extend(["rf.3-1-2", node_id])

    replaced = False
    for idx, token in enumerate(updated):
        if token == "~":
            continue
        family = as_text(token).split("-", 1)[0]
        if family in {"5", "6"} and as_text(token).count("-") == 2:
            updated[idx] = "6-0-1"
            replaced = True
            break
    if not replaced:
        if updated and as_text(updated[-1]) == "1":
            updated.insert(len(updated) - 1, "6-0-1")
        else:
            updated.extend(["6-0-1", "1"])
    return updated


def _rebuild_source_payload(
    *,
    source_payload: dict[str, Any],
    node_id: str,
    reference_geojson: dict[str, Any],
    reference_geojson_source: str,
) -> dict[str, Any]:
    old_space = dict(source_payload.get("datum_addressing_abstraction_space") or {})
    seven_row = old_space.get("7-3-1")
    old_seven_tokens: list[Any] = []
    old_seven_labels: list[Any] = []
    if isinstance(seven_row, list) and seven_row:
        old_seven_tokens = list(seven_row[0]) if isinstance(seven_row[0], list) else list(seven_row)
        if len(seven_row) > 1 and isinstance(seven_row[1], list):
            old_seven_labels = list(seven_row[1])

    preserved = {
        address: value
        for address, value in old_space.items()
        if not as_text(address).startswith(("4-", "5-", "6-", "7-"))
    }
    rebuilt = _encode_reference_rows(reference_geojson)
    rebuilt["7-3-1"] = [_update_seven_row(old_seven_tokens, node_id), old_seven_labels or [f"node_{node_id}"]]

    merged_space = {**preserved, **rebuilt}
    out = dict(source_payload)
    out["datum_addressing_abstraction_space"] = merged_space
    out["reference_geojson"] = reference_geojson
    out["reference_geojson_source"] = reference_geojson_source
    out["reference_geojson_node_id"] = node_id
    return out


def _findings_for(path: Path, payload: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    return (
        summit_repair._contract_violations(path, payload),
        summit_repair._reference_geometry_findings(path, payload),
    )


def _entry_sort_key(entry: dict[str, Any]) -> tuple[str, str]:
    return as_text(entry.get("node_id")), as_text(entry.get("source_profile"))


def _markdown_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# CTS-GIS Reference GeoJSON Repair Report")
    lines.append("")
    lines.append(f"- Generated: `{as_text(report.get('generated_at_utc'))}`")
    lines.append(f"- Dry run: `{as_text(report.get('dry_run'))}`")
    lines.append(f"- Documents reviewed: `{len(list(report.get('documents') or []))}`")
    lines.append(f"- Documents repaired: `{int(report.get('repaired_count') or 0)}`")
    lines.append("")
    lines.append("| Source | Node | Status | Before Issues | After Issues |")
    lines.append("| --- | --- | --- | --- | --- |")
    for row in list(report.get("documents") or []):
        before_types = ", ".join(list(row.get("before_issue_types") or [])) or "none"
        after_types = ", ".join(list(row.get("after_issue_types") or [])) or "none"
        lines.append(
            f"| `{as_text(row.get('source_profile'))}` | `{as_text(row.get('node_id'))}` | "
            f"`{as_text(row.get('status'))}` | `{before_types}` | `{after_types}` |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Repair CTS-GIS source profiles from vetted reference GeoJSON with deterministic HOPS regeneration."
    )
    parser.add_argument(
        "--data-root",
        action="append",
        default=[],
        help="Authoritative data root containing sandbox/cts-gis sources. May be passed multiple times.",
    )
    parser.add_argument(
        "--reference-root",
        default=str(DEFAULT_REFERENCE_ROOT),
        help="Directory containing reference GeoJSON inputs.",
    )
    parser.add_argument(
        "--manifest-path",
        default=str(DEFAULT_MANIFEST_PATH),
        help="Manifest output path tracking approved references and checksums.",
    )
    parser.add_argument(
        "--report-json",
        default=str(DEFAULT_REPORT_JSON),
        help="JSON report output path.",
    )
    parser.add_argument(
        "--report-markdown",
        default=str(DEFAULT_REPORT_MARKDOWN),
        help="Markdown report output path.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply repairs to source profiles. Without this flag, runs in dry-run mode.",
    )
    parser.add_argument(
        "--node-id",
        action="append",
        default=[],
        help="Optional node id filter. May be passed multiple times for controlled batches.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    data_roots = [Path(item) for item in (args.data_root or [])] or list(DEFAULT_DATA_ROOTS)
    reference_root = Path(args.reference_root)
    manifest_path = Path(args.manifest_path)
    report_json_path = Path(args.report_json)
    report_markdown_path = Path(args.report_markdown)
    apply_repairs = bool(args.apply)
    node_filters = {as_text(node_id) for node_id in list(args.node_id or []) if as_text(node_id)}

    manifest = _read_manifest(manifest_path)
    entries = list(manifest.get("entries") or [])
    documents = _target_documents(data_roots, node_filters=node_filters if node_filters else None)
    report_rows: list[dict[str, Any]] = []
    repaired_count = 0

    for source_path in documents:
        source_payload = read_json(source_path)
        node_id = _node_id_from_source_name(source_path.name)
        reference_geojson, reference_geojson_source, reference_geojson_path = _pick_reference_geojson(
            source_payload=source_payload,
            node_id=node_id,
            reference_root=reference_root,
            manifest_entries=entries,
        )
        if not isinstance(reference_geojson, dict):
            report_rows.append(
                {
                    "source_profile": source_path.name,
                    "node_id": node_id,
                    "status": "skipped_missing_reference",
                    "before_issue_types": [],
                    "after_issue_types": [],
                }
            )
            continue

        before_contract, before_findings = _findings_for(source_path, source_payload)
        before_issue_types = sorted(
            {entry.get("issue_type") for entry in before_findings if as_text(entry.get("issue_type"))}
            | {"contract_violation" for _ in before_contract}
        )

        rebuilt_payload = _rebuild_source_payload(
            source_payload=source_payload,
            node_id=node_id,
            reference_geojson=reference_geojson,
            reference_geojson_source=reference_geojson_source or as_text(source_payload.get("reference_geojson_source")),
        )
        after_contract, after_findings = _findings_for(source_path, rebuilt_payload)
        after_issue_types = sorted(
            {entry.get("issue_type") for entry in after_findings if as_text(entry.get("issue_type"))}
            | {"contract_violation" for _ in after_contract}
        )

        status = "dry_run_candidate"
        if apply_repairs:
            write_json(source_path, rebuilt_payload)
            status = "repaired"
            repaired_count += 1

        entries.append(
            {
                "node_id": node_id,
                "source_profile": source_path.name,
                "source_profile_path": str(source_path),
                "reference_geojson_source": reference_geojson_source,
                "reference_geojson_path": reference_geojson_path,
                "reference_geojson_sha256": sha256_file(Path(reference_geojson_path))
                if reference_geojson_path and Path(reference_geojson_path).exists()
                else "",
                "status": status,
                "before_issue_types": before_issue_types,
                "after_issue_types": after_issue_types,
                "checked_at_utc": _utc_now(),
            }
        )

        report_rows.append(
            {
                "source_profile": source_path.name,
                "node_id": node_id,
                "status": status,
                "before_issue_types": before_issue_types,
                "after_issue_types": after_issue_types,
            }
        )

    deduped_entries = sorted(
        {
            (as_text(entry.get("node_id")), as_text(entry.get("source_profile"))): entry
            for entry in entries
            if as_text(entry.get("node_id")) and as_text(entry.get("source_profile"))
        }.values(),
        key=_entry_sort_key,
    )
    manifest["generated_at_utc"] = _utc_now()
    manifest["entries"] = deduped_entries
    _write_manifest(manifest_path, manifest)

    report = {
        "report_type": "cts_gis_reference_geojson_repair",
        "generated_at_utc": _utc_now(),
        "dry_run": not apply_repairs,
        "node_filters": sorted(node_filters),
        "repaired_count": repaired_count,
        "documents": report_rows,
    }
    report_json_path.parent.mkdir(parents=True, exist_ok=True)
    report_json_path.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    report_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    report_markdown_path.write_text(_markdown_report(report), encoding="utf-8")

    print(f"Reviewed {len(report_rows)} source profiles")
    print(f"Repairs applied: {repaired_count}")
    print(f"Wrote manifest: {manifest_path}")
    print(f"Wrote report JSON: {report_json_path}")
    print(f"Wrote report markdown: {report_markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
