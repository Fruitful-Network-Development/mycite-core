"""Phase 3 integration tests for the portal tool palette.

Covers:
  - the GET /portal/api/tools/eligible endpoint exists and 200s
  - with no document context (welcome screen), the palette returns every
    registered viz tool so the menubar search input is useful immediately
    (see portal_palette_runtime._viz_tool_matches comment)
  - build_eligible_tools_response() resolves a document via the datum store and
    returns the subset of registry entries whose applies_to_archetype matches
  - each tool entry carries the dispatch ``route`` the JS palette reads from
    its ``data-route`` attribute on click

See portal_tool_surface_contract.md and the approved plan
/home/admin/.claude/plans/temporal-wandering-bengio.md (Phase 3).
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None

if FLASK_AVAILABLE:
    from MyCiteV2.instances._shared.portal_host.app import V2PortalHostConfig, create_app

from MyCiteV2.instances._shared.runtime.portal_palette_runtime import (
    PORTAL_PALETTE_RESPONSE_SCHEMA,
    build_eligible_tools_response,
)
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentCatalogResult,
    AuthoritativeDatumDocumentRow,
)
from MyCiteV2.packages.state_machine.portal_shell import (
    ARCHETYPE_SAMRAS_FAMILY,
    CTS_GIS_TOOL_ENTRYPOINT_ID,
    CTS_GIS_TOOL_ROUTE,
    CTS_GIS_TOOL_SURFACE_ID,
    SURFACE_POSTURE_PALETTE_TARGET,
    TOOL_KIND_GENERAL,
    PortalToolRegistryEntry,
)


class _StubDatumStore:
    """Returns a fixed catalog. Used to drive the palette runtime without
    needing a real Sqlite-backed authoritative store."""

    def __init__(self, documents: tuple[AuthoritativeDatumDocument, ...]):
        self._documents = documents

    def read_authoritative_datum_documents(self, request):
        return AuthoritativeDatumDocumentCatalogResult(
            tenant_id=getattr(request, "tenant_id", "fnd"),
            documents=self._documents,
            source_files={},
            readiness_status={},
            warnings=(),
        )


def _samras_document() -> AuthoritativeDatumDocument:
    # ``datum_template_archetype`` is the metadata key the palette runtime
    # reads (portal_palette_runtime.build_eligible_tools_response line ~108);
    # the older ``archetype`` shorthand is unused and silently misses the
    # archetype-matching branch.
    return AuthoritativeDatumDocument(
        document_id="lv.fnd.test.samras_fixture.deadbeef",
        source_kind="sandbox_source",
        document_name="samras_fixture",
        relative_path="samras_fixture.json",
        canonical_name="samras_fixture",
        document_metadata={"datum_template_archetype": ARCHETYPE_SAMRAS_FAMILY},
        rows=(
            AuthoritativeDatumDocumentRow(datum_address="0-0-1", raw={"value": "a"}),
        ),
    )


def _palette_tool(tool_id: str, archetype: str) -> PortalToolRegistryEntry:
    return PortalToolRegistryEntry(
        tool_id=tool_id,
        label=tool_id,
        surface_id=CTS_GIS_TOOL_SURFACE_ID,
        entrypoint_id=CTS_GIS_TOOL_ENTRYPOINT_ID,
        route=CTS_GIS_TOOL_ROUTE,
        tool_kind=TOOL_KIND_GENERAL,
        surface_posture=SURFACE_POSTURE_PALETTE_TARGET,
        read_write_posture="write",
        applies_to_archetype=(archetype,),
    )


class BuildEligibleToolsResponseTests(unittest.TestCase):
    def test_returns_all_registered_tools_when_params_missing(self) -> None:
        # Welcome-screen behavior: with no document context, every registered
        # viz tool is returned so the menubar search input has options on
        # first load. See portal_palette_runtime._viz_tool_matches docstring.
        out = build_eligible_tools_response(
            tenant_id="fnd", document_id="", datum_address="", datum_store=None
        )
        self.assertEqual(out["schema"], PORTAL_PALETTE_RESPONSE_SCHEMA)
        tool_ids = {tool["tool_id"] for tool in out["tools"]}
        # Real per-doc viz tools are registered; the retired surface (workbench_ui) +
        # legacy fixed-artifact viewers (cts_gis*) are not. (packages/tools/__init__.py)
        self.assertIn("txa_tree", tool_ids)
        self.assertNotIn("cts_gis", tool_ids)
        self.assertNotIn("workbench_ui", tool_ids)

    def test_returns_all_registered_tools_when_document_not_in_catalog(self) -> None:
        # An unknown document_id resolves to None archetypes/source_kinds, so
        # the same welcome-screen "all tools" behavior applies.
        store = _StubDatumStore(documents=())
        out = build_eligible_tools_response(
            tenant_id="fnd",
            document_id="lv.fnd.unknown.deadbeef",
            datum_address="0-0-1",
            datum_store=store,
        )
        tool_ids = {tool["tool_id"] for tool in out["tools"]}
        self.assertIn("txa_tree", tool_ids)
        self.assertNotIn("cts_gis", tool_ids)
        self.assertNotIn("workbench_ui", tool_ids)

    def test_returns_tool_when_archetype_matches(self) -> None:
        doc = _samras_document()
        store = _StubDatumStore(documents=(doc,))
        fake_registry = (
            _palette_tool("cts_gis_fixture", ARCHETYPE_SAMRAS_FAMILY),
            _palette_tool("other_fixture", "unrelated_archetype"),
        )
        # The palette reads from the viz-tool registry (_viz_all_tools), not
        # the shell tool registry — so we patch the bound name in the palette
        # module. PortalToolRegistryEntry duck-types fine for the four
        # attributes the runtime reads (tool_id, label, summary,
        # applies_to_archetype, applies_to_source_kind, route).
        with patch(
            "MyCiteV2.instances._shared.runtime.portal_palette_runtime._viz_all_tools",
            return_value=fake_registry,
        ):
            out = build_eligible_tools_response(
                tenant_id="fnd",
                document_id=doc.document_id,
                datum_address="0-0-1",
                datum_store=store,
            )
        tool_ids = [tool["tool_id"] for tool in out["tools"]]
        self.assertEqual(tool_ids, ["cts_gis_fixture"])
        tool = out["tools"][0]
        self.assertEqual(tool["route"], CTS_GIS_TOOL_ROUTE)
        self.assertIn("label", tool)
        self.assertIn("summary", tool)


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class PaletteEndpointHTTPTests(unittest.TestCase):
    def _build_app(self):
        tmp = Path(tempfile.mkdtemp(prefix="phase3_palette_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain="example.org",
            webapps_root=tmp / "webapps",
        )
        return create_app(config)

    def test_endpoint_registered_and_returns_all_tools_without_params(self) -> None:
        # Endpoint exists and welcome-screen "all viz tools" behavior is in
        # effect when no document context is supplied.
        client = self._build_app().test_client()
        resp = client.get("/portal/api/tools/eligible")
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertEqual(payload["schema"], PORTAL_PALETTE_RESPONSE_SCHEMA)
        tool_ids = {tool["tool_id"] for tool in payload["tools"]}
        self.assertIn("txa_tree", tool_ids)
        self.assertNotIn("cts_gis", tool_ids)
        self.assertNotIn("workbench_ui", tool_ids)

    def test_endpoint_returns_all_tools_for_unknown_document(self) -> None:
        # An unknown document_id falls back to the welcome behavior.
        client = self._build_app().test_client()
        resp = client.get(
            "/portal/api/tools/eligible?document_id=lv.fnd.unknown.deadbeef&datum_address=0-0-1"
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        tool_ids = {tool["tool_id"] for tool in payload["tools"]}
        self.assertIn("txa_tree", tool_ids)
        self.assertNotIn("cts_gis", tool_ids)
        self.assertNotIn("workbench_ui", tool_ids)

    def test_palette_module_in_asset_manifest(self) -> None:
        from MyCiteV2.instances._shared.portal_host.app import build_shell_asset_manifest

        manifest = build_shell_asset_manifest()
        module_ids = {entry["module_id"] for entry in manifest["scripts"]["shell_modules"]}
        self.assertIn(
            "tool_palette",
            module_ids,
            "Phase 3a registers tool_palette in PORTAL_SHELL_MODULE_CONTRACTS",
        )
        # The palette JS file must be referenced.
        files = [entry["file"] for entry in manifest["scripts"]["shell_modules"]]
        self.assertIn("v2_portal_tool_palette.js", files)


if __name__ == "__main__":
    unittest.main()
