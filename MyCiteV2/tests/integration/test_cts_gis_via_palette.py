"""Eligibility integration test — cts_gis + workbench_ui RETIRED from the palette.

History: CTS-GIS was decomposed into thin palette tools that gated on
``applies_to_source_kind=("sandbox_source",)``, and ``workbench_ui`` (the workbench
surface) was registered the same way. Because every sandbox document is stamped
``source_kind="sandbox_source"``, both appeared on EVERY document — the operator-flagged
drift. They are now retired from the viz palette (no honest per-doc eligibility): the cts
tools render a doc-independent compiled artifact and cts docs carry no reliable per-doc
archetype; workbench_ui is a surface, not a tool. This test pins the corrected behavior.
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

_RETIRED = {"cts_gis", "cts_gis_admin", "cts_gis_district", "workbench_ui"}


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
    def _eligible_tool_ids(self, doc: AuthoritativeDatumDocument) -> list[str]:
        out = build_eligible_tools_response(
            tenant_id="fnd",
            document_id=doc.document_id,
            datum_address="0-0-1",
            datum_store=_StubDatumStore(documents=(doc,)),
        )
        return [tool["tool_id"] for tool in out["tools"]]

    def test_samras_sandbox_document_offers_no_retired_tools(self) -> None:
        # A sandbox_source doc with a samras_family token no longer surfaces cts_gis /
        # workbench_ui via the broad source_kind bucket. It carries no real tool archetype.
        doc = _document(
            doc_id="lv.fnd.cts_gis.samras_fixture.deadbeef",
            source_kind="sandbox_source",
            archetype="samras_family",
        )
        self.assertEqual(set(self._eligible_tool_ids(doc)) & _RETIRED, set())

    def test_sandbox_document_without_archetype_offers_nothing_via_source_kind(self) -> None:
        # source_kind="sandbox_source" is no longer a discriminator for any tool.
        doc = _document(
            doc_id="lv.fnd.legacy.fixture.cafebabe",
            source_kind="sandbox_source",
            archetype=None,
        )
        self.assertEqual(self._eligible_tool_ids(doc), [])

    def test_system_anthology_offers_nothing(self) -> None:
        doc = _document(
            doc_id="lv.fnd.system.anthology.facefade",
            source_kind="system_anthology",
            archetype=None,
        )
        self.assertEqual(self._eligible_tool_ids(doc), [])


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class CtsGisPaletteHTTPEndpointTests(unittest.TestCase):
    def _build_app(self):
        tmp = Path(tempfile.mkdtemp(prefix="palette_"))
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

    def test_endpoint_does_not_return_retired_tools_for_samras_doc(self) -> None:
        doc = _document(
            doc_id="lv.fnd.cts_gis.endpoint_fixture.beadcafe",
            source_kind="sandbox_source",
            archetype="samras_family",
        )
        client = self._build_app().test_client()
        with patch(
            "MyCiteV2.instances._shared.datum_store_accessor._datum_store_for_authority_db",
            return_value=_StubDatumStore(documents=(doc,)),
        ):
            resp = client.get(
                f"/portal/api/tools/eligible?document_id={doc.document_id}&datum_address=0-0-1"
            )
        self.assertEqual(resp.status_code, 200)
        tool_ids = {tool["tool_id"] for tool in resp.get_json()["tools"]}
        self.assertEqual(tool_ids & _RETIRED, set())


if __name__ == "__main__":
    unittest.main()
