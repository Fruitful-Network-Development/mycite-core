"""S5 — store-bound executor (execute_migration) on an isolated DB copy.

Copies the live MOS DB into /srv/agentic/tmp (never /tmp — tmpfs OOM), plans a
real one-species relocation through datum_ops, applies it via execute_migration,
and asserts: ids re-minted, documents index updated, SAMRAS roundtrips, no
dangling refs, and an idempotent re-plan is a no-op. Skips if the live DB is
absent.
"""

from __future__ import annotations

import os
import shutil
import unittest
from pathlib import Path

_LIVE_DB = "/srv/webapps/mycite/fnd/private/mos_authority.sqlite3"
_TMP = Path("/srv/agentic/tmp")


@unittest.skipUnless(os.path.exists(_LIVE_DB), "live MOS db not present")
class ExecuteMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        _TMP.mkdir(parents=True, exist_ok=True)
        self.db = _TMP / "mos_s5_apply.sqlite3"
        if self.db.exists():
            self.db.unlink()
        shutil.copy2(_LIVE_DB, self.db)

    def tearDown(self) -> None:
        for p in (self.db, *(_TMP.glob("mos_s5_apply.sqlite3.pre-workbook-*.bak"))):
            try:
                p.unlink()
            except FileNotFoundError:
                pass

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
        from MyCiteV2.packages.adapters.sql.datum_workbook_apply import execute_migration, load_workbook
        from MyCiteV2.packages.core.datum_ops import (
            RebuildCollection,
            RecompileMagnitude,
            RelocateNode,
            plan_migration,
        )

        store = self._store()
        wb = load_workbook(store, tenant_id="fnd", sandbox="agro_erp")
        # brassica_carinata is wrongly under the catch-all; brassica genus exists.
        species_node = self._node_by_title(wb, "brassica_carinata")
        genus_node = self._node_by_title(wb, "brassica")
        self.assertTrue(species_node.startswith("4-"), species_node)

        ops = [
            RelocateNode("txa", species_node, genus_node),
            RecompileMagnitude("anchor", "1-1-1", "txa"),
            RebuildCollection("txa", "5-0-1", "txa_id_collection"),
        ]
        plan = plan_migration(wb, ops)
        self.assertIn("txa", plan.touched)
        self.assertIn("anchor", plan.touched)

        result = execute_migration(self.db, plan, tenant_id="fnd")
        self.assertEqual(result["status"], "applied")
        self.assertIsNotNone(result["backup"])

        # re-read: brassica_carinata now nests under brassica; 0 dangling; ids changed
        store2 = self._store()
        wb2 = load_workbook(store2, tenant_id="fnd", sandbox="agro_erp")
        new_node = self._node_by_title(wb2, "brassica_carinata")
        self.assertTrue(new_node.startswith(genus_node + "-"), f"{new_node} not under {genus_node}")
        from MyCiteV2.packages.core.datum_ops import check_step
        self.assertTrue(check_step(wb2).ok, check_step(wb2).hard[:5])

        # idempotent: re-plan with recompile/rebuild only → no change
        replan = plan_migration(wb2, [
            RecompileMagnitude("anchor", "1-1-1", "txa"),
            RebuildCollection("txa", "5-0-1", "txa_id_collection"),
        ])
        self.assertEqual(replan.touched, {})


if __name__ == "__main__":
    unittest.main()
