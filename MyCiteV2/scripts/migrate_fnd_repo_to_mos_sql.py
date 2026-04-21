from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.runtime_platform import build_tool_exposure_policy
from MyCiteV2.packages.adapters.filesystem import FilesystemSystemDatumStoreAdapter
from MyCiteV2.packages.adapters.sql import (
    SqliteAuditLogAdapter,
    SqliteDirectiveContextAdapter,
    SqlitePortalAuthorityAdapter,
    SqliteSystemDatumStoreAdapter,
)
from MyCiteV2.packages.adapters.sql._sqlite import open_sqlite
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocumentRequest,
    PublicationTenantSummaryResult,
    PublicationTenantSummarySource,
    PublicationTenantSummaryRequest,
    SystemDatumStoreRequest,
)
from MyCiteV2.packages.ports.portal_authority import PortalAuthoritySource
from MyCiteV2.packages.state_machine.portal_shell import build_portal_tool_registry_entries


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _default_capabilities(portal_instance_id: str) -> list[str]:
    capabilities = ["datum_recognition", "spatial_projection"]
    if _as_text(portal_instance_id).lower() == "fnd":
        capabilities.extend(["fnd_peripheral_routing", "hosted_site_manifest_visibility", "hosted_site_visibility"])
    return capabilities


def classify_data_path(relative_path: str) -> str:
    rel = _as_text(relative_path)
    if rel == "system/anthology.json":
        return "authoritative_import"
    if rel.startswith("sandbox/") and "/sources/" in rel and rel.endswith(".json"):
        return "authoritative_import"
    if rel.startswith("sandbox/") and rel.endswith(".json") and "/sources/" not in rel:
        name = Path(rel).name
        if name.startswith("tool") or name == "tool.json":
            return "supporting_anchor_context"
    if rel == "system/system_log.json":
        return "derived_materialization"
    if rel.startswith("system/sources/") and rel.endswith(".json"):
        return "derived_materialization"
    if rel.startswith("payloads/cache/") and rel.endswith(".json"):
        return "derived_materialization"
    return "explicit_exception"


def build_portal_authority_source(
    *,
    tenant_id: str,
    portal_config: dict[str, Any],
) -> PortalAuthoritySource:
    known_tool_ids = [entry.tool_id for entry in build_portal_tool_registry_entries()]
    policy = build_tool_exposure_policy(
        portal_config.get("tool_exposure"),
        known_tool_ids=known_tool_ids,
    )
    configured_tools = dict(policy.get("configured_tools") or {})
    enabled_tools = dict(policy.get("enabled_tools") or {})
    configured_tools["workbench_ui"] = True
    enabled_tools["workbench_ui"] = True
    configured_tool_ids = [tool_id for tool_id in known_tool_ids if configured_tools.get(tool_id) is True]
    enabled_tool_ids = [tool_id for tool_id in known_tool_ids if enabled_tools.get(tool_id) is True]
    disabled_tool_ids = [tool_id for tool_id in known_tool_ids if configured_tools.get(tool_id) and not enabled_tools.get(tool_id)]
    missing_tool_ids = [tool_id for tool_id in known_tool_ids if tool_id not in configured_tools]
    policy.update(
        {
            "configured_tools": configured_tools,
            "enabled_tools": enabled_tools,
            "configured_tool_ids": configured_tool_ids,
            "enabled_tool_ids": enabled_tool_ids,
            "disabled_tool_ids": disabled_tool_ids,
            "missing_tool_ids": missing_tool_ids,
            "policy_source": "mos_sql_cutover_migration",
        }
    )
    return PortalAuthoritySource(
        scope_id=tenant_id,
        capabilities=_default_capabilities(tenant_id),
        tool_exposure_policy=policy,
        ownership_posture="portal_instance",
    )


