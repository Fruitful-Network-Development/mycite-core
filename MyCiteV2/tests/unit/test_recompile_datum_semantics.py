"""MSS cutover tool — helper, dry-run mapping, and --apply on a seeded copy."""

from __future__ import annotations

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
    AuthoritativeDatumDocumentRequest,
    AuthoritativeDatumDocumentRow,
)
from MyCiteV2.scripts import recompile_datum_semantics as tool


def _store(db: Path):
    from MyCiteV2.packages.adapters.sql.datum_store import SqliteSystemDatumStoreAdapter
    return SqliteSystemDatumStoreAdapter(db, allow_legacy_writes=False)


def _seed(db: Path) -> str:
    doc = AuthoritativeDatumDocument(
        document_id="lv.3-2-3-17-77-1-6-4-1-4.agro_erp.txa." + ("a" * 64),
        source_kind="sandbox_source", document_name="txa", relative_path="agro_erp/txa.json",
        rows=(
            AuthoritativeDatumDocumentRow(datum_address="0-0-1", raw=[["0-0-1", "~"], ["top"]]),
            AuthoritativeDatumDocumentRow(datum_address="1-1-1", raw=[["1-1-1", "0-0-1", "128"], ["x"]]),
        ),
    )
    _store(db).store_authoritative_catalog(
        AuthoritativeDatumDocumentCatalogResult(
            tenant_id="fnd", documents=(doc,),
            source_files={"sandbox_source": "agro_erp/"}, readiness_status={"x": "y"},
        )
    )
    return doc.document_id


class NewDocumentIdTests(unittest.TestCase):
    def test_replaces_trailing_hash_segment(self) -> None:
        old = "lv.3-2-3-17-77-1-6-4-1-4.agro_erp.txa." + ("a" * 64)
        self.assertEqual(
            tool._new_document_id(old, "b" * 64),
            "lv.3-2-3-17-77-1-6-4-1-4.agro_erp.txa." + ("b" * 64),
        )

    def test_non_canonical_id_returns_none(self) -> None:
        self.assertIsNone(tool._new_document_id("system:anthology", "b" * 64))


class DryRunTests(unittest.TestCase):
    def test_maps_canonical_doc_to_binary_hash(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "mos.sqlite3"
            old_id = _seed(db)
            mapping, _report, skipped = tool.compute_mapping(str(db), "fnd")
            self.assertEqual(len(mapping), 1)
            self.assertEqual(skipped, 0)
            m = mapping[0]
            self.assertEqual(m["document_id"], old_id)
            self.assertTrue(m["new_version_hash"].startswith("sha256:"))
            self.assertNotEqual(m["new_document_id"], old_id)  # hash segment changed


class ApplyTests(unittest.TestCase):
    def test_apply_on_copy_rewrites_identity_and_verifies(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "copy.sqlite3"
            old_id = _seed(db)
            mapping, _, _ = tool.compute_mapping(str(db), "fnd")
            new_id = mapping[0]["new_document_id"]
            new_vh = mapping[0]["new_version_hash"]

            backup = tool.apply_mapping(str(db), "fnd", mapping)
            self.assertTrue(backup.exists())

            # Read path (snapshot) now serves the NEW document_id.
            cat = _store(db).read_authoritative_datum_documents(
                AuthoritativeDatumDocumentRequest(tenant_id="fnd")
            )
            ids = {d.document_id for d in cat.documents}
            self.assertIn(new_id, ids)
            self.assertNotIn(old_id, ids)
            # Version identity table carries the binary hash + policy.
            ident = _store(db).read_document_version_identity(tenant_id="fnd", document_id=new_id)
            self.assertEqual(ident["version_hash"], new_vh)
            self.assertEqual(ident["policy"], "mos.mss_binary_v2")
            # Row semantics were re-keyed to the new document_id (not orphaned).
            row_sem = _store(db).read_datum_semantic_identity(
                tenant_id="fnd", document_id=new_id, datum_address="1-1-1"
            )
            self.assertIsNotNone(row_sem)

    def test_apply_refuses_the_live_db_path(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "mos.sqlite3"
            _seed(db)
            mapping, _, _ = tool.compute_mapping(str(db), "fnd")
            original = tool._LIVE_DB
            try:
                tool._LIVE_DB = db  # pretend this copy IS the live DB
                with self.assertRaises(SystemExit):
                    tool.apply_mapping(str(db), "fnd", mapping)
            finally:
                tool._LIVE_DB = original


if __name__ == "__main__":
    unittest.main()
