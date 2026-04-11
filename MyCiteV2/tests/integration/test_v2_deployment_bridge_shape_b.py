from __future__ import annotations

import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

try:
    from flask import Flask

    HAS_FLASK = True
except ModuleNotFoundError:  # pragma: no cover
    HAS_FLASK = False
    Flask = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parents[3]
MYCITE_V1_ROOT = REPO_ROOT / "MyCiteV1"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(MYCITE_V1_ROOT) not in sys.path:
    sys.path.insert(0, str(MYCITE_V1_ROOT))

from MyCiteV2.instances._shared.runtime.admin_aws_runtime import (
    ADMIN_AWS_NARROW_WRITE_REQUEST_SCHEMA,
    ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
    ADMIN_RUNTIME_ENVELOPE_SCHEMA,
)
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    ADMIN_HOME_STATUS_SURFACE_SCHEMA,
    ADMIN_TOOL_REGISTRY_SURFACE_SCHEMA,
)
from MyCiteV2.packages.adapters.portal_runtime import V2AdminBridgeConfig, build_v2_admin_bridge_health
from MyCiteV2.packages.adapters.portal_runtime.v1_host_bridge import V2_ADMIN_BRIDGE_HEALTH_SCHEMA
from MyCiteV2.packages.state_machine.hanus_shell import (
    ADMIN_ENTRYPOINT_ID,
    ADMIN_HOME_STATUS_SLICE_ID,
    ADMIN_SHELL_REQUEST_SCHEMA,
    ADMIN_TOOL_REGISTRY_SLICE_ID,
    AWS_CSM_SANDBOX_READ_ONLY_ENTRYPOINT_ID,
    AWS_NARROW_WRITE_ENTRYPOINT_ID,
    AWS_NARROW_WRITE_SLICE_ID,
    AWS_READ_ONLY_ENTRYPOINT_ID,
    AWS_READ_ONLY_SLICE_ID,
)


def _status_snapshot(selected_sender: str = "alerts@example.com") -> dict[str, object]:
    return {
        "tenant_scope_id": "tenant-a",
        "mailbox_readiness": "ready_for_gmail_handoff",
        "smtp_state": "smtp_ready",
        "gmail_state": "gmail_pending",
        "verified_evidence_state": "sender_selected",
        "selected_verified_sender": selected_sender,
        "canonical_newsletter_profile": {
            "profile_id": "newsletter.example.com",
            "domain": "example.com",
            "list_address": "news@example.com",
            "selected_verified_sender": selected_sender,
            "delivery_mode": "inbound-mail-only",
        },
        "compatibility": {
            "canonical_profile_matches_compatibility_inputs": True,
        },
        "inbound_capture": {
            "status": "ready",
            "last_capture_state": "idle",
        },
        "dispatch_health": {
            "status": "healthy",
            "last_delivery_outcome": "ok",
            "pending_message_count": 0,
        },
    }


def _live_profile(selected_sender: str = "technicalcontact@trappfamilyfarm.com") -> dict[str, object]:
    return {
        "schema": "mycite.service_tool.aws_csm.profile.v1",
        "identity": {
            "profile_id": "aws-csm.tff.technicalContact",
            "tenant_id": "tff",
            "domain": "trappfamilyfarm.com",
            "mailbox_local_part": "technicalcontact",
            "send_as_email": selected_sender,
        },
        "smtp": {
            "handoff_ready": True,
            "credentials_secret_state": "configured",
            "send_as_email": selected_sender,
            "local_part": "technicalcontact",
        },
        "verification": {"status": "verified"},
        "provider": {"gmail_send_as_status": "verified"},
        "workflow": {"initiated": True, "lifecycle_state": "operational", "is_mailbox_operational": True},
        "inbound": {"receive_verified": True, "latest_message_id": "message-1"},
    }


