from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_datum_workbench_mutation_runtime import (
    run_datum_workbench_mutation_action,
)
from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter


class DatumWorkbenchMutationRuntimeTests(unittest.TestCase):
    def test_stage_validates_sandbox_ownership(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            public_dir = root / "public"
            db_file = root / "authority.sqlite3"
            (data_dir / "system").mkdir(parents=True)
            public_dir.mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text(
                '{\n  "1-0-1": [["1-0-1", "~", "0-0-0"], ["anchor-root"]]\n}\n',
                encoding="utf-8",
            )
            SqliteSystemDatumStoreAdapter(db_file).bootstrap_from_filesystem(
                data_dir=data_dir,
                public_dir=public_dir,
                tenant_id="fnd",
            )
            ok = run_datum_workbench_mutation_action(
                "stage",
                {
                    "target_authority": "datum_workbench",
                    "sandbox_id": "system",
                    "document_id": "system:anthology",
                    "datum_address": "1-0-1",
                    "operation": "update_row_raw",
                },
                authority_db_file=db_file,
                portal_instance_id="fnd",
            )
            self.assertTrue(ok["ok"])
            self.assertEqual(ok["nimm_envelope"]["verb"], "manipulate")

            rejected = run_datum_workbench_mutation_action(
                "stage",
                {
                    "target_authority": "datum_workbench",
                    "sandbox_id": "cts-gis",
                    "document_id": "system:anthology",
                    "datum_address": "1-0-1",
                    "operation": "update_row_raw",
                },
                authority_db_file=db_file,
                portal_instance_id="fnd",
            )
            self.assertFalse(rejected["ok"])
            self.assertEqual(rejected["error"]["code"], "sandbox_document_mismatch")

    def test_preview_update_row_raw_is_directive_backed_without_persisting(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            public_dir = root / "public"
            db_file = root / "authority.sqlite3"
            (data_dir / "system").mkdir(parents=True)
            public_dir.mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text(
                '{\n  "1-0-1": [["1-0-1", "~", "0-0-0"], ["anchor-root"]]\n}\n',
                encoding="utf-8",
            )
            SqliteSystemDatumStoreAdapter(db_file).bootstrap_from_filesystem(
                data_dir=data_dir,
                public_dir=public_dir,
                tenant_id="fnd",
            )
            result = run_datum_workbench_mutation_action(
                "preview",
                {
                    "target_authority": "datum_workbench",
                    "sandbox_id": "system",
                    "document_id": "system:anthology",
                    "datum_address": "1-0-1",
                    "operation": "update_row_raw",
                    "payload_text": '[["1-0-1", "~", "1-1-1"], ["updated"]]',
                },
                authority_db_file=db_file,
                portal_instance_id="fnd",
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["stage_state"], "previewed")
            rows = result["preview"]["updated_document"]["rows"]
            self.assertEqual(rows[0]["raw"][1], ["updated"])


if __name__ == "__main__":
    unittest.main()
