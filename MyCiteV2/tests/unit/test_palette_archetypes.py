from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_palette_runtime import (
    derive_document_archetypes,
)
from MyCiteV2.packages.ports.datum_store.contracts import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRow,
)

MSN = "3-2-3-17-77-1-6-4-1-4"
HASH = "a" * 64


def _doc(name: str, *, metadata: dict, rows: list) -> AuthoritativeDatumDocument:
    return AuthoritativeDatumDocument(
        document_id=f"lv.{MSN}.agro_erp.{name}.{HASH}",
        source_kind="sandbox_source",
        document_name=name,
        relative_path=f"sandbox/agro-erp/{name}.json",
        canonical_name=name,
        document_metadata=metadata,
        rows=tuple(AuthoritativeDatumDocumentRow.from_dict(r) for r in rows),
    )


class TestDeriveDocumentArchetypes(unittest.TestCase):
    def test_explicit_template_archetype(self) -> None:
        doc = _doc("product_profiles", metadata={"datum_template_archetype": "agro_erp_product_profile_row"}, rows=[])
        self.assertIn("agro_erp_product_profile_row", derive_document_archetypes(doc))

    def test_schema_token(self) -> None:
        doc = _doc("contracts", metadata={"schema": "mycite.v2.datum.agro_erp.contracts.v1"}, rows=[])
        self.assertIn("mycite.v2.datum.agro_erp.contracts.v1", derive_document_archetypes(doc))

    def test_hops_filament_shape_recognized(self) -> None:
        # A family-4 ring row carrying the rf.3-1-3 HOPS coordinate marker.
        rows = [
            {"datum_address": "4-4-1", "raw": [["4-4-1", "rf.3-1-3", "3-76-1-2-3", "rf.3-1-3", "3-76-4-5-6"], ["plot_ring"]]},
        ]
        doc = _doc("farm_profile", metadata={"note": "HOPS filament", "title": "trapp_family_farm"}, rows=rows)
        archetypes = derive_document_archetypes(doc)
        self.assertIn("hops_geospatial_filament", archetypes)

    def test_non_geospatial_doc_not_tagged_hops(self) -> None:
        rows = [
            {"datum_address": "4-5-1", "raw": [["4-5-1", "rf.3-1-5", "1-1-4-1", "rf.3-1-2", "0101"], ["berlin_seeds"]]},
        ]
        doc = _doc("contacts", metadata={"schema": "mycite.v2.datum.agro_erp.contacts.v1"}, rows=rows)
        self.assertNotIn("hops_geospatial_filament", derive_document_archetypes(doc))

    def test_recognition_is_not_by_document_id(self) -> None:
        # Two docs with different ids but the same shape resolve identically.
        rows = [{"datum_address": "4-4-1", "raw": [["4-4-1", "rf.3-1-3", "3-76-1"], ["r"]]}]
        a = _doc("farm_profile", metadata={}, rows=rows)
        b = _doc("some_other_geo_doc", metadata={}, rows=rows)
        self.assertEqual(derive_document_archetypes(a), derive_document_archetypes(b))
        self.assertIn("hops_geospatial_filament", derive_document_archetypes(a))


if __name__ == "__main__":
    unittest.main()
