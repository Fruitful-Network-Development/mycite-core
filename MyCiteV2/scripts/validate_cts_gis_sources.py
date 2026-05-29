from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.modules.cross_domain.cts_gis import (
    build_cts_gis_source_layout_summary,
    compiled_artifact_path,
    read_compiled_artifact,
    validate_compiled_artifact,
    validate_cts_gis_source_layout,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate CTS-GIS source layout and optional compiled-artifact freshness.")
    parser.add_argument("--data-dir", required=True, help="Path to portal data directory.")
    parser.add_argument("--private-dir", default="", help="Path to portal private directory (for MOS-backed source layout).")
    parser.add_argument("--scope-id", default="fnd", help="Portal scope id.")
    parser.add_argument(
        "--authority-db",
        default="",
        help="Path to mos_authority.sqlite3 (default: <private-dir>/mos_authority.sqlite3).",
    )
    parser.add_argument(
        "--require-compiled-match",
        action="store_true",
        help="Fail unless the compiled artifact exists and matches the current source fingerprint.",
    )
    args = parser.parse_args()

    # MOS-aware: the disk sandbox/cts-gis/sources/ tree was retired (2026-05-17);
    # resolve the authority DB so the source layout summarizes the MOS-backed docs.
    authority_db: Path | None = None
    if args.authority_db:
        authority_db = Path(args.authority_db)
    elif args.private_dir:
        authority_db = Path(args.private_dir) / "mos_authority.sqlite3"
    datum_store = (
        SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
        if authority_db is not None and authority_db.exists()
        else None
    )

    source_layout = build_cts_gis_source_layout_summary(
        args.data_dir, datum_store=datum_store, tenant_id=args.scope_id
    )
    source_layout_valid, source_layout_issues = validate_cts_gis_source_layout(source_layout)
    compiled_path = compiled_artifact_path(args.data_dir, portal_scope_id=args.scope_id)
    compiled_artifact = read_compiled_artifact(compiled_path)
    compiled_valid, compiled_issues = validate_compiled_artifact(
        compiled_artifact,
        expected_portal_scope_id=args.scope_id,
        expected_source_layout=source_layout,
    )

    payload = {
        "schema": "mycite.v2.portal.system.tools.cts_gis.validation.v1",
        "data_dir": args.data_dir,
        "scope_id": args.scope_id,
        "source_layout_valid": source_layout_valid,
        "source_layout_issues": source_layout_issues,
        "source_layout": source_layout,
        "compiled_artifact_path": str(compiled_path) if compiled_path is not None else "",
        "compiled_artifact_valid": compiled_valid,
        "compiled_artifact_issues": compiled_issues,
        "require_compiled_match": bool(args.require_compiled_match),
    }
    print(json.dumps(payload, indent=2))

    if not source_layout_valid:
        return 1
    if args.require_compiled_match and not compiled_valid:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
