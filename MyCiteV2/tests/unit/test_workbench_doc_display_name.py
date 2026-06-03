from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.ports.datum_store.contracts import AuthoritativeDatumDocument
from MyCiteV2.packages.tools.workbench_ui.service import (
    _document_display_name,
    _short_document_name,
)

MSN = "3-2-3-17-77-1-6-4-1-4"
HASH = "a" * 64


def _doc(*, document_id: str, document_name: str, canonical_name: str = "") -> AuthoritativeDatumDocument:
    return AuthoritativeDatumDocument(
        document_id=document_id,
        source_kind="sandbox_source",
        document_name=document_name,
        relative_path="sandbox/agro-erp/x.json",
        canonical_name=canonical_name,
    )


class TestShortDocumentName(unittest.TestCase):
    def test_plain_short_name_unchanged(self) -> None:
        self.assertEqual(_short_document_name("anchor"), "anchor")
        self.assertEqual(_short_document_name("product_profiles"), "product_profiles")

    def test_strips_json_extension(self) -> None:
        self.assertEqual(_short_document_name("aws_csm_profile_cvcc_admin.json"), "aws_csm_profile_cvcc_admin")

    def test_strips_full_filesystem_path(self) -> None:
        self.assertEqual(
            _short_document_name("/srv/webapps/mycite/fnd/private/contacts.json"),
            "contacts",
        )

    def test_dotted_tool_name_keeps_meaningful_tail(self) -> None:
        # tool.<msn>.cts-gis.json -> strips only the trailing .json extension
        self.assertEqual(
            _short_document_name(f"tool.{MSN}.cts-gis.json"),
            f"tool.{MSN}.cts-gis",
        )

    def test_strips_known_doc_extensions(self) -> None:
        for name, want in [
            ("rates.yaml", "rates"),
            ("notes.yml", "notes"),
            ("readme.md", "readme"),
            ("ledger.csv", "ledger"),
            ("memo.txt", "memo"),
        ]:
            self.assertEqual(_short_document_name(name), want)

    def test_keeps_non_extension_dotted_suffix(self) -> None:
        # A short dotted tail that is NOT a file extension (version/season code) must
        # be preserved — only recognized extensions are stripped.
        self.assertEqual(_short_document_name("report.v2"), "report.v2")
        self.assertEqual(_short_document_name("inventory.feb"), "inventory.feb")
        self.assertEqual(_short_document_name("plot.7b"), "plot.7b")

    def test_empty(self) -> None:
        self.assertEqual(_short_document_name(""), "")
        self.assertEqual(_short_document_name(None), "")


class TestDocumentDisplayName(unittest.TestCase):
    def test_prefers_canonical_name(self) -> None:
        doc = _doc(
            document_id=f"lv.{MSN}.agro_erp.contracts.{HASH}",
            document_name=f"lv.{MSN}.agro_erp.contracts",
            canonical_name="contracts",
        )
        self.assertEqual(_document_display_name(doc), "contracts")

    def test_canonical_wins_over_full_path_document_name(self) -> None:
        doc = _doc(
            document_id=f"lv.{MSN}.cts_gis.anchor.{HASH}",
            document_name=f"tool.{MSN}.cts-gis.json",
            canonical_name="anchor",
        )
        self.assertEqual(_document_display_name(doc), "anchor")

    def test_fallback_to_cleaned_document_name_when_canonical_absent(self) -> None:
        doc = _doc(
            document_id=f"lv.{MSN}.system.profile.{HASH}",
            document_name="aws_csm_profile_cvcc_admin.json",
            canonical_name="",
        )
        self.assertEqual(_document_display_name(doc), "aws_csm_profile_cvcc_admin")

    def test_stable_for_both_wellformed_and_path_inputs(self) -> None:
        # Same canonical name -> same display regardless of document_name shape.
        clean = _doc(
            document_id=f"lv.{MSN}.agro_erp.anchor.{HASH}",
            document_name="anchor",
            canonical_name="anchor",
        )
        dotted = _doc(
            document_id=f"lv.{MSN}.agro_erp.anchor.{HASH}",
            document_name=f"lv.{MSN}.agro_erp.anchor",
            canonical_name="anchor",
        )
        self.assertEqual(_document_display_name(clean), _document_display_name(dotted))
        self.assertEqual(_document_display_name(clean), "anchor")


if __name__ == "__main__":
    unittest.main()
