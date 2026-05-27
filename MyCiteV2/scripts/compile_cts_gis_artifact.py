"""Recompile the CTS-GIS production artifact (cts_gis.<scope>.compiled.json).

The compile is driven by ``build_portal_cts_gis_surface_bundle`` with
``force_live_read=True``: that bypasses the compiled-artifact fast path AND the
stale-artifact fallback (both gated on ``not force_live_read``), takes the live
path (``_read_live_service_surface`` + ``_build_source_evidence``, which
reconstructs the SAMRAS seed from MOS SQL), and PERSISTS the result to the
served ``compiled_path`` itself (runtime line ~4391). The bake now includes
``admin_profile_static`` (identity + SD-31 district outline geometry) and
``district_profile_static`` (84-member list), sourced disk-first then from MOS.

This script is a SAFE wrapper around that write:
  1. back up the current served artifact,
  2. run the bundle (which writes the served compiled_path),
  3. validate the freshly-written artifact (decode_state ready + profile_static),
  4. with ``--output``: copy the new artifact there and RESTORE the served path
     (a non-destructive dry-run); without it: keep on success, ROLL BACK on regression.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import (
    build_portal_cts_gis_surface_bundle,
)
from MyCiteV2.packages.modules.cross_domain.cts_gis import compiled_artifact_path
from MyCiteV2.packages.modules.cross_domain.cts_gis.contracts import (
    CTS_GIS_RUNTIME_MODE_AUDIT_FORENSIC,
)
from MyCiteV2.packages.state_machine.portal_shell import (
    CTS_GIS_TOOL_SURFACE_ID,
    PortalScope,
    initial_portal_shell_state,
)


def _validate_artifact(artifact: dict) -> tuple[bool, list[str]]:
    """Gate the freshly-compiled artifact. Returns (ok, issues)."""
    issues: list[str] = []
    decode_state = (artifact.get("navigation_model") or {}).get("decode_state")
    if decode_state != "ready":
        issues.append(f"navigation_decode_state:{decode_state}")
    admin = artifact.get("admin_profile_static") or {}
    if not admin.get("node_id"):
        issues.append("admin_profile_static_missing")
    elif int((admin.get("geospatial_projection") or {}).get("feature_count") or 0) < 1:
        issues.append("admin_geospatial_empty")
    district = artifact.get("district_profile_static") or {}
    if int(district.get("member_count") or 0) < 1:
        issues.append("district_profile_static_missing")
    return (not issues, issues)


def _artifact_summary(artifact: dict) -> dict:
    admin = artifact.get("admin_profile_static") or {}
    district = artifact.get("district_profile_static") or {}
    return {
        "generated_at": artifact.get("generated_at"),
        "source_layout_backend": (artifact.get("source_layout") or {}).get("source_backend"),
        "navigation_decode_state": (artifact.get("navigation_model") or {}).get("decode_state"),
        "admin_profile_static": {
            "node_id": admin.get("node_id"),
            "label": admin.get("label"),
            "capital_msn_id": admin.get("capital_msn_id"),
            "feature_count": (admin.get("geospatial_projection") or {}).get("feature_count"),
        }
        if admin
        else None,
        "district_profile_static": {
            "collection_id": district.get("collection_id"),
            "member_count": district.get("member_count"),
        }
        if district
        else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Recompile the CTS-GIS production artifact.")
    parser.add_argument("--data-dir", required=True, help="Path to portal data directory.")
    parser.add_argument("--private-dir", default="", help="Path to portal private directory.")
    parser.add_argument("--scope-id", default="fnd", help="Portal scope id.")
    parser.add_argument(
        "--output",
        default="",
        help="Dry-run: write the recompiled artifact here and RESTORE the served path "
        "(served artifact left untouched). Without this flag the served path is updated in place.",
    )
    parser.add_argument(
        "--authority-db",
        default="",
        help="Path to mos_authority.sqlite3 (default: <private-dir>/mos_authority.sqlite3).",
    )
    args = parser.parse_args()

    authority_db: Path | None = None
    if args.authority_db:
        authority_db = Path(args.authority_db)
    elif args.private_dir:
        authority_db = Path(args.private_dir) / "mos_authority.sqlite3"

    served_path = compiled_artifact_path(args.data_dir, portal_scope_id=args.scope_id)
    backup_path = served_path.with_suffix(served_path.suffix + ".compile-prev.bak") if served_path else None
    pre_existed = served_path is not None and served_path.exists()
    if pre_existed and backup_path is not None:
        shutil.copy2(served_path, backup_path)

    scope = PortalScope(scope_id=args.scope_id, capabilities=("datum_recognition", "spatial_projection"))
    shell_state = initial_portal_shell_state(surface_id=CTS_GIS_TOOL_SURFACE_ID, portal_scope=scope)
    # force_live_read → live decode + persist to served_path (with profile_static).
    build_portal_cts_gis_surface_bundle(
        portal_scope=scope,
        shell_state=shell_state,
        data_dir=args.data_dir,
        authority_db_file=str(authority_db) if authority_db is not None else None,
        private_dir=args.private_dir or None,
        request_payload={
            "runtime_mode": CTS_GIS_RUNTIME_MODE_AUDIT_FORENSIC,
            "force_live_read": True,
        },
    )

    if served_path is None or not served_path.exists():
        print(json.dumps({"compiled": False, "reason": "bundle_did_not_write_artifact"}, indent=2))
        return 2
    artifact = json.loads(served_path.read_text())
    ok, issues = _validate_artifact(artifact)
    summary = _artifact_summary(artifact)

    result: dict = {"compiled": ok, "validation_issues": issues, "summary": summary}
    if args.output:
        # Dry-run: stash the freshly-written artifact and restore the served path.
        shutil.copy2(served_path, args.output)
        result["mode"] = "dry_run"
        result["output_path"] = args.output
        if pre_existed and backup_path is not None:
            shutil.copy2(backup_path, served_path)
            result["served_path_restored"] = True
        elif not pre_existed:
            served_path.unlink(missing_ok=True)
            result["served_path_restored"] = True
    else:
        result["mode"] = "in_place"
        result["compiled_artifact_path"] = str(served_path)
        if not ok:
            # Regression — roll the served path back to the pre-compile backup.
            if pre_existed and backup_path is not None:
                shutil.copy2(backup_path, served_path)
                result["rolled_back"] = True
            else:
                result["rolled_back"] = False

    if backup_path is not None and backup_path.exists():
        backup_path.unlink(missing_ok=True)
    print(json.dumps(result, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
