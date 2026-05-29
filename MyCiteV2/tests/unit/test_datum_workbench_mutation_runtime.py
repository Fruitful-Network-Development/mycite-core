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


class CreateDocumentOperationTests(unittest.TestCase):
    """Stage 3b: title-only datum-document creation (review findings #2/#3/#4)."""

    def _bootstrap(self, db_file: Path) -> None:
        with TemporaryDirectory() as src:
            root = Path(src)
            data_dir = root / "data"
            public_dir = root / "public"
            (data_dir / "system").mkdir(parents=True)
            public_dir.mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text(
                '{\n  "1-0-1": [["1-0-1", "~", "0-0-0"], ["anchor-root"]]\n}\n',
                encoding="utf-8",
            )
            # canonical_ids: apply re-persists the whole catalog under the
            # canonical-only write posture, so the seed anchor must be canonical.
            SqliteSystemDatumStoreAdapter(db_file).bootstrap_from_filesystem(
                data_dir=data_dir,
                public_dir=public_dir,
                tenant_id="fnd",
                canonical_ids=True,
            )

    def _create(self, db_file: Path, *, title: str, action: str = "apply", sandbox_id: str = "agro_erp") -> dict:
        return run_datum_workbench_mutation_action(
            action,
            {
                "target_authority": "datum_workbench",
                "sandbox_id": sandbox_id,
                "msn_id": "3-2-3",
                "operation": "create_document",
                "document_name": title,
            },
            authority_db_file=db_file,
            portal_instance_id="fnd",
        )

    def test_create_document_is_allowlisted_and_stages(self) -> None:
        # Finding #4: the op must be allowlisted; a stale allowlist would make
        # the JS create flow silently no-op with unsupported_operation.
        with TemporaryDirectory() as tmp:
            db_file = Path(tmp) / "authority.sqlite3"
            self._bootstrap(db_file)
            staged = self._create(db_file, title="My Notes", action="stage")
            self.assertTrue(staged["ok"], staged)
            self.assertEqual(staged["stage_state"], "staged")

    def test_create_document_apply_creates_empty_canonical_document(self) -> None:
        with TemporaryDirectory() as tmp:
            db_file = Path(tmp) / "authority.sqlite3"
            self._bootstrap(db_file)
            result = self._create(db_file, title="My Notes")
            self.assertTrue(result["ok"], result)
            created = result["preview"]
            self.assertEqual(created["status"], "created")
            self.assertEqual(created["row_count"], 0)
            self.assertTrue(created["document_id"].startswith("lv.3-2-3.agro_erp.my_notes."), created["document_id"])

    def test_create_document_sanitizes_dotted_title_without_crash(self) -> None:
        # Finding #2: a free-text title with '.' would raise CanonicalNameError
        # if passed raw into format_canonical_document_id.
        with TemporaryDirectory() as tmp:
            db_file = Path(tmp) / "authority.sqlite3"
            self._bootstrap(db_file)
            result = self._create(db_file, title="Q1.2026 plan")
            self.assertTrue(result["ok"], result)
            created = result["preview"]
            self.assertEqual(created["status"], "created")
            # The '.' (and space) are stripped to a single dot-free name
            # segment; crucially the id is a valid, parseable canonical id
            # rather than raising CanonicalNameError.
            from MyCiteV2.packages.core.document_naming import (
                is_canonical_document_id,
                parse_canonical_document_id,
            )

            self.assertTrue(is_canonical_document_id(created["document_id"]))
            self.assertEqual(parse_canonical_document_id(created["document_id"]).sandbox, "agro_erp")

    def test_create_document_same_title_yields_distinct_ids(self) -> None:
        # Finding #3: empty docs are content-addressed; without a per-creation
        # nonce two same-titled creates would collide and the second would
        # silently dedupe to already_present.
        with TemporaryDirectory() as tmp:
            db_file = Path(tmp) / "authority.sqlite3"
            self._bootstrap(db_file)
            first = self._create(db_file, title="Untitled")["preview"]
            second = self._create(db_file, title="Untitled")["preview"]
            self.assertEqual(first["status"], "created")
            self.assertEqual(second["status"], "created")
            self.assertNotEqual(first["document_id"], second["document_id"])

    def test_create_document_requires_a_title(self) -> None:
        with TemporaryDirectory() as tmp:
            db_file = Path(tmp) / "authority.sqlite3"
            self._bootstrap(db_file)
            result = run_datum_workbench_mutation_action(
                "apply",
                {
                    "target_authority": "datum_workbench",
                    "sandbox_id": "agro_erp",
                    "msn_id": "3-2-3",
                    "operation": "create_document",
                },
                authority_db_file=db_file,
                portal_instance_id="fnd",
            )
            self.assertFalse(result["ok"])
            self.assertEqual(result["error"]["code"], "datum_mutation_failed")


if __name__ == "__main__":
    unittest.main()
