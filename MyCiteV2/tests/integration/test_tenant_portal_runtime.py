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
    TRUSTED_TENANT_HOME_SURFACE_SCHEMA,
    TRUSTED_TENANT_PORTAL_ENTRYPOINT_ID,
    TRUSTED_TENANT_RUNTIME_ENVELOPE_SCHEMA,
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


if __name__ == "__main__":
    unittest.main()
