"""Regression tests for the workbench-tool document resolver (review remediation).

Covers the operator-reported bug: selecting the Farm Profile (or Contracts) tool while
a NON-target document is the active workbench selection rendered an empty panel, because
the tools trusted the selected ``document_id`` and only fell back to the real target when
NO doc matched. ``resolve_tool_document`` resolves by archetype instead, honoring the
selection only when it actually matches the tool.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.ports.datum_store import AuthoritativeDatumDocumentRequest
from MyCiteV2.packages.ports.datum_store.contracts import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRow,
)
from MyCiteV2.packages.tools._archetype import resolve_tool_document
from MyCiteV2.packages.tools.contracts_tool import ContractsTool
from MyCiteV2.packages.tools.farm_profile_viewer import FarmProfileViewer

MSN = "3-2-3-17-77-1-6-4-1-4"
HASH = "a" * 64
_LIVE_DB = Path("/srv/webapps/mycite/fnd/private/mos_authority.sqlite3")


def _doc(name: str, *, sandbox: str = "agro_erp", metadata: dict | None = None, rows=()) -> AuthoritativeDatumDocument:
    return AuthoritativeDatumDocument(
        document_id=f"lv.{MSN}.{sandbox}.{name}.{HASH}",
        source_kind="sandbox_source",
        document_name=name,
        relative_path=f"sandbox/{sandbox}/{name}.json",
        canonical_name=name,
        document_metadata=metadata or {},
        rows=tuple(AuthoritativeDatumDocumentRow.from_dict(r) for r in rows),
    )


class _GeoTool:
    applies_to_archetype = ("hops_geospatial_filament",)
    applies_to_source_kind = ()


class TestResolveToolDocument(unittest.TestCase):
    def setUp(self) -> None:
        self.anchor = _doc("anchor", rows=[{"datum_address": "1-0-1", "raw": [["1-0-1", "x"], ["a"]]}])
        self.farm = _doc(
            "farm_profile",
            rows=[{"datum_address": "4-4-1", "raw": [["4-4-1", "rf.3-1-3", "3-76-1-2-3"], ["ring"]]}],
        )
        self.docs = [self.anchor, self.farm]

    def test_wrong_selection_falls_back_to_target(self) -> None:
        # The workbench auto-selected the anchor; the geo tool must still resolve farm.
        got = resolve_tool_document(
            self.docs, tool=_GeoTool(), sandbox="agro_erp",
            document_id=self.anchor.document_id, canonical_name="farm_profile",
        )
        self.assertIs(got, self.farm)

    def test_correct_selection_is_honored(self) -> None:
        got = resolve_tool_document(
            self.docs, tool=_GeoTool(), sandbox="agro_erp",
            document_id=self.farm.document_id, canonical_name="farm_profile",
        )
        self.assertIs(got, self.farm)

    def test_no_selection_finds_target(self) -> None:
        got = resolve_tool_document(
            self.docs, tool=_GeoTool(), sandbox="agro_erp",
            document_id="", canonical_name="farm_profile",
        )
        self.assertIs(got, self.farm)

    def test_other_sandbox_is_excluded(self) -> None:
        farm_elsewhere = _doc(
            "farm_profile", sandbox="other_sb",
            rows=[{"datum_address": "4-4-1", "raw": [["4-4-1", "rf.3-1-3", "3-76-1"], ["ring"]]}],
        )
        got = resolve_tool_document(
            [self.anchor, farm_elsewhere], tool=_GeoTool(), sandbox="agro_erp",
            document_id="", canonical_name="farm_profile",
        )
        self.assertIsNone(got)

    def test_foreign_sandbox_selection_does_not_win(self) -> None:
        # Review finding #9: a SELECTED doc from a DIFFERENT sandbox that shares the
        # canonical_name must not be honored across the sandbox boundary; resolution must
        # fall back to the in-sandbox target. (Reachable once the workbench can
        # auto-select a foreign-sandbox doc.)
        foreign = _doc(
            "farm_profile", sandbox="other_sb",
            rows=[{"datum_address": "4-4-1", "raw": [["4-4-1", "rf.3-1-3", "3-76-1"], ["ring"]]}],
        )
        got = resolve_tool_document(
            [foreign, self.anchor, self.farm], tool=_GeoTool(), sandbox="agro_erp",
            document_id=foreign.document_id, canonical_name="farm_profile",
        )
        self.assertIs(got, self.farm)


@unittest.skipUnless(_LIVE_DB.exists(), "live MOS not present")
class TestLiveResolutionRegression(unittest.TestCase):
    """The operator's exact symptom: the anchor is the default selection."""

    def _anchor_id(self) -> str:
        docs = SqliteSystemDatumStoreAdapter(_LIVE_DB).read_authoritative_datum_documents(
            AuthoritativeDatumDocumentRequest(tenant_id="fnd")
        ).documents
        return next(d.document_id for d in docs if d.canonical_name == "anchor" and "agro_erp" in d.document_id)

    def test_farm_profile_renders_with_anchor_selected(self) -> None:
        payload = FarmProfileViewer().build_panel_payload(
            authority_db_file=_LIVE_DB, sandbox_id="agro_erp",
            document_id=self._anchor_id(), datum_address="",
        )
        self.assertIsNone(payload.get("error"))
        self.assertGreater(payload["feature_count"], 0)
        self.assertEqual(payload["plots_source"], "migrated")
        self.assertTrue(payload["document_id"].split(".")[3] == "farm_profile")

    def test_contracts_renders_with_anchor_selected(self) -> None:
        payload = ContractsTool().build_panel_payload(
            authority_db_file=_LIVE_DB, sandbox_id="agro_erp",
            document_id=self._anchor_id(), datum_address="",
        )
        self.assertIsNone(payload.get("error"))
        self.assertEqual(payload["document_id"].split(".")[3], "contracts")
        self.assertGreater(len(payload["draw_down"]), 0)


if __name__ == "__main__":
    unittest.main()
