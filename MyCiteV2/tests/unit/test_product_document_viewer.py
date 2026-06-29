"""Tests for the product-document visualizer + sandbox-contents discovery."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_palette_runtime import (
    build_eligible_tools_response,
    build_sandbox_visualizers_response,
)
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRow,
)
from MyCiteV2.packages.tools.product_document_view import (
    LclNameIndex,
    ProductDocumentViewer,
    build_product_rows,
)

_MSN = "3-2-3-17-77-1-6-4-1-4"


def _doc(name: str, rows, *, archetype: str = "", source_kind: str = "sandbox_source"):
    return AuthoritativeDatumDocument(
        document_id=f"lv.{_MSN}.agro_erp.{name}.{'0' * 48}",
        source_kind=source_kind,
        document_name=f"lv.{_MSN}.agro_erp.{name}",
        relative_path=f"sandbox/agro-erp/{name}.json",
        canonical_name=name,
        document_metadata={"datum_template_archetype": archetype} if archetype else {},
        rows=tuple(AuthoritativeDatumDocumentRow(datum_address=a, raw=r) for a, r in rows),
    )


# A valid title-blob placeholder so each row is recognized as a definition head by the
# shape-based NameIndex (the display label still comes from the row tail). Live docs
# carry a real 512-bit ASCII title here.
_BLOB = "0" * 512
# A 136-bit ASCII nominal encoding "5 g" (the singular_unit_weight magnitude).
_UW = "".join(format(b, "08b") for b in "5 g".encode("ascii")).ljust(136, "0")


def _lcl():
    return _doc("lcl", [
        ("4-2-1", [["4-2-1", "rf.3-1-1", "1-3-2-1-3", "rf.3-1-2", _BLOB], ["brassicas"]]),
        ("4-2-2", [["4-2-2", "rf.3-1-1", "1-3-2-2-1", "rf.3-1-2", _BLOB], ["seed"]]),
        ("4-2-3", [["4-2-3", "rf.3-1-5", "1-3-1-160", "rf.3-1-2", _BLOB], ["brassica_oleracea-sidekick"]]),
    ], archetype="agro_erp_taxonomy_row")


def _txa():
    return _doc("txa", [
        ("4-2-1", [["4-2-1", "rf.3-1-1", "1-1-3-3-5-8-21-4-4-4", "rf.3-1-2", _BLOB], ["brassica_oleracea"]]),
    ])


def _product_profiles():
    head = [
        "4-10-1",
        "rf.3-1-5", "1-3-1-160",
        "rf.3-1-1", "1-1-3-3-5-8-21-4-4-4",
        "rf.3-1-1", "1-3-2-1-3",
        "rf.3-1-1", "1-3-2-2-1",
        "rf.3-1-1", "1-3-2-3-1",
        "rf.3-1-1", "1-3-2-4-1",
        "rf.3-1-1", "1-3-2-5-1",
        "2-1-1", "3542400",
        "2-1-3", "18",
        "rf.3-1-7", _UW,
    ]
    return _doc("product_profiles", [
        ("0-0-1", "schema-marker"),
        ("4-10-1", [head, ["brassica_oleracea-sidekick"]]),
    ], archetype="agro_erp_product_profile_row")


class _FakeStore:
    def __init__(self, docs):
        self._docs = tuple(docs)

    def read_authoritative_datum_documents(self, request):
        return type("R", (), {"documents": self._docs})()


class LclNameIndexTests(unittest.TestCase):
    def test_resolves_product_and_classification_nodes(self) -> None:
        idx = LclNameIndex(_lcl())
        self.assertEqual(idx.resolve("1-3-1-160"), "brassica_oleracea-sidekick")
        self.assertEqual(idx.resolve("1-3-2-1-3"), "brassicas")
        self.assertEqual(idx.resolve("1-3-2-2-1"), "seed")

    def test_unknown_node_resolves_empty(self) -> None:
        idx = LclNameIndex(_lcl())
        self.assertEqual(idx.resolve("9-9-9"), "")

    def test_none_document_is_empty(self) -> None:
        self.assertEqual(len(LclNameIndex(None)), 0)


class BuildProductRowsTests(unittest.TestCase):
    def test_resolves_all_ten_fields(self) -> None:
        rows = build_product_rows(_product_profiles(), lcl_index=LclNameIndex(_lcl()), txa_index=LclNameIndex(_txa()))
        self.assertEqual(len(rows), 1)
        product = rows[0]
        self.assertEqual(product["datum_address"], "4-10-1")
        self.assertEqual(product["product_name"], "brassica_oleracea-sidekick")
        by_field = {f["field"]: f for f in product["fields"]}
        self.assertEqual(by_field["taxonomy_id"]["resolved"], "brassica_oleracea")
        self.assertEqual(by_field["rotation_group"]["resolved"], "brassicas")
        self.assertEqual(by_field["propagule"]["resolved"], "seed")
        self.assertEqual(by_field["raunkiaerality"]["magnitude"], "1-3-2-5-1")
        self.assertEqual(by_field["gestation"]["magnitude"], "3542400")
        self.assertEqual(by_field["spacing"]["magnitude"], "18")
        # the new singular_unit_weight nominal decodes to text.
        self.assertEqual(by_field["singular_unit_weight"]["resolved"], "5 g")
        # header/non-4-10 rows are skipped
        self.assertTrue(all(r["datum_address"].startswith("4-10-") for r in rows))


class SandboxDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = _FakeStore([_lcl(), _txa(), _product_profiles()])

    def test_product_viewer_is_archetype_specific(self) -> None:
        resp = build_sandbox_visualizers_response(tenant_id="fnd", sandbox_id="agro_erp", datum_store=self.store)
        self.assertEqual(resp["sandboxes"], ["agro_erp"])
        viz = {v["tool_id"]: v for v in resp["visualizers"]}
        self.assertIn("product_document", viz)
        # product_document matches ONLY the product_profiles doc, not lcl/txa
        self.assertEqual(viz["product_document"]["eligible_count"], 1)

    def test_eligible_tools_for_product_doc_includes_viewer(self) -> None:
        pp = _product_profiles()
        resp = build_eligible_tools_response(
            tenant_id="fnd", document_id=pp.document_id, datum_address="", datum_store=self.store
        )
        self.assertIn("product_document", [t["tool_id"] for t in resp["tools"]])


class ProductViewerContractTests(unittest.TestCase):
    def test_tool_attributes(self) -> None:
        viewer = ProductDocumentViewer()
        self.assertEqual(viewer.tool_id, "product_document")
        self.assertEqual(viewer.applies_to_archetype, ("agro_erp_product_profile_row",))
        self.assertEqual(viewer.applies_to_source_kind, ())


if __name__ == "__main__":
    unittest.main()
