"""Regression — robust sheet-key derivation in the WORKBOOK-YAML bridge.

``_sheet_key`` must derive the canonical name segment via the canonical id
parser (matching ``datum_workbook_apply.load_workbook``) and fall back to
``document_name`` for non-canonical ids. The round-trip
``to_yaml`` -> ``from_yaml`` must key sheets identically.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.core.datum_ops import Workbook, workbook_codec
from MyCiteV2.packages.core.datum_ops.workbook import _sheet_key
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRow,
)

MSN = "3-2-3-17-77-1-6-4-1-4"
HASH = "a" * 64


def _doc(document_id: str, *, document_name: str, name: str = "txa") -> AuthoritativeDatumDocument:
    return AuthoritativeDatumDocument(
        document_id=document_id,
        source_kind="sandbox_source",
        document_name=document_name,
        relative_path=f"agro_erp/{name}.json",
        rows=(
            AuthoritativeDatumDocumentRow(
                datum_address="4-2-1",
                raw=[["4-2-1", "8-0-1", "1", "2-1-2", "abc"], ["genus_root"]],
            ),
        ),
    )


class SheetKeyTests(unittest.TestCase):
    def test_canonical_lv_id_keys_on_name_segment(self) -> None:
        doc = _doc(f"lv.{MSN}.agro_erp.txa.{HASH}", document_name="ignored_display_name")
        # name segment is the 4th dot-part — must win over document_name.
        self.assertEqual(_sheet_key(doc), "txa")

    def test_non_canonical_id_falls_back_to_document_name(self) -> None:
        doc = _doc("system:anthology", document_name="anthology")
        self.assertEqual(_sheet_key(doc), "anthology")

    def test_non_canonical_id_falls_back_to_document_id_when_no_name(self) -> None:
        # AuthoritativeDatumDocument forbids an empty document_name, so use a
        # duck-typed stand-in to exercise the document_id tail of the fallback.
        doc = SimpleNamespace(document_id="not-a-canonical-id", document_name="")
        self.assertEqual(_sheet_key(doc), "not-a-canonical-id")


class RoundTripTests(unittest.TestCase):
    def _wb(self) -> Workbook:
        anchor = _doc(
            f"lv.{MSN}.agro_erp.anchor.{HASH}", document_name="anchor", name="anchor"
        )
        txa = _doc(f"lv.{MSN}.agro_erp.txa.{HASH}", document_name="txa", name="txa")
        return Workbook(sandbox="agro_erp", sheets={"anchor": anchor, "txa": txa})

    def test_to_yaml_from_yaml_keys_sheets_identically(self) -> None:
        wb = self._wb()
        back = workbook_codec.from_yaml(workbook_codec.to_yaml(wb))
        self.assertEqual(back.sandbox, "agro_erp")
        self.assertEqual(sorted(back.names()), sorted(wb.names()))
        # canonical name segment, not display name, drives the key.
        self.assertEqual(sorted(back.names()), ["anchor", "txa"])


if __name__ == "__main__":
    unittest.main()
