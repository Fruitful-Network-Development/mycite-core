from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import build_portal_cts_gis_surface_bundle
from MyCiteV2.packages.modules.cross_domain.cts_gis import (
    build_compiled_artifact,
    build_cts_gis_source_layout_summary,
    compiled_artifact_path,
    validate_cts_gis_source_layout,
    write_compiled_artifact,
)
from MyCiteV2.packages.modules.cross_domain.cts_gis.contracts import CTS_GIS_RUNTIME_MODE_AUDIT_FORENSIC
from MyCiteV2.packages.state_machine.portal_shell import (
    CTS_GIS_TOOL_SURFACE_ID,
    PortalScope,
    initial_portal_shell_state,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile CTS-GIS artifact for production runtime.")
    parser.add_argument("--data-dir", required=True, help="Path to portal data directory.")
    parser.add_argument("--private-dir", default="", help="Path to portal private directory.")
    parser.add_argument("--scope-id", default="fnd", help="Portal scope id.")
    parser.add_argument("--output", default="", help="Optional explicit output path.")
    args = parser.parse_args()

    scope = PortalScope(scope_id=args.scope_id, capabilities=("datum_recognition", "spatial_projection"))
    shell_state = initial_portal_shell_state(surface_id=CTS_GIS_TOOL_SURFACE_ID, portal_scope=scope)
    bundle = build_portal_cts_gis_surface_bundle(
        portal_scope=scope,
        shell_state=shell_state,
        data_dir=args.data_dir,
        private_dir=args.private_dir or None,
        request_payload={"runtime_mode": CTS_GIS_RUNTIME_MODE_AUDIT_FORENSIC},
    )
    surface_payload = dict(bundle.get("surface_payload") or {})
    source_layout = build_cts_gis_source_layout_summary(args.data_dir)
    source_layout_valid, source_layout_issues = validate_cts_gis_source_layout(source_layout)
    if not source_layout_valid:
        print(
            json.dumps(
                {
                    "compiled_artifact_path": "",
                    "source_layout_valid": False,
                    "source_layout_issues": source_layout_issues,
                    "source_layout": source_layout,
                },
                indent=2,
            )
        )
        return 2
    artifact = build_compiled_artifact(
        portal_scope_id=args.scope_id,
        source_evidence=dict(surface_payload.get("source_evidence") or {}),
        service_surface=dict(surface_payload.get("service_surface") or {}),
        navigation_canvas=dict(surface_payload.get("navigation_model") or {}),
        default_tool_state=dict(surface_payload.get("tool_state") or {}),
        source_layout=source_layout,
        build_mode=CTS_GIS_RUNTIME_MODE_AUDIT_FORENSIC,
    )
    output_path = Path(args.output) if args.output else compiled_artifact_path(args.data_dir, portal_scope_id=args.scope_id)
    written = write_compiled_artifact(output_path, artifact)
    print(
        json.dumps(
            {
                "compiled_artifact_path": str(written) if written is not None else "",
                "schema": artifact.get("schema"),
                "source_layout_valid": True,
                "source_layout": source_layout,
                "invariants": artifact.get("invariants"),
                "strict_invariants": artifact.get("strict_invariants"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
