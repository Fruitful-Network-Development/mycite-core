from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.runtime_platform import (
    BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
    BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
    TRUSTED_TENANT_AUDIT_ACTIVITY_ENTRYPOINT_ID,
    TRUSTED_TENANT_AUDIT_ACTIVITY_REQUEST_SCHEMA,
    TRUSTED_TENANT_AUDIT_ACTIVITY_SURFACE_SCHEMA,
    TRUSTED_TENANT_HOME_SURFACE_SCHEMA,
    TRUSTED_TENANT_OPERATIONAL_STATUS_ENTRYPOINT_ID,
    TRUSTED_TENANT_OPERATIONAL_STATUS_REQUEST_SCHEMA,
    TRUSTED_TENANT_OPERATIONAL_STATUS_SURFACE_SCHEMA,
    TRUSTED_TENANT_PORTAL_ENTRYPOINT_ID,
    TRUSTED_TENANT_RUNTIME_ENVELOPE_SCHEMA,
)
from MyCiteV2.instances._shared.runtime.tenant_audit_activity_runtime import (
    run_trusted_tenant_audit_activity,
)
from MyCiteV2.instances._shared.runtime.tenant_operational_status_runtime import (
    run_trusted_tenant_operational_status,
)
from MyCiteV2.instances._shared.runtime.tenant_portal_runtime import run_trusted_tenant_portal_home
from MyCiteV2.packages.state_machine.trusted_tenant_portal import (
    BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
    TRUSTED_TENANT_PORTAL_COMPOSITION_SCHEMA,
    TRUSTED_TENANT_PORTAL_REQUEST_SCHEMA,
)


