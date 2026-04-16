from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.ports.datum_store.cts_gis_legacy_compat import (
    CTS_GIS_CANONICAL_TOOL_PUBLIC_ID,
    CTS_GIS_CANONICAL_TOOL_SLUG,
    CTS_GIS_LEGACY_TOOL_PUBLIC_ID,
    CTS_GIS_LEGACY_TOOL_SLUG,
    canonicalize_cts_gis_sandbox_document_id,
    canonicalize_cts_gis_tool_public_id,
    cts_gis_anchor_patterns_phase_a,
    cts_gis_sandbox_document_id_aliases,
    cts_gis_tool_slug_candidates_phase_a,
    is_cts_gis_legacy_anchor_filename,
    is_cts_gis_legacy_sandbox_document_id,
    is_cts_gis_legacy_tool_public_id,
    matches_cts_gis_sandbox_document_id,
)


class CtsGisLegacyCompatTests(unittest.TestCase):
    def test_tool_id_aliases_normalize_to_canonical(self) -> None:
        self.assertEqual(canonicalize_cts_gis_tool_public_id(CTS_GIS_CANONICAL_TOOL_PUBLIC_ID), CTS_GIS_CANONICAL_TOOL_PUBLIC_ID)
        self.assertEqual(canonicalize_cts_gis_tool_public_id(CTS_GIS_CANONICAL_TOOL_SLUG), CTS_GIS_CANONICAL_TOOL_PUBLIC_ID)
        self.assertEqual(canonicalize_cts_gis_tool_public_id(CTS_GIS_LEGACY_TOOL_PUBLIC_ID), CTS_GIS_CANONICAL_TOOL_PUBLIC_ID)
        self.assertTrue(is_cts_gis_legacy_tool_public_id(CTS_GIS_LEGACY_TOOL_PUBLIC_ID))
        self.assertEqual(
            cts_gis_tool_slug_candidates_phase_a(),
            (CTS_GIS_CANONICAL_TOOL_SLUG, CTS_GIS_LEGACY_TOOL_SLUG),
        )

    def test_document_id_aliases_and_matches_support_phase_a_bridge(self) -> None:
        legacy_doc_id = f"sandbox:{CTS_GIS_LEGACY_TOOL_PUBLIC_ID}:sc.example.json"
        canonical_doc_id = f"sandbox:{CTS_GIS_CANONICAL_TOOL_PUBLIC_ID}:sc.example.json"
        self.assertEqual(canonicalize_cts_gis_sandbox_document_id(legacy_doc_id), canonical_doc_id)
        self.assertEqual(
            cts_gis_sandbox_document_id_aliases(canonical_doc_id),
            (canonical_doc_id, legacy_doc_id),
        )
        self.assertTrue(matches_cts_gis_sandbox_document_id(canonical_doc_id, legacy_doc_id))
        self.assertTrue(matches_cts_gis_sandbox_document_id(legacy_doc_id, canonical_doc_id))
        self.assertTrue(is_cts_gis_legacy_sandbox_document_id(legacy_doc_id))

    def test_anchor_pattern_order_keeps_canonical_before_legacy(self) -> None:
        patterns = cts_gis_anchor_patterns_phase_a()
        canonical_pattern = f"tool.*.{CTS_GIS_CANONICAL_TOOL_SLUG}.json"
        legacy_pattern = f"tool.*.{CTS_GIS_LEGACY_TOOL_SLUG}.json"
        self.assertIn(canonical_pattern, patterns)
        self.assertIn(legacy_pattern, patterns)
        self.assertLess(patterns.index(canonical_pattern), patterns.index(legacy_pattern))
        self.assertTrue(is_cts_gis_legacy_anchor_filename(f"tool.{CTS_GIS_LEGACY_TOOL_SLUG}.json"))


if __name__ == "__main__":
    unittest.main()
