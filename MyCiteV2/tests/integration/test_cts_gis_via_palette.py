"""Phase 4 integration test for CTS-GIS as a palette tool.

Per portal_tool_surface_contract.md, CTS-GIS is reduced to a palette tool with
applies_to_archetype=("samras_family",) and applies_to_source_kind=("sandbox_source",).
This test exercises the palette pipeline end-to-end:

  1. Seed a SAMRAS-archetype sandbox-source document via a stub datum store.
  2. Hit GET /portal/api/tools/eligible?document_id=...&datum_address=...
  3. Assert cts_gis appears in the tools list with the workbench_ui sibling
     (which also applies to sandbox_source docs).
  4. Confirm a sandbox_source document with mismatched archetype still
     surfaces both tools via the source_kind fallback.
  5. Confirm a system_anthology document surfaces only workbench_ui (since
     cts_gis does not apply).

See portal_tool_surface_contract.md and
/home/admin/.claude/plans/temporal-wandering-bengio.md (Phase 4).
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
    build_eligible_tools_response,
)
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentCatalogResult,
    AuthoritativeDatumDocumentRow,
)


class _StubDatumStore:
    def __init__(self, documents):
        self._documents = documents

    def read_authoritative_datum_documents(self, request):
        return AuthoritativeDatumDocumentCatalogResult(
            tenant_id=getattr(request, "tenant_id", "fnd"),
            documents=self._documents,
            source_files={},
            readiness_status={},
            warnings=(),
        )


def _document(*, doc_id: str, source_kind: str, archetype: str | None = None) -> AuthoritativeDatumDocument:
    metadata = {"archetype": archetype} if archetype else None
    return AuthoritativeDatumDocument(
        document_id=doc_id,
        source_kind=source_kind,
        document_name="fixture",
        relative_path="fixture.json",
        canonical_name="fixture",
        document_metadata=metadata,
        rows=(AuthoritativeDatumDocumentRow(datum_address="0-0-1", raw={"value": "rudi"}),),
    )


class CtsGisPaletteEligibilityTests(unittest.TestCase):
    """Drives build_eligible_tools_response against the real registry to confirm
    Phase 4 applies_to_* settings produce the expected palette."""

    def _eligible_tool_ids(self, doc: AuthoritativeDatumDocument) -> list[str]:
        out = build_eligible_tools_response(
            tenant_id="fnd",
            document_id=doc.document_id,
            datum_address="0-0-1",
            datum_store=_StubDatumStore(documents=(doc,)),
        )
        return [tool["tool_id"] for tool in out["tools"]]

    def test_samras_sandbox_document_offers_both_cts_gis_and_workbench_ui(self) -> None:
        doc = _document(
            doc_id="lv.fnd.cts_gis.samras_fixture.deadbeef",
            source_kind="sandbox_source",
            archetype="samras_family",
        )
        self.assertEqual(self._eligible_tool_ids(doc), ["cts_gis", "workbench_ui"])

    def test_sandbox_document_without_archetype_still_offers_both_via_source_kind(self) -> None:
        # Pre-archetype-metadata documents (the common case today) match via
        # applies_to_source_kind=("sandbox_source",). Both tools surface.
        doc = _document(
            doc_id="lv.fnd.legacy.fixture.cafebabe",
            source_kind="sandbox_source",
            archetype=None,
        )
        self.assertEqual(self._eligible_tool_ids(doc), ["cts_gis", "workbench_ui"])

    def test_system_anthology_offers_only_workbench_ui(self) -> None:
        # cts_gis does not apply to system_anthology source; workbench_ui does.
        doc = _document(
            doc_id="lv.fnd.system.anthology.facefade",
            source_kind="system_anthology",
            archetype=None,
        )
        self.assertEqual(self._eligible_tool_ids(doc), ["workbench_ui"])


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class CtsGisPaletteHTTPEndpointTests(unittest.TestCase):
    """Exercises the HTTP endpoint with the registry's real tool entries."""

    def _build_app(self):
        tmp = Path(tempfile.mkdtemp(prefix="phase4_palette_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        return create_app(
            V2PortalHostConfig(
                portal_instance_id="fnd",
                public_dir=tmp / "public",
                private_dir=tmp / "private",
                data_dir=tmp / "data",
                portal_domain="example.org",
                webapps_root=tmp / "webapps",
            )
        )

    def test_endpoint_returns_cts_gis_and_workbench_ui_for_samras_doc(self) -> None:
        doc = _document(
            doc_id="lv.fnd.cts_gis.endpoint_fixture.beadcafe",
            source_kind="sandbox_source",
            archetype="samras_family",
        )
        client = self._build_app().test_client()
        # The endpoint pulls the datum_store from authority_db_file (None in
        # this fixture). Patch the resolver to return our stub so we exercise
        # the same code path the production system uses.
        with patch(
            "MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime._datum_store_for_authority_db",
            return_value=_StubDatumStore(documents=(doc,)),
        ):
            resp = client.get(
                f"/portal/api/tools/eligible?document_id={doc.document_id}&datum_address=0-0-1"
            )
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        tool_ids = [tool["tool_id"] for tool in payload["tools"]]
        self.assertIn("cts_gis", tool_ids)
        self.assertIn("workbench_ui", tool_ids)


if __name__ == "__main__":
    unittest.main()
