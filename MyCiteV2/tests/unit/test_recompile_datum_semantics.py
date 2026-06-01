"""MSS cutover dry-run tool — helper + seeded end-to-end smoke."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentCatalogResult,
    AuthoritativeDatumDocumentRow,
)
from MyCiteV2.scripts import recompile_datum_semantics as tool


class NewDocumentIdTests(unittest.TestCase):
    def test_replaces_trailing_hash_segment(self) -> None:
        old = "lv.3-2-3-17-77-1-6-4-1-4.agro_erp.txa." + ("a" * 64)
        new = tool._new_document_id(old, "b" * 64)
        self.assertEqual(new, "lv.3-2-3-17-77-1-6-4-1-4.agro_erp.txa." + ("b" * 64))

    def test_non_canonical_id_returns_none(self) -> None:
        self.assertIsNone(tool._new_document_id("system:anthology", "b" * 64))


class DryRunSmokeTests(unittest.TestCase):
    def _seed(self, db: Path) -> None:
        from MyCiteV2.packages.adapters.sql.datum_store import SqliteSystemDatumStoreAdapter
        doc = AuthoritativeDatumDocument(
            document_id="lv.3-2-3-17-77-1-6-4-1-4.agro_erp.txa." + ("a" * 64),
            source_kind="sandbox_source", document_name="txa", relative_path="agro_erp/txa.json",
            rows=(
                AuthoritativeDatumDocumentRow(datum_address="0-0-1", raw=[["0-0-1", "~"], ["top"]]),
                AuthoritativeDatumDocumentRow(datum_address="1-1-1", raw=[["1-1-1", "0-0-1", "128"], ["x"]]),
            ),
        )
        SqliteSystemDatumStoreAdapter(db, allow_legacy_writes=False).store_authoritative_catalog(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd", documents=(doc,),
                source_files={"sandbox_source": "agro_erp/"}, readiness_status={"x": "y"},
            )
        )

    def test_dry_run_maps_canonical_docs_and_refuses_apply(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "mos.sqlite3"
            out = Path(tmp) / "map.json"
            self._seed(db)
            argv = sys.argv
            try:
                sys.argv = ["recompile", "--db", str(db), "--tenant", "fnd", "--out", str(out)]
                self.assertEqual(tool.main(), 0)
            finally:
                sys.argv = argv
            mapping = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(len(mapping), 1)
            entry = mapping[0]
            self.assertTrue(entry["new_version_hash"].startswith("sha256:"))
            self.assertNotEqual(entry["new_document_id"], entry["document_id"])  # hash changed

    def test_apply_is_refused(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "mos.sqlite3"
            self._seed(db)
            argv = sys.argv
            try:
                sys.argv = ["recompile", "--db", str(db), "--apply"]
                self.assertEqual(tool.main(), 2)  # refuses
            finally:
                sys.argv = argv


if __name__ == "__main__":
    unittest.main()