def _load_portal_app_module(flavor: str, temp_root: Path, status_file: Path, audit_file: Path):
    instances_root = MYCITE_V1_ROOT / "instances"
    runtime_root = instances_root / "_shared" / "runtime" / "flavors" / flavor
    private_dir = temp_root / "private"
    public_dir = temp_root / "public"
    data_dir = temp_root / "data"
    private_dir.mkdir(parents=True, exist_ok=True)
    public_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    msn_id = "3-2-3-17-77-1-6-4-1-4" if flavor == "fnd" else "3-2-3-17-77-2-6-3-1-6"
    title = "FND" if flavor == "fnd" else "TFF"
    (private_dir / "config.json").write_text(
        json.dumps(
            {
                "msn_id": msn_id,
                "tools_configuration": [
                    {"name": "aws-csm", "status": "enabled", "mount_target": "peripherals.tools"},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (public_dir / f"msn-{msn_id}.json").write_text(
        json.dumps({"msn_id": msn_id, "title": title}) + "\n",
        encoding="utf-8",
    )
    (public_dir / f"fnd-{msn_id}.json").write_text(
        json.dumps(
            {
                "schema": "mycite.fnd.profile.v1",
                "msn_id": msn_id,
                "title": title,
                "summary": "Bridge Test",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    env_updates = {
        "PRIVATE_DIR": str(private_dir),
        "PUBLIC_DIR": str(public_dir),
        "DATA_DIR": str(data_dir),
        "MSN_ID": msn_id,
        "PORTAL_RUNTIME_FLAVOR": flavor,
        "MYCITE_PORTALS_ROOT": str(instances_root),
        "MYCITE_V2_AWS_STATUS_FILE": str(status_file),
        "MYCITE_V2_AWS_AUDIT_FILE": str(audit_file),
        "MYCITE_V2_ADMIN_AUDIT_FILE": str(temp_root / "v2_admin_bridge.ndjson"),
    }
    previous = {key: os.environ.get(key) for key in env_updates}
    os.environ.update(env_updates)
    try:
        path = runtime_root / "app.py"
        spec = importlib.util.spec_from_file_location(f"v2_bridge_{flavor}_portal_app_test", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.app.config["MYCITE_V2_AWS_STATUS_FILE"] = str(status_file)
        module.app.config["MYCITE_V2_AWS_AUDIT_FILE"] = str(audit_file)
        module.app.config["MYCITE_V2_ADMIN_AUDIT_FILE"] = str(temp_root / "v2_admin_bridge.ndjson")
        return module
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@unittest.skipUnless(HAS_FLASK, "flask is not installed in host python")
class V2DeploymentBridgeShapeBTests(unittest.TestCase):
    def test_health_does_not_expose_configured_paths(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            status_file = temp_root / "aws_status.json"
            audit_file = temp_root / "aws_audit.ndjson"
            status_file.write_text(json.dumps(_status_snapshot()) + "\n", encoding="utf-8")
            module = _load_portal_app_module("fnd", temp_root, status_file, audit_file)

            response = module.app.test_client().get("/portal/api/v2/admin/bridge/health")

            self.assertEqual(response.status_code, 200)
            payload = response.get_json() or {}
            self.assertEqual(payload["schema"], V2_ADMIN_BRIDGE_HEALTH_SCHEMA)
            self.assertEqual(payload["bridge_shape"], "shape_b_v1_host_to_v2_runtime")
            self.assertEqual(
                [entry["entrypoint_id"] for entry in payload["runtime_catalog"]],
                [
                    ADMIN_ENTRYPOINT_ID,
                    AWS_READ_ONLY_ENTRYPOINT_ID,
                    AWS_NARROW_WRITE_ENTRYPOINT_ID,
                    AWS_CSM_SANDBOX_READ_ONLY_ENTRYPOINT_ID,
                ],
            )
            self.assertEqual(
                payload["configured_inputs"],
                {
                    "audit_storage_file": True,
                    "aws_status_file": True,
                    "aws_live_profile_mapping": False,
                    "aws_audit_storage_file": True,
                    "aws_csm_sandbox_status_file": False,
                    "aws_csm_sandbox_live_profile_mapping": False,
                },
            )
            self.assertNotIn(str(temp_root), json.dumps(payload, sort_keys=True))

    def test_fnd_bridge_routes_call_cataloged_v2_entrypoints(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            status_file = temp_root / "aws_status.json"
            audit_file = temp_root / "aws_audit.ndjson"
            status_file.write_text(json.dumps(_status_snapshot("old@example.com")) + "\n", encoding="utf-8")
            module = _load_portal_app_module("fnd", temp_root, status_file, audit_file)
            client = module.app.test_client()

            shell = client.post(
                "/portal/api/v2/admin/shell",
                json={
                    "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                    "requested_slice_id": ADMIN_HOME_STATUS_SLICE_ID,
                    "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
                },
            )
            self.assertEqual(shell.status_code, 200)
            shell_payload = shell.get_json() or {}
            self.assertEqual(shell_payload["schema"], ADMIN_RUNTIME_ENVELOPE_SCHEMA)
            self.assertEqual(shell_payload["entrypoint_id"], ADMIN_ENTRYPOINT_ID)
            self.assertEqual(shell_payload["surface_payload"]["schema"], ADMIN_HOME_STATUS_SURFACE_SCHEMA)

            registry = client.post(
                "/portal/api/v2/admin/shell",
                json={
                    "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                    "requested_slice_id": ADMIN_TOOL_REGISTRY_SLICE_ID,
                    "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
                },
            )
            self.assertEqual(registry.status_code, 200)
            registry_payload = registry.get_json() or {}
            self.assertEqual(registry_payload["surface_payload"]["schema"], ADMIN_TOOL_REGISTRY_SURFACE_SCHEMA)

            read_only = client.post(
                "/portal/api/v2/admin/aws/read-only",
                json={
                    "schema": ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tenant-a", "audience": "trusted-tenant"},
                },
            )
            self.assertEqual(read_only.status_code, 200)
            read_only_payload = read_only.get_json() or {}
            self.assertEqual(read_only_payload["entrypoint_id"], AWS_READ_ONLY_ENTRYPOINT_ID)
            self.assertEqual(read_only_payload["slice_id"], AWS_READ_ONLY_SLICE_ID)
            self.assertEqual(read_only_payload["surface_payload"]["selected_verified_sender"], "old@example.com")

            narrow_write = client.post(
                "/portal/api/v2/admin/aws/narrow-write",
                json={
                    "schema": ADMIN_AWS_NARROW_WRITE_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tenant-a", "audience": "trusted-tenant"},
                    "focus_subject": "3-2-3-17-77-1-6-4-1-4.4-1-77",
                    "profile_id": "newsletter.example.com",
                    "selected_verified_sender": "new@example.com",
                },
            )
            self.assertEqual(narrow_write.status_code, 200)
            write_payload = narrow_write.get_json() or {}
            self.assertEqual(write_payload["entrypoint_id"], AWS_NARROW_WRITE_ENTRYPOINT_ID)
            self.assertEqual(write_payload["slice_id"], AWS_NARROW_WRITE_SLICE_ID)
            self.assertEqual(write_payload["surface_payload"]["write_status"], "applied")
            self.assertTrue(audit_file.exists())
            stored = json.loads(status_file.read_text(encoding="utf-8"))
            self.assertEqual(stored["selected_verified_sender"], "new@example.com")
            self.assertEqual(stored["canonical_newsletter_profile"]["selected_verified_sender"], "new@example.com")

    def test_bridge_maps_live_aws_profile_without_creating_shadow_status(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            status_file = temp_root / "aws-csm.tff.technicalContact.json"
            audit_file = temp_root / "aws_audit.ndjson"
            status_file.write_text(json.dumps(_live_profile("technicalcontact@trappfamilyfarm.com")) + "\n", encoding="utf-8")
            module = _load_portal_app_module("tff", temp_root, status_file, audit_file)
            client = module.app.test_client()

            health = client.get("/portal/api/v2/admin/bridge/health")
            self.assertEqual(health.status_code, 200)
            self.assertTrue((health.get_json() or {})["configured_inputs"]["aws_live_profile_mapping"])

            read_only = client.post(
                "/portal/api/v2/admin/aws/read-only",
                json={
                    "schema": ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
                },
            )
            self.assertEqual(read_only.status_code, 200)
            read_only_payload = read_only.get_json() or {}
            self.assertEqual(
                read_only_payload["surface_payload"]["selected_verified_sender"],
                "technicalcontact@trappfamilyfarm.com",
            )
            self.assertEqual(
                read_only_payload["surface_payload"]["canonical_newsletter_operational_profile"]["profile_id"],
                "aws-csm.tff.technicalContact",
            )

            narrow_write = client.post(
                "/portal/api/v2/admin/aws/narrow-write",
                json={
                    "schema": ADMIN_AWS_NARROW_WRITE_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
                    "focus_subject": "3-2-3-17-77-1-6-4-1-4.4-1-77",
                    "profile_id": "aws-csm.tff.technicalContact",
                    "selected_verified_sender": "ops@trappfamilyfarm.com",
                },
            )
            self.assertEqual(narrow_write.status_code, 200)
            stored = json.loads(status_file.read_text(encoding="utf-8"))
            self.assertEqual(stored["identity"]["send_as_email"], "ops@trappfamilyfarm.com")
            self.assertEqual(stored["smtp"]["send_as_email"], "ops@trappfamilyfarm.com")
            self.assertFalse((temp_root / "aws_status.json").exists())

    def test_bridge_denies_unknown_slices_and_non_internal_admin_band0_audience(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            status_file = temp_root / "aws_status.json"
            audit_file = temp_root / "aws_audit.ndjson"
            status_file.write_text(json.dumps(_status_snapshot()) + "\n", encoding="utf-8")
            module = _load_portal_app_module("fnd", temp_root, status_file, audit_file)
            client = module.app.test_client()

            unknown = client.post(
                "/portal/api/v2/admin/shell",
                json={
                    "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                    "requested_slice_id": "maps_after_aws",
                    "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
                },
            )
            self.assertEqual(unknown.status_code, 404)
            unknown_payload = unknown.get_json() or {}
            self.assertEqual(unknown_payload["error"]["code"], "slice_unknown")

            denied = client.post(
                "/portal/api/v2/admin/shell",
                json={
                    "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                    "requested_slice_id": ADMIN_HOME_STATUS_SLICE_ID,
                    "tenant_scope": {"scope_id": "tenant-a", "audience": "trusted-tenant"},
                },
            )
            self.assertEqual(denied.status_code, 403)
            denied_payload = denied.get_json() or {}
            self.assertEqual(denied_payload["error"]["code"], "audience_not_allowed")
            self.assertIsNone(denied_payload["surface_payload"])

    def test_tff_bridge_mount_uses_the_same_v2_shell_entrypoint(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            status_file = temp_root / "aws_status.json"
            audit_file = temp_root / "aws_audit.ndjson"
            status_file.write_text(json.dumps(_status_snapshot()) + "\n", encoding="utf-8")
            module = _load_portal_app_module("tff", temp_root, status_file, audit_file)

            response = module.app.test_client().post(
                "/portal/api/v2/admin/shell",
                json={
                    "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                    "requested_slice_id": ADMIN_HOME_STATUS_SLICE_ID,
                    "tenant_scope": {"scope_id": "tff-admin", "audience": "internal"},
                },
            )

            self.assertEqual(response.status_code, 200)
            payload = response.get_json() or {}
            self.assertEqual(payload["entrypoint_id"], ADMIN_ENTRYPOINT_ID)
            self.assertEqual(payload["tenant_scope"], {"scope_id": "tff-admin", "audience": "internal"})

    def test_bridge_error_payload_does_not_echo_secret_bearing_request_values(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            status_file = temp_root / "aws_status.json"
            audit_file = temp_root / "aws_audit.ndjson"
            status_file.write_text(json.dumps(_status_snapshot()) + "\n", encoding="utf-8")
            module = _load_portal_app_module("fnd", temp_root, status_file, audit_file)

            response = module.app.test_client().post(
                "/portal/api/v2/admin/aws/read-only",
                json={
                    "schema": ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
                    "tenant_scope": {
                        "scope_id": "tenant-a",
                        "audience": "not-approved",
                        "smtp_password": "do-not-return-this",
                    },
                },
            )

            self.assertEqual(response.status_code, 400)
            serialized = json.dumps(response.get_json() or {}, sort_keys=True)
            self.assertNotIn("do-not-return-this", serialized)
            self.assertNotIn("smtp_password", serialized)
            self.assertNotIn(str(temp_root), serialized)


class V2DeploymentBridgePureAdapterTests(unittest.TestCase):
    def test_health_builder_reports_configured_inputs_without_paths(self) -> None:
        health = build_v2_admin_bridge_health(
            V2AdminBridgeConfig(
                audit_storage_file="/tmp/admin.ndjson",
                aws_status_file="/tmp/aws.json",
                aws_audit_storage_file="/tmp/aws.ndjson",
            )
        )

        self.assertEqual(health["schema"], V2_ADMIN_BRIDGE_HEALTH_SCHEMA)
        self.assertTrue(health["configured_inputs"]["aws_status_file"])
        self.assertFalse(health["configured_inputs"]["aws_live_profile_mapping"])
        self.assertNotIn("/tmp/aws.json", json.dumps(health, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
