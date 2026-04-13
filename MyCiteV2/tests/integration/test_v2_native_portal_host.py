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

if HAS_FLASK:
    from MyCiteV2.instances._shared.portal_host import V2PortalHostConfig, create_app
    from MyCiteV2.instances._shared.portal_host.app import (
        HOST_SHAPE,
        TRUSTED_TENANT_ROUTE_CATALOG,
        TRUSTED_TENANT_STATIC_BUNDLE_PATH,
        TRUSTED_TENANT_STATIC_RENDER_MARKERS,
        TRUSTED_TENANT_SURFACE_CONTRACT_SCHEMA,
        V2_PORTAL_HEALTH_SCHEMA,
    )
    from MyCiteV2.instances._shared.runtime.admin_aws_runtime import (
        ADMIN_AWS_NARROW_WRITE_REQUEST_SCHEMA,
        ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
        ADMIN_RUNTIME_ENVELOPE_SCHEMA,
    )
    from MyCiteV2.instances._shared.runtime.runtime_platform import (
        ADMIN_CTS_GIS_READ_ONLY_REQUEST_SCHEMA,
        ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE,
        BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
        BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
        BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID,
        TRUSTED_TENANT_AUDIT_ACTIVITY_REQUEST_SCHEMA,
        TRUSTED_TENANT_OPERATIONAL_STATUS_REQUEST_SCHEMA,
        TRUSTED_TENANT_PROFILE_BASICS_WRITE_REQUEST_SCHEMA,
        TRUSTED_TENANT_RUNTIME_ENVELOPE_SCHEMA,
    )
    from MyCiteV2.packages.ports.datum_store import SYSTEM_DATUM_RESOURCE_WORKBENCH_SCHEMA
    from MyCiteV2.packages.state_machine.hanus_shell import (
        ADMIN_ENTRYPOINT_ID,
        ADMIN_HOME_STATUS_SLICE_ID,
        ADMIN_NETWORK_ROOT_SLICE_ID,
        ADMIN_SHELL_COMPOSITION_SCHEMA,
        ADMIN_SHELL_REQUEST_SCHEMA,
        ADMIN_TOOL_REGISTRY_SLICE_ID,
        AWS_CSM_ONBOARDING_SLICE_ID,
        AWS_CSM_SANDBOX_SLICE_ID,
        CTS_GIS_READ_ONLY_ENTRYPOINT_ID,
        AWS_NARROW_WRITE_ENTRYPOINT_ID,
        AWS_NARROW_WRITE_SLICE_ID,
        AWS_READ_ONLY_ENTRYPOINT_ID,
        AWS_READ_ONLY_SLICE_ID,
        DATUM_RESOURCE_WORKBENCH_SLICE_ID,
        CTS_GIS_READ_ONLY_SLICE_ID,
    )
    from MyCiteV2.packages.state_machine.trusted_tenant_portal import (
        BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
        TRUSTED_TENANT_PORTAL_REQUEST_SCHEMA,
    )
