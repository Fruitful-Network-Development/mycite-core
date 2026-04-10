from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

try:
    from flask import Flask

    HAS_FLASK = True
except ModuleNotFoundError:  # pragma: no cover
    HAS_FLASK = False
    Flask = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.portal_host import V2PortalHostConfig, create_app
from MyCiteV2.instances._shared.portal_host.app import HOST_SHAPE, V2_PORTAL_HEALTH_SCHEMA
from MyCiteV2.instances._shared.runtime.admin_aws_runtime import (
    ADMIN_AWS_NARROW_WRITE_REQUEST_SCHEMA,
    ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
    ADMIN_RUNTIME_ENVELOPE_SCHEMA,
)
from MyCiteV2.packages.ports.datum_store import SYSTEM_DATUM_RESOURCE_WORKBENCH_SCHEMA
from MyCiteV2.packages.state_machine.hanus_shell import (
    ADMIN_ENTRYPOINT_ID,
    ADMIN_HOME_STATUS_SLICE_ID,
    ADMIN_SHELL_REQUEST_SCHEMA,
    AWS_NARROW_WRITE_ENTRYPOINT_ID,
    AWS_READ_ONLY_ENTRYPOINT_ID,
)


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
        "verification": {"status": "verified", "portal_state": "verified"},
        "provider": {"gmail_send_as_status": "verified"},
        "workflow": {
            "initiated": True,
            "lifecycle_state": "operational",
            "is_ready_for_user_handoff": True,
            "is_mailbox_operational": True,
        },
        "inbound": {
            "receive_verified": True,
            "portal_native_display_ready": True,
            "receive_state": "receive_operational",
            "latest_message_id": "message-1",
        },
    }


def _build_config(temp_root: Path, *, aws_status_file: Path | None = None) -> V2PortalHostConfig:
    public_dir = temp_root / "public"
    private_dir = temp_root / "private"
    data_dir = temp_root / "data"
    (data_dir / "system" / "sources").mkdir(parents=True)
    (data_dir / "payloads" / "cache").mkdir(parents=True)
    public_dir.mkdir(parents=True)
    private_dir.mkdir(parents=True)
    (data_dir / "system" / "anthology.json").write_text(
        json.dumps({"0-0-1": [["0-0-1", "~", "0-0-0"], ["time-ordinal-position"]]}) + "\n",
        encoding="utf-8",
    )
    (data_dir / "system" / "sources" / "sc.example.json").write_text("{}\n", encoding="utf-8")
    (data_dir / "payloads" / "cache" / "sc.example.txa.json").write_text("{}\n", encoding="utf-8")
    (public_dir / "msn-example.json").write_text(json.dumps({"ok": True}) + "\n", encoding="utf-8")
    if aws_status_file is None:
        aws_status_file = temp_root / "aws-csm.tff.technicalContact.json"
        aws_status_file.write_text(json.dumps(_live_profile()) + "\n", encoding="utf-8")
    return V2PortalHostConfig(
        tenant_id="tff",
        public_dir=public_dir,
        private_dir=private_dir,
        data_dir=data_dir,
        analytics_domain="trappfamilyfarm.com",
        analytics_webapps_root=temp_root / "webapps",
        aws_status_file=aws_status_file,
        aws_audit_storage_file=private_dir / "local_audit" / "v2_aws_narrow_write.ndjson",
        admin_audit_storage_file=private_dir / "local_audit" / "v2_admin.ndjson",
    )


