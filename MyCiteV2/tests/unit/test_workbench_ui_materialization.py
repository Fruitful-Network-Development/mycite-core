"""Phase 3 — workbench-UI read path materializes through the WORKBOOK-YAML codec
and derives row/version semantics from the core engine (not parallel SQL reads).

Two guarantees:

1. **Equivalence** — for a consistent catalog, the core engine
   (``build_document_semantics`` / ``build_document_version_identity``) produces
   exactly the row + document identity the store persists and previously served
   via ``read_datum_semantic_identity`` / ``read_document_version_identity``.
   This is what makes the cut-over behavior-preserving.

2. **Golden** — ``read_surface`` output for a seeded catalog is byte-for-byte
   stable across the refactor (captured fixture under ``fixtures/``).
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.core.datum_semantics import (
    build_document_semantics,
    build_document_version_identity,
)
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentCatalogResult,
    AuthoritativeDatumDocumentRequest,
    AuthoritativeDatumDocumentRow,
)
from MyCiteV2.packages.tools.workbench_ui.service import WorkbenchUiReadService

_GOLDEN = Path(__file__).resolve().parent / "fixtures" / "workbench_ui_surface_golden.json"
_NID = "rf.3-1-1"
_TITLE = "rf.3-1-2"
_BLOB = "0" * 16


def _bits(label: str) -> str:
    from MyCiteV2.packages.core.datum_ops import labels
    return labels.encode_label_bits(label)


def _doc(name: str, rows: list[tuple[str, object]]) -> AuthoritativeDatumDocument:
    return AuthoritativeDatumDocument(
        document_id=f"lv.3-2-3-17-77-1-6-4-1-4.agro_erp.{name}." + ("a" * 64),
        source_kind="sandbox_source",
        document_name=name,
        relative_path=f"agro_erp/{name}.json",
        rows=tuple(AuthoritativeDatumDocumentRow(datum_address=a, raw=r) for a, r in rows),
    )


def _seed_documents() -> tuple[AuthoritativeDatumDocument, ...]:
    from MyCiteV2.packages.core.datum_ops import samras_deps
    bits = samras_deps.build_magnitude_bitstream({"1", "1-1", "2", "2-1"})
    txa = _doc("txa", [
        ("4-2-1", [["4-2-1", _NID, "1", _TITLE, _bits("brassica")], ["brassica"]]),
        ("4-2-2", [["4-2-2", _NID, "1-1", _TITLE, _bits("brassica_oleracea")], ["brassica_oleracea"]]),
        ("4-2-3", [["4-2-3", _NID, "2", _TITLE, _bits("catch_all")], ["catch_all"]]),
        ("4-2-4", [["4-2-4", _NID, "2-1", _TITLE, _bits("brassica_carinata")], ["brassica_carinata"]]),
        ("5-0-1", [["5-0-1", "~", "4-2-1", "4-2-2", "4-2-3", "4-2-4"], ["txa_id_collection"]]),
    ])
    anchor = _doc("anchor", [("1-1-1", [["1-1-1", "0-0-5", bits], ["txa-SAMRAS"]])])
    product = _doc("product_profiles", [
        ("4-9-1", [["4-9-1", _NID, "2-1", "2-1-1", "100"], ["prod_a"]]),
    ])
    return (anchor, txa, product)


_QUERIES = {
    "default": {},
    "txa_selected_grouped": {
        "document": f"lv.3-2-3-17-77-1-6-4-1-4.agro_erp.txa.{'a' * 64}",
        "row": "4-2-4",
        "group": "layer_value_group",
        "sort": "datum_address",
    },
}


class WorkbenchUiMaterializationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.db = Path(self._tmp.name) / "mos.sqlite3"
        self._store().store_authoritative_catalog(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=_seed_documents(),
                source_files={"sandbox_source": "agro_erp/"},
                readiness_status={"authoritative_catalog": "loaded"},
            )
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _store(self):
        from MyCiteV2.packages.adapters.sql.datum_store import SqliteSystemDatumStoreAdapter
        return SqliteSystemDatumStoreAdapter(self.db, allow_legacy_writes=False)

    def test_engine_semantics_match_persisted_store_values(self) -> None:
        # Compare against the documents AS RETURNED BY THE STORE READ (what the
        # render path actually operates on) — not the seed originals — so this
        # proves the read-path derivation equals what the store persisted.
        store = self._store()
        catalog = store.read_authoritative_datum_documents(
            AuthoritativeDatumDocumentRequest(tenant_id="fnd")
        )
        for document in catalog.documents:
            engine_doc = build_document_version_identity(document)
            persisted_doc = store.read_document_version_identity(
                tenant_id="fnd", document_id=document.document_id
            )
            self.assertEqual(
                engine_doc["version_hash"], (persisted_doc or {}).get("version_hash"),
                f"version hash drift for {document.document_name}",
            )
            engine_rows = build_document_semantics(document)["rows"]
            for row in document.rows:
                engine_row = engine_rows[row.datum_address]
                persisted = store.read_datum_semantic_identity(
                    tenant_id="fnd", document_id=document.document_id, datum_address=row.datum_address,
                )
                self.assertIsNotNone(persisted, f"{document.document_name}:{row.datum_address}")
                for key in ("policy", "semantic_hash", "hyphae_hash", "local_references", "warnings"):
                    self.assertEqual(
                        engine_row[key], persisted[key],
                        f"{key} drift at {document.document_name}:{row.datum_address}",
                    )
                self.assertEqual(engine_row["hyphae_chain"]["addresses"], persisted["hyphae_chain"]["addresses"])

    def test_anchor_context_survives_store_round_trip(self) -> None:
        # A document carrying anchor context (anchor_rows + anchor_document_metadata)
        # must, after store→read, still recompute via the engine to the persisted
        # hashes. This guards the reason the render path derives from the catalog
        # document directly (the single-doc codec drops anchor context).
        from MyCiteV2.packages.core.datum_ops import samras_deps
        bits = samras_deps.build_magnitude_bitstream({"1", "2", "2-1"})
        anchored = AuthoritativeDatumDocument(
            document_id=f"lv.3-2-3-17-77-1-6-4-1-4.agro_erp.txa2.{'b' * 64}",
            source_kind="sandbox_source", document_name="txa2", relative_path="agro_erp/txa2.json",
            rows=(
                AuthoritativeDatumDocumentRow(datum_address="4-2-1", raw=[["4-2-1", _NID, "1", _TITLE, _bits("g")], ["g"]]),
                AuthoritativeDatumDocumentRow(datum_address="4-2-2", raw=[["4-2-2", _NID, "2-1", _TITLE, _bits("s")], ["s"]]),
            ),
            anchor_document_metadata={"context": "txa-anchor"},
            anchor_rows=(AuthoritativeDatumDocumentRow(datum_address="1-1-1", raw=[["1-1-1", "0-0-5", bits], ["txa-SAMRAS"]]),),
        )
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "anchor.sqlite3"
            from MyCiteV2.packages.adapters.sql.datum_store import SqliteSystemDatumStoreAdapter
            store = SqliteSystemDatumStoreAdapter(db, allow_legacy_writes=False)
            store.store_authoritative_catalog(
                AuthoritativeDatumDocumentCatalogResult(
                    tenant_id="fnd", documents=(anchored,),
                    source_files={"sandbox_source": "agro_erp/"}, readiness_status={"x": "y"},
                )
            )
            catalog = store.read_authoritative_datum_documents(
                AuthoritativeDatumDocumentRequest(tenant_id="fnd")
            )
            catalog_doc = next(d for d in catalog.documents if d.document_name == "txa2")
            self.assertTrue(catalog_doc.anchor_rows, "store must round-trip anchor_rows")
            engine_rows = build_document_semantics(catalog_doc)["rows"]
            for addr in ("4-2-1", "4-2-2"):
                persisted = store.read_datum_semantic_identity(
                    tenant_id="fnd", document_id=anchored.document_id, datum_address=addr
                )
                self.assertEqual(engine_rows[addr]["hyphae_hash"], persisted["hyphae_hash"], addr)
                self.assertEqual(engine_rows[addr]["semantic_hash"], persisted["semantic_hash"], addr)

    def _surface(self, query: dict) -> dict:
        return WorkbenchUiReadService(self.db).read_surface(
            portal_instance_id="fnd", portal_domain="example.test", surface_query=query,
        )

    def test_read_surface_matches_golden(self) -> None:
        captured = {name: self._surface(q) for name, q in _QUERIES.items()}
        if not _GOLDEN.exists():
            _GOLDEN.parent.mkdir(parents=True, exist_ok=True)
            _GOLDEN.write_text(json.dumps(captured, indent=2, sort_keys=True, default=str), encoding="utf-8")
            self.skipTest(f"golden written to {_GOLDEN} — re-run to assert against it")
        expected = json.loads(_GOLDEN.read_text(encoding="utf-8"))
        # Compare via normalized JSON so key order / tuple-vs-list don't matter.
        self.assertEqual(
            json.loads(json.dumps(captured, sort_keys=True, default=str)),
            expected,
            "read_surface output drifted from the golden snapshot",
        )


if __name__ == "__main__":
    unittest.main()