class TenantPortalRuntimeIntegrationTests(unittest.TestCase):
    def test_runtime_builds_trusted_tenant_home_surface_from_publication_projection(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            public_dir = root / "public"
            (data_dir / "system").mkdir(parents=True)
            public_dir.mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text(
                json.dumps(
                    {
                        "6-2-3": [
                            ["6-3-3", "3-1-4", "f7472617070", "4-1-1", "3-2-3-17-77-2-6-3-1-6"],
                            ["trappfamilyfarm.com"],
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (public_dir / "3-2-3-17-77-2-6-3-1-6.json").write_text(
                json.dumps({"title": "trapp_family_farm", "entity_type": "legal_entity"}) + "\n",
                encoding="utf-8",
            )
            (public_dir / "fnd-3-2-3-17-77-2-6-3-1-6.json").write_text(
                json.dumps(
                    {
                        "summary": "Read-only summary for the trusted-tenant landing surface.",
                        "links": [{"href": "https://trappfamilyfarm.com"}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = run_trusted_tenant_portal_home(
                {
                    "schema": TRUSTED_TENANT_PORTAL_REQUEST_SCHEMA,
                    "requested_slice_id": BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
                    "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
                },
                data_dir=data_dir,
                public_dir=public_dir,
                portal_tenant_id="tff",
                tenant_domain="trappfamilyfarm.com",
            )

            self.assertEqual(result["schema"], TRUSTED_TENANT_RUNTIME_ENVELOPE_SCHEMA)
            self.assertEqual(result["entrypoint_id"], TRUSTED_TENANT_PORTAL_ENTRYPOINT_ID)
            self.assertEqual(result["slice_id"], BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID)
            self.assertIsNone(result["error"])
            self.assertEqual(result["surface_payload"]["schema"], TRUSTED_TENANT_HOME_SURFACE_SCHEMA)
            self.assertEqual(
                result["surface_payload"]["tenant_profile"]["profile_title"],
                "Trapp Family Farm",
            )
            self.assertEqual(
                result["surface_payload"]["tenant_profile"]["public_website_url"],
                "https://trappfamilyfarm.com",
            )
            self.assertEqual(
                result["shell_composition"]["schema"],
                TRUSTED_TENANT_PORTAL_COMPOSITION_SCHEMA,
            )
            self.assertEqual(result["shell_composition"]["regions"]["workbench"]["kind"], "tenant_home_status")
            self.assertEqual(result["shell_composition"]["regions"]["inspector"]["kind"], "tenant_profile_summary")
            self.assertEqual(
                [entry["slice_id"] for entry in result["surface_payload"]["available_slices"]],
                [
                    BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
                    BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
                    BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
                ],
            )

    def test_runtime_falls_back_safely_when_publication_summary_cannot_be_resolved(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            public_dir = root / "public"
            (data_dir / "system").mkdir(parents=True)
            public_dir.mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text(json.dumps({}) + "\n", encoding="utf-8")

            result = run_trusted_tenant_portal_home(
                {
                    "schema": TRUSTED_TENANT_PORTAL_REQUEST_SCHEMA,
                    "requested_slice_id": BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
                    "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
                },
                data_dir=data_dir,
                public_dir=public_dir,
                portal_tenant_id="tff",
                tenant_domain="trappfamilyfarm.com",
            )

            self.assertIsNone(result["error"])
            self.assertEqual(
                result["surface_payload"]["tenant_profile"]["profile_resolution"],
                "publication_unresolved",
            )
            self.assertIn(
                "Publication-backed tenant summary is not yet available",
                " ".join(result["warnings"]),
            )

    def test_runtime_rejects_cross_tenant_scope(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            public_dir = root / "public"
            (data_dir / "system").mkdir(parents=True)
            public_dir.mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text(json.dumps({}) + "\n", encoding="utf-8")

            result = run_trusted_tenant_portal_home(
                {
                    "schema": TRUSTED_TENANT_PORTAL_REQUEST_SCHEMA,
                    "requested_slice_id": BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
                    "tenant_scope": {"scope_id": "other", "audience": "trusted-tenant"},
                },
                data_dir=data_dir,
                public_dir=public_dir,
                portal_tenant_id="tff",
                tenant_domain="trappfamilyfarm.com",
            )

            self.assertEqual(result["error"]["code"], "tenant_scope_mismatch")
            self.assertEqual(result["slice_id"], BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID)

    def test_operational_status_runtime_returns_degraded_safe_surface_when_no_recent_audit_exists(self) -> None:
        with TemporaryDirectory() as temp_dir:
            audit_storage_file = Path(temp_dir) / "audit.ndjson"

            result = run_trusted_tenant_operational_status(
                {
                    "schema": TRUSTED_TENANT_OPERATIONAL_STATUS_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
                },
                audit_storage_file=audit_storage_file,
                portal_tenant_id="tff",
            )

            self.assertEqual(result["schema"], TRUSTED_TENANT_RUNTIME_ENVELOPE_SCHEMA)
            self.assertEqual(result["entrypoint_id"], TRUSTED_TENANT_OPERATIONAL_STATUS_ENTRYPOINT_ID)
            self.assertEqual(result["surface_payload"]["schema"], TRUSTED_TENANT_OPERATIONAL_STATUS_SURFACE_SCHEMA)
            self.assertIsNone(result["error"])
            self.assertEqual(
                result["surface_payload"]["audit_persistence"]["health_state"],
                "no_recent_persistence_evidence",
            )
            self.assertEqual(
                result["shell_composition"]["regions"]["workbench"]["kind"],
                "operational_status",
            )
            self.assertEqual(
                [entry["slice_id"] for entry in result["surface_payload"]["available_slices"]],
                [
                    BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
                    BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
                    BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
                ],
            )

    def test_operational_status_runtime_returns_recent_persistence_when_records_exist(self) -> None:
        with TemporaryDirectory() as temp_dir:
            audit_storage_file = Path(temp_dir) / "audit.ndjson"
            audit_storage_file.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "record_id": "audit-0001",
                                "recorded_at_unix_ms": 1770000000001,
                                "record": {"event_type": "shell.transition.accepted"},
                            }
                        ),
                        json.dumps(
                            {
                                "record_id": "audit-0002",
                                "recorded_at_unix_ms": 1770000000002,
                                "record": {"event_type": "shell.transition.accepted"},
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = run_trusted_tenant_operational_status(
                {
                    "schema": TRUSTED_TENANT_OPERATIONAL_STATUS_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
                },
                audit_storage_file=audit_storage_file,
                portal_tenant_id="tff",
            )

            self.assertEqual(
                result["surface_payload"]["audit_persistence"]["health_state"],
                "recent_persistence_observed",
            )
            self.assertEqual(
                result["surface_payload"]["audit_persistence"]["latest_recorded_at_unix_ms"],
                1770000000002,
            )
            self.assertEqual(
                result["shell_composition"]["regions"]["inspector"]["kind"],
                "operational_status_summary",
            )

    def test_operational_status_runtime_reports_unavailable_for_unreadable_storage(self) -> None:
        with TemporaryDirectory() as temp_dir:
            audit_storage_file = Path(temp_dir) / "audit.ndjson"
            audit_storage_file.write_bytes(b"\x80\x81")

            result = run_trusted_tenant_operational_status(
                {
                    "schema": TRUSTED_TENANT_OPERATIONAL_STATUS_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
                },
                audit_storage_file=audit_storage_file,
                portal_tenant_id="tff",
            )

            self.assertIsNone(result["error"])
            self.assertEqual(
                result["surface_payload"]["audit_persistence"]["health_state"],
                "unavailable",
            )
            self.assertEqual(
                result["surface_payload"]["audit_persistence"]["storage_state"],
                "unreadable",
            )

    def test_operational_status_runtime_rejects_cross_tenant_scope(self) -> None:
        with TemporaryDirectory() as temp_dir:
            result = run_trusted_tenant_operational_status(
                {
                    "schema": TRUSTED_TENANT_OPERATIONAL_STATUS_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "other", "audience": "trusted-tenant"},
                },
                audit_storage_file=Path(temp_dir) / "audit.ndjson",
                portal_tenant_id="tff",
            )

            self.assertEqual(result["error"]["code"], "tenant_scope_mismatch")
            self.assertEqual(result["slice_id"], BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID)

    def test_audit_activity_runtime_returns_empty_safe_surface_when_no_recent_audit_exists(self) -> None:
        with TemporaryDirectory() as temp_dir:
            audit_storage_file = Path(temp_dir) / "audit.ndjson"

            result = run_trusted_tenant_audit_activity(
                {
                    "schema": TRUSTED_TENANT_AUDIT_ACTIVITY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
                },
                audit_storage_file=audit_storage_file,
                portal_tenant_id="tff",
            )

            self.assertEqual(result["schema"], TRUSTED_TENANT_RUNTIME_ENVELOPE_SCHEMA)
            self.assertEqual(result["entrypoint_id"], TRUSTED_TENANT_AUDIT_ACTIVITY_ENTRYPOINT_ID)
            self.assertEqual(result["slice_id"], BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID)
            self.assertIsNone(result["error"])
            self.assertEqual(result["surface_payload"]["schema"], TRUSTED_TENANT_AUDIT_ACTIVITY_SURFACE_SCHEMA)
            self.assertEqual(result["surface_payload"]["recent_activity"]["activity_state"], "empty")
            self.assertEqual(result["shell_composition"]["regions"]["workbench"]["kind"], "audit_activity")
            self.assertEqual(result["shell_composition"]["regions"]["inspector"]["kind"], "audit_activity_summary")

    def test_audit_activity_runtime_returns_recent_records_from_fixed_window(self) -> None:
        with TemporaryDirectory() as temp_dir:
            audit_storage_file = Path(temp_dir) / "audit.ndjson"
            audit_storage_file.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "record_id": "audit-0001",
                                "recorded_at_unix_ms": 1770000000001,
                                "record": {
                                    "event_type": "aws.onboarding.accepted",
                                    "focus_subject": "3-2-3-17-77-1-6-4-1-4.4-1-77",
                                    "shell_verb": "apply",
                                    "details": {"onboarding_action": "verify_sender"},
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "record_id": "audit-0002",
                                "recorded_at_unix_ms": 1770000000002,
                                "record": {
                                    "event_type": "aws.narrow_write.applied",
                                    "focus_subject": "3-2-3-17-77-1-6-4-1-4.4-1-77",
                                    "shell_verb": "submit",
                                    "details": {
                                        "profile_id": "aws-csm.tff.technicalContact",
                                        "updated_fields": ["selected_verified_sender"],
                                    },
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = run_trusted_tenant_audit_activity(
                {
                    "schema": TRUSTED_TENANT_AUDIT_ACTIVITY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
                },
                audit_storage_file=audit_storage_file,
                portal_tenant_id="tff",
            )

            self.assertEqual(
                result["surface_payload"]["recent_activity"]["activity_state"],
                "recent_activity_observed",
            )
            self.assertEqual(
                result["surface_payload"]["recent_activity"]["latest_recorded_at_unix_ms"],
                1770000000002,
            )
            self.assertEqual(
                [record["record_id"] for record in result["surface_payload"]["recent_activity"]["records"]],
                ["audit-0002", "audit-0001"],
            )
            self.assertNotIn("external_events", result["surface_payload"])
            self.assertEqual(
                [entry["slice_id"] for entry in result["surface_payload"]["available_slices"]],
                [
                    BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
                    BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
                    BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
                ],
            )

    def test_audit_activity_runtime_reports_unavailable_for_unreadable_storage(self) -> None:
        with TemporaryDirectory() as temp_dir:
            audit_storage_file = Path(temp_dir) / "audit.ndjson"
            audit_storage_file.write_bytes(b"\x80\x81")

            result = run_trusted_tenant_audit_activity(
                {
                    "schema": TRUSTED_TENANT_AUDIT_ACTIVITY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
                },
                audit_storage_file=audit_storage_file,
                portal_tenant_id="tff",
            )

            self.assertIsNone(result["error"])
            self.assertEqual(
                result["surface_payload"]["recent_activity"]["activity_state"],
                "unavailable",
            )

    def test_audit_activity_runtime_rejects_cross_tenant_scope(self) -> None:
        with TemporaryDirectory() as temp_dir:
            result = run_trusted_tenant_audit_activity(
                {
                    "schema": TRUSTED_TENANT_AUDIT_ACTIVITY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "other", "audience": "trusted-tenant"},
                },
                audit_storage_file=Path(temp_dir) / "audit.ndjson",
                portal_tenant_id="tff",
            )

            self.assertEqual(result["error"]["code"], "tenant_scope_mismatch")
            self.assertEqual(result["slice_id"], BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID)


if __name__ == "__main__":
    unittest.main()
