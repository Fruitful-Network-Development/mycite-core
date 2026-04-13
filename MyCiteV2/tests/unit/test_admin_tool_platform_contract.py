from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.runtime_platform import (
    ADMIN_RUNTIME_ENVELOPE_SCHEMA,
    ADMIN_RUNTIME_ENTRYPOINT_DESCRIPTOR_SCHEMA,
    ADMIN_RUNTIME_REQUIRED_ENVELOPE_KEYS,
    ADMIN_SHELL_ENTRY_LAUNCH_CONTRACT,
    ADMIN_CTS_GIS_READ_ONLY_SURFACE_SCHEMA,
    ADMIN_FND_EBI_READ_ONLY_SURFACE_SCHEMA,
    build_admin_runtime_entrypoint_catalog,
    build_admin_runtime_envelope,
    build_admin_runtime_error,
    resolve_admin_runtime_entrypoint,
)
from MyCiteV2.packages.state_machine.hanus_shell import (
    ADMIN_ENTRYPOINT_ID,
    ADMIN_TOOL_DESCRIPTOR_SCHEMA,
    ADMIN_TOOL_KIND_GENERAL,
    ADMIN_TOOL_KIND_SERVICE,
    ADMIN_TOOL_LAUNCH_CONTRACT,
    AWS_CSM_FAMILY_HOME_ENTRYPOINT_ID,
    AWS_CSM_ONBOARDING_ENTRYPOINT_ID,
    AWS_CSM_SANDBOX_READ_ONLY_ENTRYPOINT_ID,
    AWS_NARROW_WRITE_ENTRYPOINT_ID,
    AWS_READ_ONLY_ENTRYPOINT_ID,
    CTS_GIS_READ_ONLY_ENTRYPOINT_ID,
    FND_EBI_READ_ONLY_ENTRYPOINT_ID,
    AdminToolRegistryEntry,
    build_admin_tool_registry_entries,
)


