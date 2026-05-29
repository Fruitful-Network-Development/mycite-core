"""S7 — acceptance: the agro_erp TXA re-nesting end-to-end through datum_ops.

Copies the live MOS DB to /srv/agentic/tmp, runs the re-nesting harness, and
asserts the end state: catch-all collapses to a single 'unspecified' bucket, the
binomials nest under genera, products resolve (0 dangling), counts hold, and a
re-run is a clean no-op. Skips if the live DB is absent.
"""

from __future__ import annotations

import os
import shutil
import unittest
from pathlib import Path

_LIVE_DB = "/srv/webapps/mycite/fnd/private/mos_authority.sqlite3"
_TMP = Path("/srv/agentic/tmp")


@unittest.skipUnless(os.path.exists(_LIVE_DB), "live MOS db not present")
class RenestAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        _TMP.mkdir(parents=True, exist_ok=True)
        self.db = _TMP / "mos_s7_renest.sqlite3"
        if self.db.exists():
            self.db.unlink()
        shutil.copy2(_LIVE_DB, self.db)

    def tearDown(self) -> None:
        for p in (self.db, *_TMP.glob("mos_s7_renest.sqlite3.pre-workbook-*.bak")):
            try:
                p.unlink()
            except FileNotFoundError:
                pass

    def test_renest_end_to_end(self) -> None:
        import MyCiteV2.scripts.renest_agro_erp_txa as R
        from MyCiteV2.packages.adapters.sql.datum_store import SqliteSystemDatumStoreAdapter
        from MyCiteV2.packages.adapters.sql.datum_workbook_apply import execute_migration, load_workbook
        from MyCiteV2.packages.core.datum_ops import (
            build_reference_index,
            check_step,
            defined_node_addrs,
            plan_migration,
        )
        from MyCiteV2.packages.core.datum_ops import node_addrs as na

        store = SqliteSystemDatumStoreAdapter(self.db, allow_legacy_writes=False)
        baseline = load_workbook(store, tenant_id="fnd", sandbox="agro_erp")
        product_count = len(baseline.sheet("product_profiles").rows)

        plan = plan_migration(baseline, R.build_ops(baseline))
        self.assertEqual(set(plan.touched), {"anchor", "txa", "product_profiles"})

        result = execute_migration(self.db, plan, tenant_id="fnd")
        self.assertEqual(result["status"], "applied")

        # re-read and assert the end state
        wb = load_workbook(SqliteSystemDatumStoreAdapter(self.db, allow_legacy_writes=False),
                           tenant_id="fnd", sandbox="agro_erp")
        txa = wb.sheet("txa")
        leaves = sorted(n for n in defined_node_addrs(txa) if n == "4" or na.parent_of(n) == "4")
        self.assertEqual(leaves, ["4", "4-1"])  # root + single unspecified bucket

        n2t = {str(r.raw[0][2]): str(r.raw[1][0]).lower()
               for r in txa.rows if isinstance(r.raw, list) and len(r.raw) > 1 and r.raw[1]}
        self.assertEqual(n2t["4-1"], "unspecified")
        # brassica_carinata now nests under the pre-existing brassica genus
        bc = next(n for n, t in n2t.items() if t == "brassica_carinata")
        self.assertTrue(bc.startswith("1-1-3-3-5-8-21-4-4-"), bc)

        # product rows unchanged in count; only the 11 genuine-unknowns point at 4-1
        self.assertEqual(len(wb.sheet("product_profiles").rows), product_count)
        idx = build_reference_index(wb)
        ca = idx.references_to("4")
        self.assertEqual(len(ca), 11)
        self.assertEqual({e.target_node_addr for e in ca}, {"4-1"})

        self.assertTrue(check_step(wb).ok, check_step(wb).hard[:5])

        # idempotent: re-running on the migrated db produces no ops
        self.assertEqual(R.build_ops(wb), [])


if __name__ == "__main__":
    unittest.main()