else:  # pragma: no cover
    V2PortalHostConfig = object  # type: ignore[assignment]
    create_app = None  # type: ignore[assignment]
    HOST_SHAPE = "v2_native"
    TRUSTED_TENANT_ROUTE_CATALOG = (
        {
            "page_route": "/portal/home",
            "api_route": "/portal/api/v2/tenant/home",
            "request_schema": "mycite.v2.portal.tenant_home.request.v1",
            "slice_id": "band1.portal_home_tenant_status",
            "workbench_kind": "tenant_home_status",
        },
        {
            "page_route": "/portal/status",
            "api_route": "/portal/api/v2/tenant/operational-status",
            "request_schema": "mycite.v2.portal.operational_status.request.v1",
            "slice_id": "band1.operational_status_surface",
            "workbench_kind": "operational_status",
        },
        {
            "page_route": "/portal/activity",
            "api_route": "/portal/api/v2/tenant/audit-activity",
            "request_schema": "mycite.v2.portal.audit_activity.request.v1",
            "slice_id": "band1.audit_activity_visibility",
            "workbench_kind": "audit_activity",
        },
        {
            "page_route": "/portal/profile-basics",
            "api_route": "/portal/api/v2/tenant/profile-basics",
            "request_schema": "mycite.v2.portal.profile_basics_write.request.v1",
            "slice_id": "band2.profile_basics_write_surface",
            "workbench_kind": "profile_basics_write",
        },
    )
    TRUSTED_TENANT_STATIC_BUNDLE_PATH = "/portal/static/v2_portal_shell.js"
    TRUSTED_TENANT_STATIC_RENDER_MARKERS = (
        "tenant_home_status",
        "operational_status",
        "audit_activity",
        "profile_basics_write",
    )
    TRUSTED_TENANT_SURFACE_CONTRACT_SCHEMA = "mycite.v2.portal.surface_contract.v1"
    V2_PORTAL_HEALTH_SCHEMA = "mycite.v2.portal.health.v1"
    ADMIN_AWS_NARROW_WRITE_REQUEST_SCHEMA = "mycite.v2.admin.aws.narrow_write.request.v1"
    ADMIN_CTS_GIS_READ_ONLY_REQUEST_SCHEMA = "mycite.v2.admin.cts_gis.read_only.request.v1"
    ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA = "mycite.v2.admin.aws.read_only.request.v1"
    ADMIN_RUNTIME_ENVELOPE_SCHEMA = "mycite.v2.admin.runtime.envelope.v1"
    ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE = "tool_not_exposed"
    TRUSTED_TENANT_RUNTIME_ENVELOPE_SCHEMA = "mycite.v2.portal.runtime.envelope.v1"
    SYSTEM_DATUM_RESOURCE_WORKBENCH_SCHEMA = "mycite.v2.data.system_resource_workbench.surface.v1"
    ADMIN_ENTRYPOINT_ID = "admin.shell_entry"
    ADMIN_HOME_STATUS_SLICE_ID = "admin_band0.home_status"
    ADMIN_NETWORK_ROOT_SLICE_ID = "admin_band0.network_root"
    ADMIN_SHELL_COMPOSITION_SCHEMA = "mycite.v2.admin.shell.composition.v1"
    ADMIN_SHELL_REQUEST_SCHEMA = "mycite.v2.admin.shell.request.v1"
    ADMIN_TOOL_REGISTRY_SLICE_ID = "admin_band0.tool_registry"
    AWS_CSM_ONBOARDING_SLICE_ID = "admin_band4.aws_csm_onboarding_surface"
    AWS_CSM_SANDBOX_SLICE_ID = "admin_band3.aws_csm_sandbox_surface"
    CTS_GIS_READ_ONLY_ENTRYPOINT_ID = "admin.cts_gis.read_only"
    AWS_NARROW_WRITE_ENTRYPOINT_ID = "admin.aws.narrow_write"
    AWS_NARROW_WRITE_SLICE_ID = "admin_band2.aws_narrow_write_surface"
    AWS_READ_ONLY_ENTRYPOINT_ID = "admin.aws.read_only"
    AWS_READ_ONLY_SLICE_ID = "admin_band1.aws_read_only_surface"
    DATUM_RESOURCE_WORKBENCH_SLICE_ID = "datum.resource_workbench"
    CTS_GIS_READ_ONLY_SLICE_ID = "admin_band5.cts_gis_read_only_surface"
    BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID = "band1.audit_activity_visibility"
    TRUSTED_TENANT_AUDIT_ACTIVITY_REQUEST_SCHEMA = "mycite.v2.portal.audit_activity.request.v1"
    BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID = "band1.operational_status_surface"
    BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID = "band2.profile_basics_write_surface"
    TRUSTED_TENANT_OPERATIONAL_STATUS_REQUEST_SCHEMA = "mycite.v2.portal.operational_status.request.v1"
    TRUSTED_TENANT_PROFILE_BASICS_WRITE_REQUEST_SCHEMA = "mycite.v2.portal.profile_basics_write.request.v1"
    BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID = "band1.portal_home_tenant_status"
    TRUSTED_TENANT_PORTAL_REQUEST_SCHEMA = "mycite.v2.portal.tenant_home.request.v1"


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


def _default_tool_exposure() -> dict[str, object]:
    return {
        "aws": {"enabled": True},
        "aws_csm_newsletter": {"enabled": False},
        "aws_narrow_write": {"enabled": True},
        "aws_csm_onboarding": {"enabled": True},
        "aws_csm_sandbox": {"enabled": False},
        "cts_gis": {"enabled": False},
    }


