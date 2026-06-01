"""S5 — store-bound executor (execute_migration) on a seeded, hermetic MOS DB.

Seeds a synthetic agro_erp sandbox into a temp SQLite authority (via
``store_authoritative_catalog``), plans a one-species relocation through
datum_ops, applies it via ``execute_migration``, and asserts: the species
re-nests under the target genus, the store round-trips, ``check_step`` passes,
a backup is written, and an idempotent re-plan is a no-op.

This used to copy the live prod MOS DB and assert a pre-migration data state;
the migration has since been applied live, so the test now seeds its own fixture
and is fully hermetic (runs in clean CI, no /srv/webapps dependency).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.core.datum_ops import labels, samras_deps
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentCatalogResult,
    AuthoritativeDatumDocumentRow,
)

_NID = labels.RF_NODE_ID
_TITLE = labels.RF_TITLE


def _doc(name: str, rows: list[tuple[str, object]]) -> AuthoritativeDatumDocument:
    return AuthoritativeDatumDocument(
        document_id=f"lv.3-2-3-17-77-1-6-4-1-4.agro_erp.{name}." + ("a" * 64),
        source_kind="sandbox_source",
        document_name=name,
        relative_path=f"agro_erp/{name}.json",
        rows=tuple(AuthoritativeDatumDocumentRow(datum_address=a, raw=r) for a, r in rows),
    )


def _def(addr: str, node: str, title: str) -> tuple[str, object]:
    return (addr, [[addr, _NID, node, _TITLE, labels.encode_label_bits(title)], [title]])


def _product(addr: str, taxon: str) -> tuple[str, object]:
    return (addr, [[addr, _NID, taxon, "2-1-1", "100"], ["prod"]])


def _seed_documents() -> tuple[AuthoritativeDatumDocument, ...]:
    """A valid single-root agro_erp tree: a 'brassica' genus (node 1) and a
    'brassica_carinata' species wrongly parked under the catch-all (node 2)."""
    node_set = {"1", "1-1", "2", "2-1"}
    bits = samras_deps.build_magnitude_bitstream(node_set)
    txa = _doc("txa", [
        _def("4-2-1", "1", "brassica"),
        _def("4-2-2", "1-1", "brassica_oleracea"),
        _def("4-2-3", "2", "catch_all"),
        _def("4-2-4", "2-1", "brassica_carinata"),
        ("5-0-1", [["5-0-1", "~", "4-2-1", "4-2-2", "4-2-3", "4-2-4"], ["txa_id_collection"]]),
    ])
    anchor = _doc("anchor", [("1-1-1", [["1-1-1", "0-0-5", bits], ["txa-SAMRAS"]])])
    product = _doc("product_profiles", [_product("4-9-1", "2-1")])
    return (anchor, txa, product)


class ExecuteMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.db = Path(self._tmp.name) / "mos_s5_apply.sqlite3"
        store = self._store()
        store.store_authoritative_catalog(
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

    def _node_by_title(self, wb, title: str) -> str:
        for r in wb.sheet("txa").rows:
            raw = r.raw
            if isinstance(raw, list) and len(raw) > 1 and raw[1] and str(raw[1][0]) == title:
                return str(raw[0][2])
        raise AssertionError(f"title not found in txa: {title}")

    def test_relocate_one_species_end_to_end(self) -> None:
        from MyCiteV2.packages.adapters.sql.datum_workbook_apply import (
            execute_migration,
            load_workbook,
        )
        from MyCiteV2.packages.core.datum_ops import (
            RebuildCollection,
            RecompileMagnitude,
            RelocateNode,
            check_step,
            plan_migration,
        )
        from MyCiteV2.packages.core.datum_ops import (
            node_addrs as na,
        )

        store = self._store()
        wb = load_workbook(store, tenant_id="fnd", sandbox="agro_erp")
        # brassica_carinata is wrongly under the catch-all; the brassica genus exists.
        species_node = self._node_by_title(wb, "brassica_carinata")
        genus_node = self._node_by_title(wb, "brassica")
        self.assertEqual(na.parent_of(species_node), self._node_by_title(wb, "catch_all"))

        ops = [
            RelocateNode("txa", species_node, genus_node),
            RecompileMagnitude("anchor", "1-1-1", "txa"),
            RebuildCollection("txa", "5-0-1", "txa_id_collection"),
        ]
        plan = plan_migration(wb, ops)
        self.assertIn("txa", plan.touched)
        self.assertIn("anchor", plan.touched)
        # the product ref following the relocated node is rewritten too
        self.assertIn("product_profiles", plan.touched)

        result = execute_migration(self.db, plan, tenant_id="fnd")
        self.assertEqual(result["status"], "applied")
        self.assertIsNotNone(result["backup"])

        # re-read from the store: brassica_carinata now nests under brassica; consistent.
        wb2 = load_workbook(self._store(), tenant_id="fnd", sandbox="agro_erp")
        new_node = self._node_by_title(wb2, "brassica_carinata")
        self.assertTrue(new_node.startswith(genus_node + "-"), f"{new_node} not under {genus_node}")
        self.assertTrue(check_step(wb2).ok, check_step(wb2).hard[:5])

        # idempotent: re-plan with recompile/rebuild only → no change
        replan = plan_migration(wb2, [
            RecompileMagnitude("anchor", "1-1-1", "txa"),
            RebuildCollection("txa", "5-0-1", "txa_id_collection"),
        ])
        self.assertEqual(replan.touched, {})


if __name__ == "__main__":
    unittest.main()
