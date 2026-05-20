"""Phase 1 + 2 of the Agro-ERP workbench materialization (2026-05-17).

Verifies:
  * /portal/system/tools/agro-erp resolves (200) with the portal shell HTML
  * the Agro-ERP surface bundle pins the agro_erp identifiers
  * the bootstrapped agro_erp.anchor + agro_erp.txa documents are listed
  * the new_source_document_form slot is present and well-shaped
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None
LIVE_DB = Path("/srv/webapps/mycite/fnd/private/mos_authority.sqlite3")

if FLASK_AVAILABLE:
    from MyCiteV2.instances._shared.portal_host.app import V2PortalHostConfig, create_app

from MyCiteV2.instances._shared.runtime.portal_agro_erp_runtime import (
    AGRO_ERP_TOOL_SURFACE_SCHEMA,
    build_portal_agro_erp_surface_bundle,
)
from MyCiteV2.packages.state_machine.portal_shell import (
    AGRO_ERP_SANDBOX_TOKEN,
    AGRO_ERP_TOOL_ROUTE,
    AGRO_ERP_TOOL_SURFACE_ID,
    PortalScope,
)


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not available")
@unittest.skipUnless(LIVE_DB.exists(), "live MOS authority db not present")
class PortalAgroErpRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="agro_erp_route_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain="fruitfulnetworkdevelopment.com",
            webapps_root=tmp / "webapps",
            authority_db_file=LIVE_DB,
        )
        self.client = create_app(config).test_client()

    def test_route_resolves_with_portal_shell(self) -> None:
        # Plan v2: the agro-erp tool URL 302-redirects into the unified
        # workbench at /portal/system?sandbox=agro_erp. Following the
        # redirect should land on a 200 system page whose bootstrap
        # request carries the system root surface id.
        response = self.client.get(AGRO_ERP_TOOL_ROUTE, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/portal/system", response.headers["Location"])
        self.assertIn("sandbox=agro_erp", response.headers["Location"])
        # The system root resolves cleanly.
        followed = self.client.get(AGRO_ERP_TOOL_ROUTE, follow_redirects=True)
        self.assertEqual(followed.status_code, 200)


@unittest.skipUnless(LIVE_DB.exists(), "live MOS authority db not present")
class PortalAgroErpSurfaceBundleTests(unittest.TestCase):
    def _scope(self) -> PortalScope:
        return PortalScope(scope_id="fnd", capabilities=("datum_recognition",))

    def test_surface_payload_pins_agro_erp_identifiers(self) -> None:
        bundle = build_portal_agro_erp_surface_bundle(
            portal_scope=self._scope(),
            portal_domain="fruitfulnetworkdevelopment.com",
            shell_state=None,
            authority_db_file=LIVE_DB,
        )
        payload = bundle.get("surface_payload", {})
        self.assertEqual(payload.get("schema"), AGRO_ERP_TOOL_SURFACE_SCHEMA)
        self.assertEqual(payload.get("kind"), "agro_erp_workbench")
        self.assertEqual(payload.get("title"), "Agro-ERP")
        request_contract = payload.get("request_contract", {})
        self.assertEqual(request_contract.get("surface_id"), AGRO_ERP_TOOL_SURFACE_ID)
        self.assertEqual(request_contract.get("route"), AGRO_ERP_TOOL_ROUTE)

    def test_documents_filtered_to_agro_erp_sandbox(self) -> None:
        bundle = build_portal_agro_erp_surface_bundle(
            portal_scope=self._scope(),
            portal_domain="fruitfulnetworkdevelopment.com",
            shell_state=None,
            authority_db_file=LIVE_DB,
        )
        documents = (
            bundle.get("workbench", {})
            .get("document_collection", {})
            .get("documents", [])
        )
        # The 2026-05-17 bootstrap created exactly 2 agro_erp documents
        # (anchor + txa). The workbench surface lists both.
        self.assertGreaterEqual(len(documents), 2)
        document_ids = [str(d.get("document_id") or "") for d in documents]
        for doc_id in document_ids:
            self.assertIn(f".{AGRO_ERP_SANDBOX_TOKEN}.", doc_id)
        self.assertTrue(
            any("agro_erp.anchor." in d for d in document_ids),
            "agro_erp anchor not listed in workbench surface",
        )
        self.assertTrue(
            any("agro_erp.txa." in d for d in document_ids),
            "agro_erp txa source not listed in workbench surface",
        )

    def test_new_source_document_form_is_present(self) -> None:
        bundle = build_portal_agro_erp_surface_bundle(
            portal_scope=self._scope(),
            portal_domain="fruitfulnetworkdevelopment.com",
            shell_state=None,
            authority_db_file=LIVE_DB,
        )
        form = bundle.get("surface_payload", {}).get("new_source_document_form")
        self.assertIsNotNone(form, "new_source_document_form slot missing")
        self.assertEqual(form.get("sandbox_id"), AGRO_ERP_SANDBOX_TOKEN)
        self.assertEqual(form.get("msn_id_default"), "3-2-3-17-77-1-6-4-1-4")
        self.assertEqual(form.get("endpoint_stage"), "/portal/api/v2/mutations/stage")
        name_input = form.get("name_input") or {}
        self.assertEqual(name_input.get("field"), "document_name")
        self.assertEqual(name_input.get("pattern"), "^[a-z][a-z0-9_]*$")
        # available_templates must include the agro_erp_taxonomy_source template
        templates = form.get("available_templates") or []
        template_ids = [str(t.get("template_id")) for t in templates]
        self.assertIn("agro_erp_taxonomy_source", template_ids)


if __name__ == "__main__":
    unittest.main()