class AdminToolPlatformContractTests(unittest.TestCase):
    def test_tool_descriptors_have_stable_drop_in_shape(self) -> None:
        entries = [entry.to_dict() for entry in build_admin_tool_registry_entries()]

        self.assertEqual([entry["schema"] for entry in entries], [ADMIN_TOOL_DESCRIPTOR_SCHEMA] * 6)
        self.assertTrue(all(entry["discovery_mode"] == "catalog-driven" for entry in entries))
        self.assertTrue(all(entry["launch_contract"] == ADMIN_TOOL_LAUNCH_CONTRACT for entry in entries))
        self.assertTrue(all(entry["default_posture"] == "deny-by-default" for entry in entries))
        self.assertEqual(entries[0]["surface_pattern"], "read-only")
        self.assertEqual(entries[0]["tool_kind"], ADMIN_TOOL_KIND_SERVICE)
        self.assertEqual(entries[0]["shared_portal_capabilities"], ["external_service_binding"])
        self.assertFalse(entries[0]["audit_required"])
        self.assertFalse(entries[0]["read_after_write_required"])
        self.assertEqual(entries[1]["surface_pattern"], "bounded-write")
        self.assertEqual(entries[1]["tool_kind"], ADMIN_TOOL_KIND_SERVICE)
        self.assertTrue(entries[1]["audit_required"])
        self.assertTrue(entries[1]["read_after_write_required"])
        self.assertEqual(entries[2]["surface_pattern"], "read-only")
        self.assertEqual(entries[2]["tool_kind"], ADMIN_TOOL_KIND_SERVICE)
        self.assertEqual(entries[2]["audience"], "internal-admin")
        self.assertEqual(entries[3]["surface_pattern"], "bounded-write")
        self.assertEqual(entries[3]["tool_kind"], ADMIN_TOOL_KIND_SERVICE)
        self.assertTrue(entries[3]["audit_required"])
        self.assertTrue(entries[3]["read_after_write_required"])
        self.assertEqual(entries[3]["audience"], "trusted-tenant-admin")
        self.assertEqual(entries[4]["surface_pattern"], "read-only")
        self.assertEqual(entries[4]["tool_kind"], ADMIN_TOOL_KIND_GENERAL)
        self.assertEqual(entries[4]["tool_id"], "cts_gis")
        self.assertFalse(entries[4]["audit_required"])
        self.assertFalse(entries[4]["read_after_write_required"])
        self.assertEqual(entries[4]["audience"], "internal-admin")
        self.assertEqual(entries[5]["surface_pattern"], "read-only")
        self.assertEqual(entries[5]["tool_kind"], ADMIN_TOOL_KIND_SERVICE)
        self.assertEqual(entries[5]["tool_id"], "fnd_ebi")
        self.assertEqual(entries[5]["shared_portal_capabilities"], ["external_service_binding", "hosted_site_visibility"])
        self.assertFalse(entries[5]["audit_required"])
        self.assertFalse(entries[5]["read_after_write_required"])
        self.assertEqual(entries[5]["audience"], "internal-admin")
        self.assertEqual(json.loads(json.dumps(entries, sort_keys=True)), entries)

    def test_descriptor_rejects_writable_tool_without_audit_or_read_after_write(self) -> None:
        with self.assertRaisesRegex(ValueError, "audit and read-after-write"):
            AdminToolRegistryEntry(
                tool_id="future",
                label="Future Tool",
                slice_id="future.slice",
                entrypoint_id="future.entrypoint",
                tool_kind=ADMIN_TOOL_KIND_SERVICE,
                admin_band="Future Band",
                exposure_status="candidate",
                read_write_posture="write",
                surface_pattern="bounded-write",
                status_summary="not_ready",
                audience="trusted-tenant-admin",
                internal_only_reason="not implemented",
            )

    def test_descriptor_rejects_default_tool_vocabulary_for_tool_kind(self) -> None:
        with self.assertRaisesRegex(ValueError, "default_tool is forbidden"):
            AdminToolRegistryEntry(
                tool_id="future",
                label="Future Tool",
                slice_id="future.slice",
                entrypoint_id="future.entrypoint",
                tool_kind="default_tool",
                admin_band="Future Band",
                exposure_status="candidate",
                read_write_posture="read-only",
                surface_pattern="read-only",
                status_summary="not_ready",
                audience="internal-admin",
                internal_only_reason="not implemented",
            )

    def test_runtime_entrypoint_catalog_is_static_and_serializable(self) -> None:
        descriptors = [entry.to_dict() for entry in build_admin_runtime_entrypoint_catalog()]

        self.assertEqual([entry["schema"] for entry in descriptors], [ADMIN_RUNTIME_ENTRYPOINT_DESCRIPTOR_SCHEMA] * 8)
        self.assertEqual(
            [entry["entrypoint_id"] for entry in descriptors],
            [
                ADMIN_ENTRYPOINT_ID,
                AWS_CSM_FAMILY_HOME_ENTRYPOINT_ID,
                AWS_READ_ONLY_ENTRYPOINT_ID,
                AWS_NARROW_WRITE_ENTRYPOINT_ID,
                AWS_CSM_SANDBOX_READ_ONLY_ENTRYPOINT_ID,
                AWS_CSM_ONBOARDING_ENTRYPOINT_ID,
                CTS_GIS_READ_ONLY_ENTRYPOINT_ID,
                FND_EBI_READ_ONLY_ENTRYPOINT_ID,
            ],
        )
        self.assertEqual(descriptors[0]["launch_contract"], ADMIN_SHELL_ENTRY_LAUNCH_CONTRACT)
        self.assertIsNone(descriptors[0]["tool_kind"])
        self.assertEqual(descriptors[0]["shared_portal_capabilities"], [])
        self.assertEqual(descriptors[1]["launch_contract"], ADMIN_TOOL_LAUNCH_CONTRACT)
        self.assertEqual(descriptors[1]["tool_kind"], ADMIN_TOOL_KIND_SERVICE)
        self.assertEqual(descriptors[1]["required_configuration"], ["aws_status_file", "private_dir"])
        self.assertEqual(descriptors[2]["surface_pattern"], "read-only")
        self.assertEqual(descriptors[2]["tool_kind"], ADMIN_TOOL_KIND_SERVICE)
        self.assertEqual(descriptors[3]["surface_pattern"], "bounded-write")
        self.assertEqual(descriptors[3]["tool_kind"], ADMIN_TOOL_KIND_SERVICE)
        self.assertEqual(descriptors[3]["required_configuration"], ["aws_status_file", "audit_storage_file"])
        self.assertEqual(descriptors[4]["entrypoint_id"], AWS_CSM_SANDBOX_READ_ONLY_ENTRYPOINT_ID)
        self.assertEqual(descriptors[4]["tool_kind"], ADMIN_TOOL_KIND_SERVICE)
        self.assertEqual(descriptors[4]["required_configuration"], ["aws_csm_sandbox_status_file"])
        self.assertEqual(descriptors[5]["entrypoint_id"], AWS_CSM_ONBOARDING_ENTRYPOINT_ID)
        self.assertEqual(descriptors[5]["tool_kind"], ADMIN_TOOL_KIND_SERVICE)
        self.assertEqual(descriptors[5]["required_configuration"], ["aws_status_file", "audit_storage_file"])
        self.assertEqual(descriptors[6]["entrypoint_id"], CTS_GIS_READ_ONLY_ENTRYPOINT_ID)
        self.assertEqual(descriptors[6]["tool_kind"], ADMIN_TOOL_KIND_GENERAL)
        self.assertEqual(descriptors[6]["surface_schema"], ADMIN_CTS_GIS_READ_ONLY_SURFACE_SCHEMA)
        self.assertEqual(descriptors[6]["required_configuration"], ["data_dir"])
        self.assertEqual(descriptors[7]["entrypoint_id"], FND_EBI_READ_ONLY_ENTRYPOINT_ID)
        self.assertEqual(descriptors[7]["tool_kind"], ADMIN_TOOL_KIND_SERVICE)
        self.assertEqual(descriptors[7]["surface_schema"], ADMIN_FND_EBI_READ_ONLY_SURFACE_SCHEMA)
        self.assertEqual(descriptors[7]["required_configuration"], ["private_dir", "analytics_webapps_root"])
        self.assertEqual(json.loads(json.dumps(descriptors, sort_keys=True)), descriptors)
        self.assertIsNone(resolve_admin_runtime_entrypoint("missing.entrypoint"))
        self.assertEqual(
            resolve_admin_runtime_entrypoint(AWS_NARROW_WRITE_ENTRYPOINT_ID).entrypoint_id,
            AWS_NARROW_WRITE_ENTRYPOINT_ID,
        )
        self.assertEqual(
            resolve_admin_runtime_entrypoint(CTS_GIS_READ_ONLY_ENTRYPOINT_ID).entrypoint_id,
            CTS_GIS_READ_ONLY_ENTRYPOINT_ID,
        )
        self.assertEqual(
            resolve_admin_runtime_entrypoint(FND_EBI_READ_ONLY_ENTRYPOINT_ID).entrypoint_id,
            FND_EBI_READ_ONLY_ENTRYPOINT_ID,
        )

    def test_shared_runtime_envelope_shape_is_fixed(self) -> None:
        envelope = build_admin_runtime_envelope(
            admin_band="Test Band",
            exposure_status="internal-only",
            tenant_scope={"scope_id": "tenant-a", "audience": "internal"},
            requested_slice_id="test.slice",
            slice_id="test.slice",
            entrypoint_id="test.entrypoint",
            read_write_posture="read-only",
            shell_state={"allowed": True},
            surface_payload={"schema": "test.surface"},
            shell_composition={"schema": "mycite.v2.admin.shell.composition.v1"},
            warnings=[],
            error=None,
        )

        self.assertEqual(tuple(envelope.keys()), ADMIN_RUNTIME_REQUIRED_ENVELOPE_KEYS)
        self.assertEqual(envelope["schema"], ADMIN_RUNTIME_ENVELOPE_SCHEMA)
        self.assertEqual(
            build_admin_runtime_error(code="slice_gated", message="Not ready"),
            {"code": "slice_gated", "message": "Not ready"},
        )


if __name__ == "__main__":
    unittest.main()
