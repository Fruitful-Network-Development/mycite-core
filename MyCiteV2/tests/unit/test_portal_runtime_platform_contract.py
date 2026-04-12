from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.runtime_platform import (
    BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
    BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
    TRUSTED_TENANT_AUDIT_ACTIVITY_ENTRYPOINT_ID,
    TRUSTED_TENANT_AUDIT_ACTIVITY_SURFACE_SCHEMA,
    TRUSTED_TENANT_HOME_SURFACE_SCHEMA,
    TRUSTED_TENANT_OPERATIONAL_STATUS_ENTRYPOINT_ID,
    TRUSTED_TENANT_OPERATIONAL_STATUS_SURFACE_SCHEMA,
    TRUSTED_TENANT_PORTAL_ENTRYPOINT_ID,
    TRUSTED_TENANT_RUNTIME_ENVELOPE_SCHEMA,
    TRUSTED_TENANT_RUNTIME_ENTRYPOINT_DESCRIPTOR_SCHEMA,
    TRUSTED_TENANT_RUNTIME_REQUIRED_ENVELOPE_KEYS,
    build_trusted_tenant_runtime_envelope,
    build_trusted_tenant_runtime_entrypoint_catalog,
    build_trusted_tenant_runtime_error,
    resolve_trusted_tenant_runtime_entrypoint,
)


class PortalRuntimePlatformContractTests(unittest.TestCase):
    def test_trusted_tenant_entrypoint_catalog_is_static_and_serializable(self) -> None:
        descriptors = [entry.to_dict() for entry in build_trusted_tenant_runtime_entrypoint_catalog()]

        self.assertEqual(
            [entry["schema"] for entry in descriptors],
            [
                TRUSTED_TENANT_RUNTIME_ENTRYPOINT_DESCRIPTOR_SCHEMA,
                TRUSTED_TENANT_RUNTIME_ENTRYPOINT_DESCRIPTOR_SCHEMA,
                TRUSTED_TENANT_RUNTIME_ENTRYPOINT_DESCRIPTOR_SCHEMA,
            ],
        )
        self.assertEqual(
            descriptors,
            [
                {
                    "schema": TRUSTED_TENANT_RUNTIME_ENTRYPOINT_DESCRIPTOR_SCHEMA,
                    "entrypoint_id": TRUSTED_TENANT_PORTAL_ENTRYPOINT_ID,
                    "callable_path": "MyCiteV2.instances._shared.runtime.tenant_portal_runtime.run_trusted_tenant_portal_home",
                    "slice_id": "band1.portal_home_tenant_status",
                    "rollout_band": "Band 1 Trusted-Tenant Read-Only",
                    "exposure_status": "trusted-tenant-read-only",
                    "read_write_posture": "read-only",
                    "launch_contract": "admin-shell-entry",
                    "surface_pattern": "tenant-home",
                    "surface_schema": TRUSTED_TENANT_HOME_SURFACE_SCHEMA,
                    "required_configuration": ["data_dir", "public_dir", "tenant_domain"],
                },
                {
                    "schema": TRUSTED_TENANT_RUNTIME_ENTRYPOINT_DESCRIPTOR_SCHEMA,
                    "entrypoint_id": TRUSTED_TENANT_OPERATIONAL_STATUS_ENTRYPOINT_ID,
                    "callable_path": (
                        "MyCiteV2.instances._shared.runtime.tenant_operational_status_runtime."
                        "run_trusted_tenant_operational_status"
                    ),
                    "slice_id": BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
                    "rollout_band": "Band 1 Trusted-Tenant Read-Only",
                    "exposure_status": "trusted-tenant-read-only",
                    "read_write_posture": "read-only",
                    "launch_contract": "admin-shell-entry",
                    "surface_pattern": "tenant-operational-status",
                    "surface_schema": TRUSTED_TENANT_OPERATIONAL_STATUS_SURFACE_SCHEMA,
                    "required_configuration": ["audit_storage_file"],
                },
                {
                    "schema": TRUSTED_TENANT_RUNTIME_ENTRYPOINT_DESCRIPTOR_SCHEMA,
                    "entrypoint_id": TRUSTED_TENANT_AUDIT_ACTIVITY_ENTRYPOINT_ID,
                    "callable_path": (
                        "MyCiteV2.instances._shared.runtime.tenant_audit_activity_runtime."
                        "run_trusted_tenant_audit_activity"
                    ),
                    "slice_id": BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
                    "rollout_band": "Band 1 Trusted-Tenant Read-Only",
                    "exposure_status": "trusted-tenant-read-only",
                    "read_write_posture": "read-only",
                    "launch_contract": "admin-shell-entry",
                    "surface_pattern": "tenant-audit-activity",
                    "surface_schema": TRUSTED_TENANT_AUDIT_ACTIVITY_SURFACE_SCHEMA,
                    "required_configuration": ["audit_storage_file"],
                },
            ],
        )
        self.assertEqual(json.loads(json.dumps(descriptors, sort_keys=True)), descriptors)
        self.assertIsNone(resolve_trusted_tenant_runtime_entrypoint("missing.entrypoint"))
        self.assertEqual(
            resolve_trusted_tenant_runtime_entrypoint(TRUSTED_TENANT_PORTAL_ENTRYPOINT_ID).entrypoint_id,
            TRUSTED_TENANT_PORTAL_ENTRYPOINT_ID,
        )
        self.assertEqual(
            resolve_trusted_tenant_runtime_entrypoint(
                TRUSTED_TENANT_OPERATIONAL_STATUS_ENTRYPOINT_ID
            ).entrypoint_id,
            TRUSTED_TENANT_OPERATIONAL_STATUS_ENTRYPOINT_ID,
        )
        self.assertEqual(
            resolve_trusted_tenant_runtime_entrypoint(
                TRUSTED_TENANT_AUDIT_ACTIVITY_ENTRYPOINT_ID
            ).entrypoint_id,
            TRUSTED_TENANT_AUDIT_ACTIVITY_ENTRYPOINT_ID,
        )

    def test_trusted_tenant_runtime_envelope_shape_is_fixed(self) -> None:
        envelope = build_trusted_tenant_runtime_envelope(
            rollout_band="Band 1 Trusted-Tenant Read-Only",
            exposure_status="trusted-tenant-read-only",
            tenant_scope={"scope_id": "tff", "audience": "trusted-tenant"},
            requested_slice_id="band1.portal_home_tenant_status",
            slice_id="band1.portal_home_tenant_status",
            entrypoint_id=TRUSTED_TENANT_PORTAL_ENTRYPOINT_ID,
            read_write_posture="read-only",
            shell_state={"allowed": True},
            surface_payload={"schema": TRUSTED_TENANT_HOME_SURFACE_SCHEMA},
            shell_composition={"schema": "mycite.v2.portal.tenant_home.composition.v1"},
            warnings=[],
            error=None,
        )

        self.assertEqual(tuple(envelope.keys()), TRUSTED_TENANT_RUNTIME_REQUIRED_ENVELOPE_KEYS)
        self.assertEqual(envelope["schema"], TRUSTED_TENANT_RUNTIME_ENVELOPE_SCHEMA)
        self.assertEqual(
            build_trusted_tenant_runtime_error(code="tenant_scope_mismatch", message="Mismatch"),
            {"code": "tenant_scope_mismatch", "message": "Mismatch"},
        )


if __name__ == "__main__":
    unittest.main()