def _build_config(
    temp_root: Path,
    *,
    aws_status_file: Path | None = None,
    tool_exposure: dict[str, object] | None = None,
    tenant_id: str = "tff",
) -> V2PortalHostConfig:
    public_dir = temp_root / "public"
    private_dir = temp_root / "private"
    data_dir = temp_root / "data"
    webapps_root = temp_root / "webapps"
    (data_dir / "system" / "sources").mkdir(parents=True)
    (data_dir / "payloads" / "cache").mkdir(parents=True)
    public_dir.mkdir(parents=True)
    private_dir.mkdir(parents=True)
    (private_dir / "local_audit").mkdir(parents=True)
    webapps_root.mkdir(parents=True)
    (data_dir / "system" / "anthology.json").write_text(
        json.dumps({"0-0-1": [["0-0-1", "~", "0-0-0"], ["time-ordinal-position"]]}) + "\n",
        encoding="utf-8",
    )
    (data_dir / "system" / "sources" / "sc.example.json").write_text("{}\n", encoding="utf-8")
    (data_dir / "payloads" / "cache" / "sc.example.txa.json").write_text("{}\n", encoding="utf-8")
    (public_dir / "msn-example.json").write_text(json.dumps({"ok": True}) + "\n", encoding="utf-8")
    (private_dir / "config.json").write_text(
        json.dumps(
            {
                "tools_configuration": [],
                "tool_exposure": tool_exposure if tool_exposure is not None else _default_tool_exposure(),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    if aws_status_file is None:
        aws_status_file = temp_root / "aws-csm.tff.technicalContact.json"
        aws_status_file.write_text(json.dumps(_live_profile()) + "\n", encoding="utf-8")
    return V2PortalHostConfig(
        tenant_id=tenant_id,
        public_dir=public_dir,
        private_dir=private_dir,
        data_dir=data_dir,
        analytics_domain="fruitfulnetworkdevelopment.com" if tenant_id == "fnd" else "trappfamilyfarm.com",
        analytics_webapps_root=webapps_root,
        aws_status_file=aws_status_file,
        aws_audit_storage_file=private_dir / "local_audit" / "v2_aws_narrow_write.ndjson",
        admin_audit_storage_file=private_dir / "local_audit" / "v2_admin.ndjson",
    )


def _write_maps_data(config: V2PortalHostConfig) -> None:
    tool_dir = config.data_dir / "sandbox" / "maps"
    source_dir = tool_dir / "sources"
    source_dir.mkdir(parents=True, exist_ok=True)
    (tool_dir / "tool.maps.json").write_text(
        json.dumps(
            {
                "3-1-1": [["3-1-1", "~", "0-0-0"], ["HOPS-babelette-coordinate"]],
                "3-1-2": [["3-1-2", "~", "0-0-0"], ["SAMRAS-babelette-msn_id"]],
                "3-1-3": [["3-1-3", "~", "0-0-0"], ["title-babelette"]],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (source_dir / "sc.example.json").write_text(
        json.dumps(
            {
                "anchor_file_version": "<hash here>",
                "datum_addressing_abstraction_space": {
                    "4-2-1": [
                        ["4-2-1", "rf.3-1-1", "3-76-11-40-92-20-21-92-51-75-26-64-11-48-77-78-73"],
                        ["point_alpha"],
                    ],
                    "4-2-2": [
                        [
                            "4-2-2",
                            "rf.3-1-1",
                            "3-76-11-40-92-20-21-92-81-29-56-60-79-56-3-4-39",
                            "rf.3-1-1",
                            "3-76-11-40-92-20-21-92-81-25-68-43-68-84-44-22-24",
                            "rf.3-1-1",
                            "3-76-11-40-92-20-21-92-51-75-26-64-11-48-77-78-73",
                        ],
                        ["polygon_1"],
                    ],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_publication_home_data(config: V2PortalHostConfig) -> None:
    (config.data_dir / "system" / "anthology.json").write_text(
        json.dumps(
            {
                "0-0-1": [["0-0-1", "~", "0-0-0"], ["time-ordinal-position"]],
                "6-2-3": [
                    ["6-3-3", "3-1-4", "f7472617070", "4-1-1", "3-2-3-17-77-2-6-3-1-6"],
                    ["trappfamilyfarm.com"],
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (config.public_dir / "3-2-3-17-77-2-6-3-1-6.json").write_text(
        json.dumps({"title": "trapp_family_farm", "entity_type": "legal_entity"}) + "\n",
        encoding="utf-8",
    )
    (config.public_dir / "fnd-3-2-3-17-77-2-6-3-1-6.json").write_text(
        json.dumps(
            {
                "summary": "Read-only summary for the trusted-tenant landing surface.",
                "links": [{"href": "https://trappfamilyfarm.com"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )


@unittest.skipUnless(HAS_FLASK, "flask is not installed in host python")
class V2NativePortalHostTests(unittest.TestCase):
    def test_from_env_requires_portal_instance_id(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PORTAL_RUNTIME_FLAVOR": "fnd",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "PORTAL_INSTANCE_ID"):
                V2PortalHostConfig.from_env()

    def test_from_env_requires_existing_state_directories(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            status_file = root / "aws-csm.tff.technicalContact.json"
            status_file.write_text(json.dumps(_live_profile()) + "\n", encoding="utf-8")
            (root / "webapps").mkdir()
            (root / "audit").mkdir()

            with patch.dict(
                os.environ,
                {
                    "PORTAL_INSTANCE_ID": "tff",
                    "PORTAL_RUNTIME_FLAVOR": "tff",
                    "PUBLIC_DIR": str(root / "missing-public"),
                    "PRIVATE_DIR": str(root / "missing-private"),
                    "DATA_DIR": str(root / "missing-data"),
                    "MYCITE_ANALYTICS_DOMAIN": "trappfamilyfarm.com",
                    "MYCITE_WEBAPPS_ROOT": str(root / "webapps"),
                    "MYCITE_V2_AWS_STATUS_FILE": str(status_file),
                    "MYCITE_V2_AWS_AUDIT_FILE": str(root / "audit" / "aws.ndjson"),
                    "MYCITE_V2_ADMIN_AUDIT_FILE": str(root / "audit" / "admin.ndjson"),
                },
                clear=True,
            ):
                with self.assertRaisesRegex(ValueError, "PUBLIC_DIR"):
                    V2PortalHostConfig.from_env()

    def test_from_env_requires_live_aws_status_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            public_dir = root / "public"
            private_dir = root / "private"
            data_dir = root / "data"
            webapps_root = root / "webapps"
            audit_root = root / "audit"
            for path in (public_dir, private_dir, data_dir, webapps_root, audit_root):
                path.mkdir(parents=True)
            invalid_status_file = root / "aws-status.json"
            invalid_status_file.write_text(json.dumps({"tenant_scope_id": "tff"}) + "\n", encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "PORTAL_INSTANCE_ID": "tff",
                    "PORTAL_RUNTIME_FLAVOR": "tff",
                    "PUBLIC_DIR": str(public_dir),
                    "PRIVATE_DIR": str(private_dir),
                    "DATA_DIR": str(data_dir),
                    "MYCITE_ANALYTICS_DOMAIN": "trappfamilyfarm.com",
                    "MYCITE_WEBAPPS_ROOT": str(webapps_root),
                    "MYCITE_V2_AWS_STATUS_FILE": str(invalid_status_file),
                    "MYCITE_V2_AWS_AUDIT_FILE": str(audit_root / "aws.ndjson"),
                    "MYCITE_V2_ADMIN_AUDIT_FILE": str(audit_root / "admin.ndjson"),
                },
                clear=True,
            ):
                with self.assertRaisesRegex(ValueError, "MYCITE_V2_AWS_STATUS_FILE"):
                    V2PortalHostConfig.from_env()

    def test_from_env_requires_audit_sinks(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            public_dir = root / "public"
            private_dir = root / "private"
            data_dir = root / "data"
            webapps_root = root / "webapps"
            for path in (public_dir, private_dir, data_dir, webapps_root):
                path.mkdir(parents=True)
            status_file = root / "aws-csm.tff.technicalContact.json"
            status_file.write_text(json.dumps(_live_profile()) + "\n", encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "PORTAL_INSTANCE_ID": "tff",
                    "PORTAL_RUNTIME_FLAVOR": "tff",
                    "PUBLIC_DIR": str(public_dir),
                    "PRIVATE_DIR": str(private_dir),
                    "DATA_DIR": str(data_dir),
                    "MYCITE_ANALYTICS_DOMAIN": "trappfamilyfarm.com",
                    "MYCITE_WEBAPPS_ROOT": str(webapps_root),
                    "MYCITE_V2_AWS_STATUS_FILE": str(status_file),
                },
                clear=True,
            ):
                with self.assertRaisesRegex(ValueError, "MYCITE_V2_AWS_AUDIT_FILE"):
                    V2PortalHostConfig.from_env()

    def test_private_config_tool_exposure_parses_unknown_and_missing_keys(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            public_dir = root / "public"
            private_dir = root / "private"
            data_dir = root / "data"
            webapps_root = root / "webapps"
            audit_root = private_dir / "local_audit"
            for path in (public_dir, private_dir, data_dir, webapps_root, audit_root):
                path.mkdir(parents=True, exist_ok=True)
            status_file = root / "aws-csm.tff.technicalContact.json"
            status_file.write_text(json.dumps(_live_profile()) + "\n", encoding="utf-8")
            (private_dir / "config.json").write_text(
                json.dumps(
                    {
                        "tools_configuration": [],
                        "tool_exposure": {
                            "aws": {"enabled": True},
                            "aws_narrow_write": {},
                            "ghost_tool": {"enabled": True},
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            config = V2PortalHostConfig(
                tenant_id="tff",
                public_dir=public_dir,
                private_dir=private_dir,
                data_dir=data_dir,
                analytics_domain="trappfamilyfarm.com",
                analytics_webapps_root=webapps_root,
                aws_status_file=status_file,
                aws_audit_storage_file=audit_root / "aws.ndjson",
                admin_audit_storage_file=audit_root / "admin.ndjson",
            )

            summary = config.tool_exposure_policy or {}
            self.assertEqual(summary.get("enabled_tool_ids"), ["aws"])
            self.assertIn("aws_csm_newsletter", summary.get("missing_tool_ids") or [])
            self.assertIn("aws_csm_onboarding", summary.get("missing_tool_ids") or [])
            self.assertIn("cts_gis", summary.get("missing_tool_ids") or [])
            self.assertIn("aws_narrow_write", summary.get("invalid_tool_ids") or [])
            self.assertIn("ghost_tool", summary.get("unknown_tool_ids") or [])

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
            self.assertTrue(payload["portal_build_id"])
            bundle = payload.get("portal_static_bundle") or {}
            self.assertTrue(bundle.get("static_ok"))
            self.assertTrue(bundle.get("portal_css_present"))
            self.assertTrue(bundle.get("v2_portal_shell_js_present"))
            self.assertGreater(int(bundle.get("portal_css_size_bytes") or 0), 0)
            self.assertEqual(bundle.get("static_url_path"), "/portal/static")
            contract = payload.get("surface_contract") or {}
            self.assertEqual(contract.get("schema"), TRUSTED_TENANT_SURFACE_CONTRACT_SCHEMA)
            self.assertEqual(contract.get("routes"), [dict(route) for route in TRUSTED_TENANT_ROUTE_CATALOG])
            self.assertEqual(contract.get("static_bundle_path"), TRUSTED_TENANT_STATIC_BUNDLE_PATH)
            self.assertEqual(contract.get("required_static_markers"), list(TRUSTED_TENANT_STATIC_RENDER_MARKERS))
            self.assertEqual(payload["datum_health"]["row_count"], 1)
            self.assertEqual(payload["datum_health"]["readiness_status"]["anthology_status"], "loaded")
            self.assertIn("derived_materialization", payload["datum_health"]["readiness_status"])
            self.assertTrue(payload["aws_config_health"]["live_profile_mapping"])
            tool_exposure = payload.get("tool_exposure") or {}
            self.assertEqual(
                sorted(tool_exposure.get("enabled_tool_ids") or []),
                ["aws", "aws_csm_onboarding", "aws_narrow_write"],
            )
            self.assertEqual(
                sorted(tool_exposure.get("disabled_tool_ids") or []),
                ["aws_csm_newsletter", "aws_csm_sandbox", "cts_gis"],
            )
            self.assertEqual(tool_exposure.get("unknown_tool_ids"), [])
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
            comp = shell_payload.get("shell_composition") or {}
            self.assertEqual(comp.get("schema"), ADMIN_SHELL_COMPOSITION_SCHEMA)
            regions = comp.get("regions") or {}
            self.assertIn("activity_bar", regions)
            self.assertIn("workbench", regions)
            activity_items = regions.get("activity_bar", {}).get("items") or []
            self.assertEqual(
                [item.get("slice_id") for item in activity_items],
                [
                    ADMIN_HOME_STATUS_SLICE_ID,
                    ADMIN_NETWORK_ROOT_SLICE_ID,
                    ADMIN_HOME_STATUS_SLICE_ID,
                    ADMIN_TOOL_REGISTRY_SLICE_ID,
                    AWS_READ_ONLY_SLICE_ID,
                ],
            )

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

            sandbox = client.post(
                "/portal/api/v2/admin/aws/csm-sandbox/read-only",
                json={
                    "schema": ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
                },
            )
            self.assertEqual(sandbox.status_code, 404)
            sandbox_payload = sandbox.get_json() or {}
            self.assertEqual(sandbox_payload["error"]["code"], ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE)

            datum = client.get("/portal/api/v2/data/system/resource-workbench")
            self.assertEqual(datum.status_code, 200)
            datum_payload = datum.get_json() or {}
            self.assertEqual(datum_payload["schema"], SYSTEM_DATUM_RESOURCE_WORKBENCH_SCHEMA)
            self.assertEqual(datum_payload["row_count"], 1)
            self.assertEqual(datum_payload["selected_document"]["source_kind"], "system_anthology")

            public_json = client.get("/msn-example.json")
            self.assertEqual(public_json.status_code, 200)
            self.assertEqual(public_json.get_json(), {"ok": True})
            public_json.close()

    def test_system_resource_workbench_prefers_sandbox_source_and_reports_diagnostics(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = _build_config(root)
            (config.data_dir / "sandbox" / "maps" / "sources").mkdir(parents=True)
            (config.data_dir / "sandbox" / "maps" / "tool.maps.json").write_text(
                json.dumps(
                    {
                        "3-1-2": [["3-1-2", "2-0-2", "0"], ["SAMRAS-babelette-msn_id"]],
                        "3-1-3": [["3-1-3", "2-1-1", "0"], ["title-babelette"]],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (config.data_dir / "sandbox" / "maps" / "sources" / "sc.example.json").write_text(
                json.dumps(
                    {
                        "anchor_file_version": "<hash here>",
                        "datum_addressing_abstraction_space": {
                            "4-2-118": [
                                ["4-2-118", "rf.3-1-2", "3-2-3-17-77-1", "rf.3-1-3", "HERE"],
                                ["summit_county_cities"],
                            ]
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            client = create_app(config).test_client()

            datum = client.get("/portal/api/v2/data/system/resource-workbench")
            self.assertEqual(datum.status_code, 200)
            payload = datum.get_json() or {}
            self.assertEqual(payload["selected_document"]["document_name"], "sc.example.json")
            self.assertEqual(payload["selected_document"]["anchor_document_name"], "tool.maps.json")
            self.assertIn("illegal_magnitude_literal", payload["rows"][0]["diagnostic_states"])
            self.assertEqual(payload["rows"][0]["primary_value_token"], "HERE")

    def test_portal_home_bootstraps_trusted_tenant_runtime_and_home_api_returns_band1_surface(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = _build_config(root)
            _write_publication_home_data(config)
            client = create_app(config).test_client()

            portal = client.get("/portal/home")
            self.assertEqual(portal.status_code, 200)
            body = portal.get_data(as_text=True)
            self.assertIn('data-shell-endpoint="/portal/api/v2/tenant/home"', body)
            self.assertIn('data-runtime-envelope-schema="mycite.v2.portal.runtime.envelope.v1"', body)

            home = client.post(
                "/portal/api/v2/tenant/home",
                json={
                    "schema": TRUSTED_TENANT_PORTAL_REQUEST_SCHEMA,
                    "requested_slice_id": BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
                    "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
                },
            )
            self.assertEqual(home.status_code, 200)
            payload = home.get_json() or {}
            self.assertEqual(payload["schema"], TRUSTED_TENANT_RUNTIME_ENVELOPE_SCHEMA)
            self.assertEqual(payload["slice_id"], BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID)
            self.assertEqual(
                payload["surface_payload"]["tenant_profile"]["profile_title"],
                "Trapp Family Farm",
            )
            self.assertEqual(
                payload["surface_payload"]["tenant_profile"]["public_website_url"],
                "https://trappfamilyfarm.com",
            )
            self.assertEqual(
                [entry["slice_id"] for entry in payload["surface_payload"]["available_slices"]],
                [
                    BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
                    BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
                    BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
                    BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID,
                ],
            )

    def test_portal_status_bootstraps_operational_status_runtime_and_api_returns_band1_surface(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = _build_config(root)
            config.admin_audit_storage_file.write_text(
                json.dumps(
                    {
                        "record_id": "admin-0001",
                        "recorded_at_unix_ms": 1770000000001,
                        "record": {
                            "event_type": "admin.shell.transition.accepted",
                            "focus_subject": "3-2-3-17-77-1-6-4-1-4.4-1-77",
                            "shell_verb": "navigate",
                            "details": {"surface": "internal-admin"},
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            client = create_app(config).test_client()

            portal = client.get("/portal/status")
            self.assertEqual(portal.status_code, 200)
            body = portal.get_data(as_text=True)
            self.assertIn('data-shell-endpoint="/portal/api/v2/tenant/operational-status"', body)
            self.assertIn('data-runtime-envelope-schema="mycite.v2.portal.runtime.envelope.v1"', body)

            status = client.post(
                "/portal/api/v2/tenant/operational-status",
                json={
                    "schema": TRUSTED_TENANT_OPERATIONAL_STATUS_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
                },
            )
            self.assertEqual(status.status_code, 200)
            payload = status.get_json() or {}
            self.assertEqual(payload["schema"], TRUSTED_TENANT_RUNTIME_ENVELOPE_SCHEMA)
            self.assertEqual(payload["slice_id"], BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID)
            self.assertEqual(
                payload["surface_payload"]["audit_persistence"]["health_state"],
                "no_recent_persistence_evidence",
            )
            self.assertEqual(
                [entry["slice_id"] for entry in payload["surface_payload"]["available_slices"]],
                [
                    BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
                    BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
                    BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
                    BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID,
                ],
            )
            self.assertEqual(
                payload["shell_composition"]["regions"]["workbench"]["kind"],
                "operational_status",
            )

            config.aws_audit_storage_file.write_text(
                json.dumps(
                    {
                        "record_id": "tenant-0001",
                        "recorded_at_unix_ms": 1770000000002,
                        "record": {
                            "event_type": "aws.narrow_write.applied",
                            "focus_subject": "3-2-3-17-77-1-6-4-1-4.4-1-77",
                            "shell_verb": "submit",
                            "details": {"profile_id": "aws-csm.tff.technicalContact"},
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            status_after_tenant_audit = client.post(
                "/portal/api/v2/tenant/operational-status",
                json={
                    "schema": TRUSTED_TENANT_OPERATIONAL_STATUS_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
                },
            )
            self.assertEqual(status_after_tenant_audit.status_code, 200)
            payload_after_tenant_audit = status_after_tenant_audit.get_json() or {}
            self.assertEqual(
                payload_after_tenant_audit["surface_payload"]["audit_persistence"]["health_state"],
                "recent_persistence_observed",
            )
            self.assertEqual(
                payload_after_tenant_audit["surface_payload"]["audit_persistence"]["latest_recorded_at_unix_ms"],
                1770000000002,
            )

    def test_portal_activity_bootstraps_audit_activity_runtime_and_uses_trusted_tenant_sink_only(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = _build_config(root)
            config.admin_audit_storage_file.write_text(
                json.dumps(
                    {
                        "record_id": "admin-0001",
                        "recorded_at_unix_ms": 1770000000001,
                        "record": {
                            "event_type": "admin.shell.transition.accepted",
                            "focus_subject": "3-2-3-17-77-1-6-4-1-4.4-1-77",
                            "shell_verb": "navigate",
                            "details": {"surface": "internal-admin"},
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            client = create_app(config).test_client()

            portal = client.get("/portal/activity")
            self.assertEqual(portal.status_code, 200)
            body = portal.get_data(as_text=True)
            self.assertIn('data-shell-endpoint="/portal/api/v2/tenant/audit-activity"', body)
            self.assertIn('data-runtime-envelope-schema="mycite.v2.portal.runtime.envelope.v1"', body)

            activity = client.post(
                "/portal/api/v2/tenant/audit-activity",
                json={
                    "schema": TRUSTED_TENANT_AUDIT_ACTIVITY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
                },
            )
            self.assertEqual(activity.status_code, 200)
            payload = activity.get_json() or {}
            self.assertEqual(payload["schema"], TRUSTED_TENANT_RUNTIME_ENVELOPE_SCHEMA)
            self.assertEqual(payload["slice_id"], BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID)
            self.assertEqual(payload["surface_payload"]["recent_activity"]["activity_state"], "empty")
            self.assertEqual(
                [entry["slice_id"] for entry in payload["surface_payload"]["available_slices"]],
                [
                    BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
                    BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
                    BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
                    BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID,
                ],
            )
            self.assertEqual(
                payload["shell_composition"]["regions"]["workbench"]["kind"],
                "audit_activity",
            )
            self.assertNotIn("external_events", payload["surface_payload"])

            config.aws_audit_storage_file.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "record_id": "tenant-0001",
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
                                "record_id": "tenant-0002",
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
            activity_after_tenant_audit = client.post(
                "/portal/api/v2/tenant/audit-activity",
                json={
                    "schema": TRUSTED_TENANT_AUDIT_ACTIVITY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
                },
            )
            self.assertEqual(activity_after_tenant_audit.status_code, 200)
            payload_after_tenant_audit = activity_after_tenant_audit.get_json() or {}
            self.assertEqual(
                payload_after_tenant_audit["surface_payload"]["recent_activity"]["activity_state"],
                "recent_activity_observed",
            )
            self.assertEqual(
                [record["record_id"] for record in payload_after_tenant_audit["surface_payload"]["recent_activity"]["records"]],
                ["tenant-0002", "tenant-0001"],
            )

    def test_portal_profile_basics_bootstraps_write_surface_and_uses_trusted_tenant_audit_sink(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = _build_config(root)
            _write_publication_home_data(config)
            config.admin_audit_storage_file.write_text(
                json.dumps(
                    {
                        "record_id": "admin-0001",
                        "recorded_at_unix_ms": 1770000000001,
                        "record": {
                            "event_type": "admin.shell.transition.accepted",
                            "focus_subject": "3-2-3-17-77-1-6-4-1-4.4-1-77",
                            "shell_verb": "navigate",
                            "details": {"surface": "internal-admin"},
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            client = create_app(config).test_client()

            portal = client.get("/portal/profile-basics")
            self.assertEqual(portal.status_code, 200)
            body = portal.get_data(as_text=True)
            self.assertIn('data-shell-endpoint="/portal/api/v2/tenant/profile-basics"', body)
            self.assertIn('data-runtime-envelope-schema="mycite.v2.portal.runtime.envelope.v1"', body)

            bootstrap = client.post(
                "/portal/api/v2/tenant/profile-basics",
                json={
                    "schema": TRUSTED_TENANT_PROFILE_BASICS_WRITE_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
                },
            )
            self.assertEqual(bootstrap.status_code, 200)
            payload = bootstrap.get_json() or {}
            self.assertEqual(payload["schema"], TRUSTED_TENANT_RUNTIME_ENVELOPE_SCHEMA)
            self.assertEqual(payload["slice_id"], BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID)
            self.assertEqual(payload["surface_payload"]["write_status"], "ready")
            self.assertEqual(
                payload["surface_payload"]["confirmed_profile_basics"]["profile_summary"],
                "Read-only summary for the trusted-tenant landing surface.",
            )

            update = client.post(
                "/portal/api/v2/tenant/profile-basics",
                json={
                    "schema": TRUSTED_TENANT_PROFILE_BASICS_WRITE_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
                    "apply_change": True,
                    "profile_title": "Trapp Family Farm",
                    "profile_summary": "Updated summary from the trusted-tenant write surface.",
                    "contact_email": "hello@trappfamilyfarm.com",
                    "public_website_url": "https://trappfamilyfarm.com",
                },
            )
            self.assertEqual(update.status_code, 200)
            update_payload = update.get_json() or {}
            self.assertEqual(update_payload["surface_payload"]["write_status"], "applied")
            self.assertEqual(
                update_payload["surface_payload"]["confirmed_profile_basics"]["profile_summary"],
                "Updated summary from the trusted-tenant write surface.",
            )
            self.assertTrue(update_payload["surface_payload"]["audit"]["record_id"])
            stored_tenant_profile = json.loads(
                (config.public_dir / "fnd-3-2-3-17-77-2-6-3-1-6.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                stored_tenant_profile["summary"],
                "Updated summary from the trusted-tenant write surface.",
            )
            self.assertEqual(stored_tenant_profile["contact_email"], "hello@trappfamilyfarm.com")
            self.assertFalse(config.admin_audit_storage_file.read_text(encoding="utf-8").count("publication.profile_basics"))
            self.assertIn(
                "publication.profile_basics.write.accepted",
                config.aws_audit_storage_file.read_text(encoding="utf-8"),
            )

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
                self.assertIn(b"v2-bootstrap-shell-request", home.data)
                self.assertIn(b"band1.portal_home_tenant_status", home.data)
                self.assertIn(b"/portal/api/v2/tenant/home", home.data)
                self.assertIn(b"shell-template: v2-composition", home.data)
                self.assertIn(b"/portal/static/portal.css", home.data)
            finally:
                home.close()

            system = client.get("/portal/system")
            try:
                self.assertEqual(system.status_code, 200)
                self.assertIn(b"ide-shell", system.data)
                self.assertIn(b"v2_portal_shell.js", system.data)
                self.assertIn(b"admin_band0.home_status", system.data)
            finally:
                system.close()

            system_sources = client.get("/portal/system?tab=sources")
            try:
                self.assertEqual(system_sources.status_code, 200)
                self.assertIn(b'"root_tab": "sources"', system_sources.data)
            finally:
                system_sources.close()

    def test_url_deep_linking_bootstraps_to_correct_slice(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = _build_config(root)
            client = create_app(config).test_client()

            network_page = client.get("/portal/network")
            try:
                self.assertEqual(network_page.status_code, 200)
                self.assertIn(ADMIN_NETWORK_ROOT_SLICE_ID.encode(), network_page.data)
            finally:
                network_page.close()

            utilities_page = client.get("/portal/utilities")
            try:
                self.assertEqual(utilities_page.status_code, 200)
                self.assertIn(ADMIN_TOOL_REGISTRY_SLICE_ID.encode(), utilities_page.data)
            finally:
                utilities_page.close()

            utilities_config = client.get("/portal/utilities?tab=config")
            try:
                self.assertEqual(utilities_config.status_code, 200)
                self.assertIn(b'"root_tab": "config"', utilities_config.data)
            finally:
                utilities_config.close()

            tools_page = client.get("/portal/system/tools")
            try:
                self.assertEqual(tools_page.status_code, 200)
                self.assertIn(ADMIN_TOOL_REGISTRY_SLICE_ID.encode(), tools_page.data)
            finally:
                tools_page.close()

            utility_aws_page = client.get("/portal/utilities/aws-csm")
            try:
                self.assertEqual(utility_aws_page.status_code, 200)
                self.assertIn(AWS_READ_ONLY_SLICE_ID.encode(), utility_aws_page.data)
            finally:
                utility_aws_page.close()

            aws_page = client.get("/portal/system/aws")
            try:
                self.assertEqual(aws_page.status_code, 200)
                self.assertIn(AWS_READ_ONLY_SLICE_ID.encode(), aws_page.data)
            finally:
                aws_page.close()

            onboarding_page = client.get("/portal/system/aws-csm-onboarding")
            try:
                self.assertEqual(onboarding_page.status_code, 200)
                self.assertIn(AWS_CSM_ONBOARDING_SLICE_ID.encode(), onboarding_page.data)
            finally:
                onboarding_page.close()

            sandbox_page = client.get("/portal/system/aws-csm-sandbox")
            try:
                self.assertEqual(sandbox_page.status_code, 200)
                self.assertIn(AWS_CSM_SANDBOX_SLICE_ID.encode(), sandbox_page.data)
            finally:
                sandbox_page.close()

            datum_page = client.get("/portal/system/datum")
            try:
                self.assertEqual(datum_page.status_code, 200)
                self.assertIn(DATUM_RESOURCE_WORKBENCH_SLICE_ID.encode(), datum_page.data)
            finally:
                datum_page.close()

            v1_compat = client.get("/portal/system/mediate_tool-aws_platform_admin")
            try:
                self.assertEqual(v1_compat.status_code, 200)
                self.assertIn(AWS_READ_ONLY_SLICE_ID.encode(), v1_compat.data)
            finally:
                v1_compat.close()

            tenant_actions_compat = client.get("/portal/system?mediate_tool=aws_tenant_actions")
            try:
                self.assertEqual(tenant_actions_compat.status_code, 200)
                self.assertIn(AWS_CSM_ONBOARDING_SLICE_ID.encode(), tenant_actions_compat.data)
            finally:
                tenant_actions_compat.close()

            unknown = client.get("/portal/system/nonexistent")
            try:
                self.assertEqual(unknown.status_code, 200)
                self.assertIn(b"admin_band0.home_status", unknown.data)
            finally:
                unknown.close()

    def test_fnd_cts_gis_surface_bootstraps_and_tff_cts_gis_route_stays_hidden(self) -> None:
        with TemporaryDirectory() as temp_dir:
            fnd_root = Path(temp_dir) / "fnd"
            fnd_config = _build_config(
                fnd_root,
                tenant_id="fnd",
                tool_exposure={
                    "aws": {"enabled": True},
                    "aws_csm_newsletter": {"enabled": False},
                    "aws_narrow_write": {"enabled": True},
                    "aws_csm_onboarding": {"enabled": True},
                    "aws_csm_sandbox": {"enabled": False},
                    "cts_gis": {"enabled": True},
                },
            )
            _write_maps_data(fnd_config)
            fnd_client = create_app(fnd_config).test_client()

            cts_gis_page = fnd_client.get("/portal/utilities/cts-gis")
            self.assertEqual(cts_gis_page.status_code, 200)
            self.assertIn(CTS_GIS_READ_ONLY_SLICE_ID.encode(), cts_gis_page.data)

            shell = fnd_client.post(
                "/portal/api/v2/admin/shell",
                json={
                    "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                    "requested_slice_id": CTS_GIS_READ_ONLY_SLICE_ID,
                    "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
                },
            )
            self.assertEqual(shell.status_code, 200)
            shell_payload = shell.get_json() or {}
            self.assertEqual(shell_payload["slice_id"], CTS_GIS_READ_ONLY_SLICE_ID)
            self.assertEqual(shell_payload["shell_composition"]["regions"]["workbench"]["kind"], "cts_gis_workbench")

            direct = fnd_client.post(
                "/portal/api/v2/admin/cts-gis/read-only",
                json={
                    "schema": ADMIN_CTS_GIS_READ_ONLY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
                },
            )
            self.assertEqual(direct.status_code, 200)
            direct_payload = direct.get_json() or {}
            self.assertEqual(direct_payload["entrypoint_id"], CTS_GIS_READ_ONLY_ENTRYPOINT_ID)
            self.assertEqual(direct_payload["slice_id"], CTS_GIS_READ_ONLY_SLICE_ID)
            self.assertGreater(
                int(
                    ((direct_payload.get("surface_payload") or {}).get("map_projection") or {}).get(
                        "feature_count"
                    )
                    or 0
                ),
                0,
            )

            tff_root = Path(temp_dir) / "tff"
            tff_config = _build_config(tff_root, tenant_id="tff")
            tff_client = create_app(tff_config).test_client()
            hidden = tff_client.post(
                "/portal/api/v2/admin/cts-gis/read-only",
                json={
                    "schema": ADMIN_CTS_GIS_READ_ONLY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
                },
            )
            self.assertEqual(hidden.status_code, 404)
            hidden_payload = hidden.get_json() or {}
            self.assertEqual(hidden_payload["error"]["code"], ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE)

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

    def test_invalid_live_aws_mapping_fails_fast_at_startup(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            status_file = root / "aws-status.json"
            status_file.write_text(json.dumps({"tenant_scope_id": "tff"}) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "MYCITE_V2_AWS_STATUS_FILE"):
                create_app(_build_config(root, aws_status_file=status_file))


if __name__ == "__main__":
    unittest.main()