def _load_directive_manifest(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    return _read_json_object(path)


def _fallback_publication_summary(
    *,
    public_dir: Path,
    tenant_id: str,
    tenant_domain: str,
) -> PublicationTenantSummaryResult | None:
    tenant_profiles = sorted(public_dir.glob(f"{tenant_id}-*.json"))
    candidates: list[PublicationTenantSummaryResult] = []
    for tenant_profile_path in tenant_profiles:
        profile_id = tenant_profile_path.stem[len(f"{tenant_id}-") :]
        public_profile_path = public_dir / f"{profile_id}.json"
        if not public_profile_path.exists():
            continue
        try:
            public_profile = _read_json_object(public_profile_path)
            tenant_profile = _read_json_object(tenant_profile_path)
        except Exception:
            continue
        candidates.append(
            PublicationTenantSummaryResult(
                source=PublicationTenantSummarySource(
                    tenant_id=tenant_id,
                    tenant_domain=tenant_domain,
                    profile_id=profile_id,
                    public_profile=public_profile,
                    tenant_profile=tenant_profile,
                ),
                resolution_status={
                    "anthology": "loaded",
                    "domain_match": "fallback_public_dir_pair",
                    "public_profile": "loaded",
                    "tenant_profile": "loaded",
                },
                warnings=("publication_summary_fallback_from_public_dir",),
            )
        )
    if len(candidates) == 1:
        return candidates[0]
    return None


def _classified_inventory(data_root: Path) -> dict[str, list[str]]:
    inventory = {
        "authoritative_import": [],
        "supporting_anchor_context": [],
        "derived_materialization": [],
        "explicit_exception": [],
    }
    for path in sorted(data_root.rglob("*")):
        if not path.is_file():
            continue
        relative_path = path.relative_to(data_root).as_posix()
        inventory[classify_data_path(relative_path)].append(relative_path)
    return inventory


def _external_exception_scope(data_root: Path, portal_config_path: Path) -> list[dict[str, str]]:
    root = data_root.parent
    retained: list[dict[str, str]] = []
    for candidate in [root / "public", root / "build.json"]:
        if not candidate.exists():
            continue
        retained.append(
            {
                "path": str(candidate.relative_to(root.parent)),
                "reason": "host_bound_or_public_asset",
            }
        )
    for candidate in sorted((root / "private").glob("*")):
        if candidate == portal_config_path:
            continue
        retained.append(
            {
                "path": str(candidate.relative_to(root.parent)),
                "reason": "retained_private_scope_without_dedicated_port",
            }
        )
    return retained


def run_migration(
    *,
    data_root: Path,
    portal_config_path: Path,
    authority_db_file: Path,
    tenant_id: str,
    tenant_domain: str,
    apply: bool,
    directive_context_manifest: Path | None = None,
    audit_storage_file: Path | None = None,
) -> dict[str, Any]:
    inventory = _classified_inventory(data_root)
    portal_config = _read_json_object(portal_config_path)
    public_dir = data_root.parent / "public"
    filesystem = FilesystemSystemDatumStoreAdapter(data_root, public_dir=public_dir if public_dir.exists() else None)
    authoritative_catalog = filesystem.read_authoritative_datum_documents(
        AuthoritativeDatumDocumentRequest(tenant_id=tenant_id)
    )
    system_workbench = filesystem.read_system_resource_workbench(SystemDatumStoreRequest(tenant_id=tenant_id))
    publication_summary = filesystem.read_publication_tenant_summary(
        PublicationTenantSummaryRequest(tenant_id=tenant_id, tenant_domain=tenant_domain)
    )
    if publication_summary.source is None and public_dir.exists():
        fallback_summary = _fallback_publication_summary(
            public_dir=public_dir,
            tenant_id=tenant_id,
            tenant_domain=tenant_domain,
        )
        if fallback_summary is not None:
            publication_summary = fallback_summary
    directive_manifest = _load_directive_manifest(directive_context_manifest)

    report: dict[str, Any] = {
        "tenant_id": tenant_id,
        "tenant_domain": tenant_domain,
        "authority_db_file": str(authority_db_file),
        "mode": "apply" if apply else "dry_run",
        "inventory": {
            bucket: {
                "count": len(paths),
                "paths": list(paths),
            }
            for bucket, paths in inventory.items()
        },
        "external_retained_scope": _external_exception_scope(data_root, portal_config_path),
        "import_summary": {
            "document_count": len(authoritative_catalog.documents),
            "document_ids": [document.document_id for document in authoritative_catalog.documents],
            "row_count": sum(document.row_count for document in authoritative_catalog.documents),
            "anchor_row_count": sum(document.anchor_row_count for document in authoritative_catalog.documents),
            "supporting_anchor_context_count": len(inventory["supporting_anchor_context"]),
            "derived_materialization_count": len(inventory["derived_materialization"]),
            "explicit_exception_count": len(inventory["explicit_exception"]),
        },
        "documents": [
            {
                "document_id": document.document_id,
                "source_kind": document.source_kind,
                "relative_path": document.relative_path,
                "row_count": document.row_count,
                "anchor_row_count": document.anchor_row_count,
                "warnings": list(document.warnings),
            }
            for document in authoritative_catalog.documents
        ],
        "directive_context": {
            "manifest_supplied": directive_context_manifest is not None,
            "snapshot_count": len(list(directive_manifest.get("snapshots") or [])),
            "event_count": len(list(directive_manifest.get("events") or [])),
            "policy": "explicit_manifest_only",
        },
        "audit_import": {
            "source": str(audit_storage_file) if audit_storage_file is not None else "",
            "requested": audit_storage_file is not None,
        },
        "publication_summary": {
            "present": publication_summary.source is not None,
            "warnings": list(publication_summary.warnings),
            "resolution_status": dict(publication_summary.resolution_status),
        },
        "sql_verification": {},
        "failures": [],
    }

    if not apply:
        report["directive_context"]["event_imported"] = 0
        report["audit_import"]["imported_records"] = 0
        report["directive_context"]["note"] = (
            "No canonical shared directive overlays were imported because no apply step was requested."
            if directive_context_manifest is None
            else "Manifest recognized during dry-run; import deferred."
        )
        return report

    datum_store = SqliteSystemDatumStoreAdapter(authority_db_file)
    datum_store.store_authoritative_catalog(authoritative_catalog)
    datum_store.store_system_workbench(system_workbench)
    datum_store.store_publication_summary(publication_summary, tenant_id=tenant_id, tenant_domain=tenant_domain)
    SqlitePortalAuthorityAdapter(authority_db_file).store_portal_authority(
        build_portal_authority_source(tenant_id=tenant_id, portal_config=portal_config)
    )

    directive_adapter = SqliteDirectiveContextAdapter(authority_db_file)
    imported_snapshots = 0
    imported_events = 0
    if directive_context_manifest is not None:
        for snapshot in list(directive_manifest.get("snapshots") or []):
            directive_adapter.store_directive_context(snapshot)
            imported_snapshots += 1
        for event in list(directive_manifest.get("events") or []):
            directive_adapter.append_directive_context_event(event)
            imported_events += 1
        report["directive_context"]["note"] = "Directive context imported from explicit normalized manifest."
    else:
        report["directive_context"]["note"] = (
            "No canonical shared directive overlays were imported because no explicit migration manifest was supplied."
        )
    report["directive_context"]["snapshot_imported"] = imported_snapshots
    report["directive_context"]["event_imported"] = imported_events

    imported_audit_records = 0
    if audit_storage_file is not None:
        SqliteAuditLogAdapter(authority_db_file).bootstrap_from_filesystem(audit_storage_file)
    with open_sqlite(authority_db_file) as connection:
        imported_audit_records = int(
            connection.execute("SELECT COUNT(*) AS count FROM audit_records").fetchone()["count"]
        )
        document_semantics_count = int(
            connection.execute(
                "SELECT COUNT(*) AS count FROM datum_document_semantics WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchone()["count"]
        )
        row_semantics_count = int(
            connection.execute(
                "SELECT COUNT(*) AS count FROM datum_row_semantics WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchone()["count"]
        )
        portal_authority_count = int(
            connection.execute(
                "SELECT COUNT(*) AS count FROM portal_authority_snapshots WHERE scope_id = ?",
                (tenant_id,),
            ).fetchone()["count"]
        )
        directive_snapshot_count = int(
            connection.execute(
                "SELECT COUNT(*) AS count FROM directive_context_snapshots WHERE portal_instance_id = ?",
                (tenant_id,),
            ).fetchone()["count"]
        )
        directive_event_count = int(
            connection.execute(
                "SELECT COUNT(*) AS count FROM directive_context_events WHERE portal_instance_id = ?",
                (tenant_id,),
            ).fetchone()["count"]
        )
    expected_row_count = report["import_summary"]["row_count"]
    failures: list[str] = []
    if publication_summary.source is None:
        failures.append("publication_summary_missing")
    if document_semantics_count != report["import_summary"]["document_count"]:
        failures.append("document_semantics_count_mismatch")
    if row_semantics_count != expected_row_count:
        failures.append("row_semantics_count_mismatch")
    if portal_authority_count != 1:
        failures.append("portal_authority_missing")
    report["audit_import"]["imported_records"] = imported_audit_records
    report["sql_verification"] = {
        "document_semantics_count": document_semantics_count,
        "row_semantics_count": row_semantics_count,
        "portal_authority_count": portal_authority_count,
        "directive_snapshot_count": directive_snapshot_count,
        "directive_event_count": directive_event_count,
        "expected_document_count": report["import_summary"]["document_count"],
        "expected_row_count": expected_row_count,
    }
    explicit_exception_rows = len(inventory["explicit_exception"])
    report["coverage_gate"] = {
        "status": "passed" if not failures else "failed",
        "rule": "Every datum row must be present in SQL semantics or listed in the exception manifest with a reason.",
        "explicit_exception_count": explicit_exception_rows,
    }
    report["failures"] = failures
    return report


def render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# MOS FND SQL Ingestion Report",
        "",
        f"- `tenant_id`: `{report['tenant_id']}`",
        f"- `tenant_domain`: `{report['tenant_domain']}`",
        f"- `mode`: `{report['mode']}`",
        f"- `authority_db_file`: `{report['authority_db_file']}`",
        "",
        "## Inventory",
        "",
    ]
    for bucket, entry in report["inventory"].items():
        lines.append(f"- `{bucket}`: {entry['count']}")
    lines.extend(
        [
            "",
            "## Import Summary",
            "",
            f"- `document_count`: {report['import_summary']['document_count']}",
            f"- `row_count`: {report['import_summary']['row_count']}",
            f"- `anchor_row_count`: {report['import_summary']['anchor_row_count']}",
            f"- `supporting_anchor_context_count`: {report['import_summary']['supporting_anchor_context_count']}",
            f"- `derived_materialization_count`: {report['import_summary']['derived_materialization_count']}",
            f"- `explicit_exception_count`: {report['import_summary']['explicit_exception_count']}",
            "",
            "## Directive Context",
            "",
            f"- `manifest_supplied`: {report['directive_context']['manifest_supplied']}",
            f"- `snapshot_imported`: {report['directive_context'].get('snapshot_imported', 0)}",
            f"- `event_imported`: {report['directive_context'].get('event_imported', 0)}",
            f"- note: {report['directive_context']['note']}",
            "",
            "## SQL Verification",
            "",
        ]
    )
    for key, value in report.get("sql_verification", {}).items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Coverage Gate",
            "",
            f"- `status`: {report['coverage_gate']['status'] if 'coverage_gate' in report else 'dry_run'}",
            f"- rule: {report.get('coverage_gate', {}).get('rule', 'not_evaluated')}",
            "",
            "## External Retained Scope",
            "",
        ]
    )
    for item in report.get("external_retained_scope", []):
        lines.append(f"- `{item['path']}`: {item['reason']}")
    lines.extend(
        [
            "",
            "## Failures",
            "",
        ]
    )
    failures = list(report.get("failures") or [])
    if failures:
        for item in failures:
            lines.append(f"- `{item}`")
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate an FND repo copy into the MOS SQL authority database.")
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--portal-config", required=True)
    parser.add_argument("--authority-db", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--tenant-domain", required=True)
    parser.add_argument("--report-json", required=True)
    parser.add_argument("--report-markdown", required=True)
    parser.add_argument("--directive-context-manifest")
    parser.add_argument("--audit-storage-file")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_migration(
        data_root=Path(args.data_root),
        portal_config_path=Path(args.portal_config),
        authority_db_file=Path(args.authority_db),
        tenant_id=_as_text(args.tenant_id).lower(),
        tenant_domain=_as_text(args.tenant_domain).lower(),
        apply=bool(args.apply),
        directive_context_manifest=Path(args.directive_context_manifest) if args.directive_context_manifest else None,
        audit_storage_file=Path(args.audit_storage_file) if args.audit_storage_file else None,
    )
    report_json_path = Path(args.report_json)
    report_json_path.parent.mkdir(parents=True, exist_ok=True)
    report_json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_markdown_path = Path(args.report_markdown)
    report_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    report_markdown_path.write_text(render_markdown_report(report), encoding="utf-8")
    return 0 if not report.get("failures") else 1


if __name__ == "__main__":
    raise SystemExit(main())