@unittest.skipUnless(HAS_FLASK, "flask is not installed in host python")
class V2NativePortalHostTests(unittest.TestCase):
    def test_portal_and_health_are_native_v2_without_admin_bridge_route(self) -> None:
        with TemporaryDirectory() as temp_dir:
            client = create_app(_build_config(Path(temp_dir))).test_client()

            portal = client.get("/portal")
            self.assertEqual(portal.status_code, 200)
            body = portal.get_data(as_text=True)
            self.assertIn('data-host-shape="v2_native"', body)
            self.assertNotIn("shape_b_v1_host_to_v2_runtime", body)

            health = client.get("/portal/healthz")
            self.assertEqual(health.status_code, 200)
            payload = health.get_json() or {}
            self.assertEqual(payload["schema"], V2_PORTAL_HEALTH_SCHEMA)
            self.assertEqual(payload["host_shape"], HOST_SHAPE)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["datum_health"]["row_count"], 1)
            self.assertTrue(payload["aws_config_health"]["live_profile_mapping"])
            self.assertIn("/clients/trappfamilyfarm.com/analytics", payload["analytics_root"]["analytics_root"])

            self.assertEqual(client.get("/portal/api/v2/admin/bridge/health").status_code, 404)

    def test_admin_shell_aws_and_datum_routes_call_v2_runtime_directly(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = _build_config(root)
            client = create_app(config).test_client()

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

            read_only = client.post(
                "/portal/api/v2/admin/aws/read-only",
                json={
                    "schema": ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
                },
            )
            self.assertEqual(read_only.status_code, 200)
            read_only_payload = read_only.get_json() or {}
            self.assertEqual(read_only_payload["entrypoint_id"], AWS_READ_ONLY_ENTRYPOINT_ID)
            self.assertEqual(
                read_only_payload["surface_payload"]["selected_verified_sender"],
                "technicalcontact@trappfamilyfarm.com",
            )
            self.assertEqual(
                read_only_payload["surface_payload"]["allowed_send_domains"],
                ["trappfamilyfarm.com"],
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
            narrow_write_payload = narrow_write.get_json() or {}
            self.assertEqual(narrow_write_payload["entrypoint_id"], AWS_NARROW_WRITE_ENTRYPOINT_ID)

            datum = client.get("/portal/api/v2/data/system/resource-workbench")
            self.assertEqual(datum.status_code, 200)
            datum_payload = datum.get_json() or {}
            self.assertEqual(datum_payload["schema"], SYSTEM_DATUM_RESOURCE_WORKBENCH_SCHEMA)
            self.assertEqual(datum_payload["row_count"], 1)

            public_json = client.get("/msn-example.json")
            self.assertEqual(public_json.status_code, 200)
            self.assertEqual(public_json.get_json(), {"ok": True})
            public_json.close()

    def test_portal_static_css_and_shell_markup(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = _build_config(root)
            client = create_app(config).test_client()

            css = client.get("/portal/static/portal.css")
            try:
                self.assertEqual(css.status_code, 200)
                self.assertIn(b"ide-shell", css.data)
            finally:
                css.close()

            home = client.get("/portal/")
            try:
                self.assertEqual(home.status_code, 200)
                self.assertIn(b"ide-shell", home.data)
                self.assertIn(b"v2_portal_shell.js", home.data)
            finally:
                home.close()

            system = client.get("/portal/system")
            try:
                self.assertEqual(system.status_code, 200)
                self.assertIn(b"ide-shell", system.data)
                self.assertIn(b"v2_portal_shell.js", system.data)
            finally:
                system.close()

    def test_analytics_collect_writes_only_to_clients_domain_path(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = _build_config(root)
            client = create_app(config).test_client()

            with patch.dict(os.environ, {"MYCITE_ANALYTICS_YEAR_MONTH": "2026-04"}):
                receipt = client.post(
                    "/__fnd/collect",
                    headers={"Host": "trappfamilyfarm.com", "User-Agent": "test-agent"},
                    json={"path": "/"},
                )

            self.assertEqual(receipt.status_code, 202)
            payload = receipt.get_json() or {}
            expected = root / "webapps" / "clients" / "trappfamilyfarm.com" / "analytics" / "events" / "2026-04.ndjson"
            self.assertEqual(payload["events_file"], str(expected))
            self.assertTrue(expected.exists())
            self.assertFalse((root / "webapps" / "trappfamilyfarm.com" / "analytics" / "events" / "2026-04.ndjson").exists())

    def test_non_live_aws_mapping_fails_closed_for_health_and_aws_routes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            status_file = root / "aws-status.json"
            status_file.write_text(json.dumps({"tenant_scope_id": "tff"}) + "\n", encoding="utf-8")
            client = create_app(_build_config(root, aws_status_file=status_file)).test_client()

            health = client.get("/portal/healthz")
            self.assertEqual(health.status_code, 503)
            self.assertFalse((health.get_json() or {})["aws_config_health"]["live_profile_mapping"])

            read_only = client.post(
                "/portal/api/v2/admin/aws/read-only",
                json={
                    "schema": ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
                },
            )
            self.assertEqual(read_only.status_code, 503)
            payload = read_only.get_json() or {}
            self.assertEqual(payload["schema"], ADMIN_RUNTIME_ENVELOPE_SCHEMA)
            self.assertEqual(payload["error"]["code"], "status_source_not_configured")


if __name__ == "__main__":
    unittest.main()
