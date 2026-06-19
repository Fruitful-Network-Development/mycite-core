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
        # A family-4 RING row carrying ≥3 rf.3-1-3 coordinate markers (a real polygon).
        rows = [
            {"datum_address": "4-4-1", "raw": [["4-4-1", "rf.3-1-3", "3-76-1", "rf.3-1-3", "3-76-2", "rf.3-1-3", "3-76-3"], ["plot_ring"]]},
        ]
        doc = _doc("farm_profile", metadata={"note": "HOPS filament", "title": "trapp_family_farm"}, rows=rows)
        self.assertIn("hops_geospatial_filament", derive_document_archetypes(doc))

    def test_single_rf313_in_family4_is_NOT_hops(self) -> None:
        # rf.3-1-3 is OVERLOADED — a single occurrence in a family-4 row is a node-reference
        # (entity docs) or an encoded value, NOT a polygon ring. Must not tag geospatial.
        rows = [
            {"datum_address": "4-1-1", "raw": [["4-1-1", "rf.3-1-3", "3-2-3-17-18-1-1", "rf.3-1-4", "elizabeth"], ["natural_entity_row"]]},
        ]
        doc = _doc("natural_entity", metadata={}, rows=rows)
        self.assertNotIn("hops_geospatial_filament", derive_document_archetypes(doc))

    def test_taxonomy_shape_recognized_structurally(self) -> None:
        # A 4-2-* titled id-pair definition row → samras_taxonomy (no metadata needed).
        rows = [
            {"datum_address": "4-2-1", "raw": [["4-2-1", "rf.3-1-1", "1", "rf.3-1-2", "0" * 16], ["root"]]},
        ]
        doc = _doc("txa", metadata={"legacy_alias": "x"}, rows=rows)
        self.assertIn("samras_taxonomy", derive_document_archetypes(doc))

    def test_bare_4_2_reference_is_NOT_taxonomy(self) -> None:
        # A 4-2 row reusing rf.3-1-1 but with NO title blob (head[4] not binary) is a bare
        # reference, not a definition — must not tag taxonomy.
        rows = [
            {"datum_address": "4-2-9", "raw": [["4-2-9", "rf.3-1-1", "3-2-3-17", "rf.3-1-5", "ref-not-a-title"], ["bare_ref"]]},
        ]
        doc = _doc("cts_structural", metadata={}, rows=rows)
        self.assertNotIn("samras_taxonomy", derive_document_archetypes(doc))

    def test_non_geospatial_doc_not_tagged_hops(self) -> None:
        rows = [
            {"datum_address": "4-5-1", "raw": [["4-5-1", "rf.3-1-5", "1-1-4-1", "rf.3-1-2", "0101"], ["berlin_seeds"]]},
        ]
        doc = _doc("contacts", metadata={"schema": "mycite.v2.datum.agro_erp.contacts.v1"}, rows=rows)
        self.assertNotIn("hops_geospatial_filament", derive_document_archetypes(doc))

    def test_stray_rf313_outside_family4_not_tagged(self) -> None:
        # rf.3-1-3 appearing outside a family-4 ring row (e.g. an anchor file-pointer
        # row) must NOT tag the doc geospatial — only the real 4->5->6->7 ring form does.
        rows = [
            {"datum_address": "1-0-3", "raw": [["1-0-3", "rf.3-1-3", "coord-pointer"], ["anchor_ptr"]]},
        ]
        doc = _doc("anchor", metadata={}, rows=rows)
        self.assertNotIn("hops_geospatial_filament", derive_document_archetypes(doc))

    def test_recognition_is_not_by_document_id(self) -> None:
        # Two docs with different ids but the same shape resolve identically.
        rows = [{"datum_address": "4-4-1", "raw": [["4-4-1", "rf.3-1-3", "3-76-1", "rf.3-1-3", "3-76-2", "rf.3-1-3", "3-76-3"], ["r"]]}]
        a = _doc("farm_profile", metadata={}, rows=rows)
        b = _doc("some_other_geo_doc", metadata={}, rows=rows)
        self.assertEqual(derive_document_archetypes(a), derive_document_archetypes(b))
        self.assertIn("hops_geospatial_filament", derive_document_archetypes(a))


class TestPaletteRegistryMembership(unittest.TestCase):
    def test_surface_and_unreachable_tools_not_in_palette(self) -> None:
        from MyCiteV2.packages.tools import all_tools

        ids = {t.tool_id for t in all_tools()}
        # `workbench_ui` is the surface, not a tool; the 3 cts_gis fixed-artifact viewers
        # are retired (no reliable per-doc eligibility). None should be selectable.
        for retired in ("workbench_ui", "cts_gis", "cts_gis_district", "cts_gis_admin"):
            self.assertNotIn(retired, ids)
        # The real per-doc tools remain.
        for live in ("contracts", "farm_profile", "product_document", "samras_structure"):
            self.assertIn(live, ids)


if __name__ == "__main__":
    unittest.main()
