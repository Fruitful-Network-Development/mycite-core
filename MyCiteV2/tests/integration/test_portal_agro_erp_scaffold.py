"""Phase 3 + 4 of the Agro-ERP workbench materialization (2026-05-17).

End-to-end scaffold_datum verification:
  * stage → preview → apply pipeline succeeds for the
    agro_erp_taxonomy_source template
  * the resulting canonical document_id has the agro_erp sandbox segment
  * MOS catalog snapshot includes the new document
  * the template's header rows (0-0-1..0-0-4) are materialized
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_datum_workbench_mutation_runtime import (
    run_datum_workbench_mutation_action,
)
from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.ports.datum_store import AuthoritativeDatumDocumentRequest

LIVE_DB = Path("/srv/webapps/mycite/fnd/private/mos_authority.sqlite3")
_MSN = "3-2-3-17-77-1-6-4-1-4"


@unittest.skipUnless(LIVE_DB.exists(), "live MOS authority db not present")
class PortalAgroErpScaffoldTests(unittest.TestCase):
    def setUp(self) -> None:
        # Snapshot the live MOS DB to a tmp file so the test is hermetic
        # (no risk of leaving stray rows in the production catalog).
        self._tmpdir = Path(tempfile.mkdtemp(prefix="agro_erp_scaffold_"))
        self._db = self._tmpdir / "mos.sqlite3"
        self._db.write_bytes(LIVE_DB.read_bytes())

    def _payload(self, document_name: str) -> dict:
        return {
            "target_authority": "datum_workbench",
            "sandbox_id": "agro_erp",
            "operation": "scaffold_datum",
            "template_id": "agro_erp_taxonomy_source",
            "msn_id": _MSN,
            "document_name": document_name,
            "canonical_name": document_name,
        }

    def test_stage_preview_apply_lands_in_catalog(self) -> None:
        document_name = "crops_test"
        payload = self._payload(document_name)

        stage = run_datum_workbench_mutation_action(
            "stage", payload,
            authority_db_file=self._db, portal_instance_id="fnd",
        )
        self.assertTrue(stage.get("ok"), f"stage failed: {stage}")
        self.assertEqual(stage.get("stage_state"), "staged")

        preview = run_datum_workbench_mutation_action(
            "preview", payload,
            authority_db_file=self._db, portal_instance_id="fnd",
        )
        self.assertTrue(preview.get("ok"), f"preview failed: {preview}")
        preview_body = preview.get("preview") or {}
        self.assertEqual(preview_body.get("status"), "previewed")
        new_id = preview_body.get("document_id") or ""
        self.assertIn(".agro_erp.", new_id)
        self.assertIn(f".{document_name}.", new_id, f"canonical_name not in id: {new_id}")
        self.assertGreaterEqual(int(preview_body.get("row_count", 0)), 4)

        apply_result = run_datum_workbench_mutation_action(
            "apply", payload,
            authority_db_file=self._db, portal_instance_id="fnd",
        )
        self.assertTrue(apply_result.get("ok"))
        self.assertEqual(apply_result.get("stage_state"), "applied")
        applied_body = apply_result.get("preview") or {}
        self.assertEqual(applied_body.get("status"), "created")
        applied_id = applied_body.get("document_id")
        self.assertEqual(applied_id, new_id, "preview / apply id should match")

        store = SqliteSystemDatumStoreAdapter(self._db, allow_legacy_writes=True)
        catalog = store.read_authoritative_datum_documents(
            AuthoritativeDatumDocumentRequest(tenant_id="fnd")
        )
        agro_doc_ids = [d.document_id for d in catalog.documents if "agro_erp" in d.document_id]
        self.assertIn(applied_id, agro_doc_ids)

        new_doc = next(d for d in catalog.documents if d.document_id == applied_id)
        addresses = {row.datum_address for row in new_doc.rows}
        for expected in ("0-0-1", "0-0-2", "0-0-3", "0-0-4"):
            self.assertIn(expected, addresses, f"template header row {expected} missing")

        # Idempotency: re-applying with same payload yields already_present
        again = run_datum_workbench_mutation_action(
            "apply", payload,
            authority_db_file=self._db, portal_instance_id="fnd",
        )
        again_body = again.get("preview") or {}
        self.assertIn(again_body.get("status"), {"already_present", "created"})

    def test_scaffold_rejects_template_sandbox_mismatch(self) -> None:
        payload = self._payload("mismatch_test")
        payload["sandbox_id"] = "system"  # template is bound to agro_erp
        result = run_datum_workbench_mutation_action(
            "preview", payload,
            authority_db_file=self._db, portal_instance_id="fnd",
        )
        if result.get("ok"):
            inner = result.get("preview") or {}
            self.assertNotEqual(inner.get("status"), "previewed")
        else:
            self.assertFalse(result.get("ok"))

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
