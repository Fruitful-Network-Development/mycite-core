"""S8 — the apply_workbook mutation verb (workbook engine reachable via the API).

Exercises run_datum_workbench_mutation_action(operation="apply_workbook"): an
edited workbook YAML is compiled to a plan; stage returns it without writing,
apply executes it. Uses an isolated copy of the live DB; skips if absent.
"""

from __future__ import annotations

import os
import shutil
import unittest
from pathlib import Path

_LIVE_DB = "/srv/webapps/mycite/fnd/private/mos_authority.sqlite3"
_TMP = Path("/srv/agentic/tmp")


@unittest.skipUnless(os.path.exists(_LIVE_DB), "live MOS db not present")
class ApplyWorkbookVerbTests(unittest.TestCase):
    def setUp(self) -> None:
        _TMP.mkdir(parents=True, exist_ok=True)
        self.db = _TMP / "mos_s8_verb.sqlite3"
        if self.db.exists():
            self.db.unlink()
        shutil.copy2(_LIVE_DB, self.db)

    def tearDown(self) -> None:
        for p in (self.db, *_TMP.glob("mos_s8_verb.sqlite3.pre-workbook-*.bak")):
            try:
                p.unlink()
            except FileNotFoundError:
                pass

    def _edited_yaml(self) -> str:
        """Produce an edited workbook = baseline with the catch-all root renamed.

        A rename (title change, no address change) is a clean localized edit the
        compiler recovers without sibling-renumber side effects — the right shape
        for the UI verb. (Bulk structural migration uses explicit ops; see S7.)
        """
        from MyCiteV2.packages.adapters.sql.datum_store import SqliteSystemDatumStoreAdapter
        from MyCiteV2.packages.adapters.sql.datum_workbook_apply import load_workbook
        from MyCiteV2.packages.core.datum_ops import RenameNode, apply_sequence, workbook_codec

        store = SqliteSystemDatumStoreAdapter(self.db, allow_legacy_writes=False)
        wb = load_workbook(store, tenant_id="fnd", sandbox="agro_erp")
        edited, _ = apply_sequence(wb, [RenameNode("txa", "4", "unspecified")])
        return workbook_codec.to_yaml(edited)

    def test_stage_then_apply(self) -> None:
        from MyCiteV2.instances._shared.runtime.portal_datum_workbench_mutation_runtime import (
            run_datum_workbench_mutation_action,
        )

        edited_yaml = self._edited_yaml()
        base_payload = {
            "target_authority": "datum_workbench",
            "operation": "apply_workbook",
            "sandbox_id": "agro_erp",
            "edited_workbook_yaml": edited_yaml,
        }

        staged = run_datum_workbench_mutation_action(
            "stage", base_payload, authority_db_file=self.db, portal_instance_id="fnd"
        )
        self.assertTrue(staged["ok"], staged)
        plan = staged["workbook_plan"]
        self.assertEqual(set(plan["touched_sheets"]), {"txa"})  # rename touches only txa

        applied = run_datum_workbench_mutation_action(
            "apply", base_payload, authority_db_file=self.db, portal_instance_id="fnd"
        )
        self.assertTrue(applied["ok"], applied)
        self.assertEqual(applied["apply_result"]["status"], "applied")

    def test_bad_yaml_errors_cleanly(self) -> None:
        from MyCiteV2.instances._shared.runtime.portal_datum_workbench_mutation_runtime import (
            run_datum_workbench_mutation_action,
        )

        res = run_datum_workbench_mutation_action(
            "stage",
            {"target_authority": "datum_workbench", "operation": "apply_workbook",
             "sandbox_id": "agro_erp", "edited_workbook_yaml": "not: a: workbook"},
            authority_db_file=self.db, portal_instance_id="fnd",
        )
        self.assertFalse(res["ok"])


if __name__ == "__main__":
    unittest.main()
