from __future__ import annotations

import json
import re
import sqlite3
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.filesystem import FilesystemSystemDatumStoreAdapter
from MyCiteV2.packages.ports.datum_store import AuthoritativeDatumDocumentRequest

LIVE_FND_STATE_ROOT = Path("/srv/webapps/mycite/fnd")
LIVE_FND_DATA_DIR = LIVE_FND_STATE_ROOT / "data"
LIVE_FND_DB_FILE = LIVE_FND_STATE_ROOT / "private" / "mos_authority.sqlite3"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class MosProgramClosureTests(unittest.TestCase):
    def _require_live_fnd_data_dir(self) -> Path:
        if not LIVE_FND_DATA_DIR.exists():
            self.skipTest(f"live FND data dir not present: {LIVE_FND_DATA_DIR}")
        return LIVE_FND_DATA_DIR

    def _require_live_fnd_db(self) -> Path:
        if not LIVE_FND_DB_FILE.exists():
            self.skipTest(f"live FND authority db not present: {LIVE_FND_DB_FILE}")
        return LIVE_FND_DB_FILE

    # Required invariant. The 2026-05-17 MOS reconciliation cleared the
    # phantom + orphan + legacy-form drift; this test must remain green.
    def test_mos_documents_index_is_internally_consistent(self) -> None:
        """Every documents row has a matching datum_document_semantics payload,
        and every datum_document_semantics row has a corresponding documents
        index entry. No phantom docs, no orphan content.

        agro_erp+fnd_ebi+system+cts_gis are clean (the cts_gis phantom rows and
        the bulk of the fnd_csm orphans were cleaned up; precinct docs removed
        2026-06-25). The only remaining catalog-without-index rows are the derived
        fnd_analytics_summary_* aggregates, which are exempt below by design.
        """
        db_file = self._require_live_fnd_db()
        connection = sqlite3.connect(db_file)
        try:
            connection.row_factory = sqlite3.Row
            index_ids = {
                row["document_id"]
                for row in connection.execute(
                    "SELECT document_id FROM documents WHERE tenant_id = 'fnd'"
                )
            }
            semantic_ids = {
                row["document_id"]
                for row in connection.execute(
                    "SELECT document_id FROM datum_document_semantics WHERE tenant_id = 'fnd'"
                )
            }
            phantoms = index_ids - semantic_ids
            # Derived per-domain analytics aggregates (fnd_analytics_summary_*) live in the
            # authoritative catalog only: they are recomputed with a fresh content-hash on
            # every aggregation, so the stable `documents` index intentionally does not track
            # them (they are reached via /__fnd/analytics/summary, never the canonical index).
            # Exempt them from the orphan check; any OTHER orphan is still a real regression.
            orphans = {
                doc_id for doc_id in (semantic_ids - index_ids)
                if "fnd_analytics_summary_" not in doc_id
            }
            self.assertEqual(phantoms, set(), f"{len(phantoms)} phantom index rows")
            self.assertEqual(orphans, set(), f"{len(orphans)} orphan semantic payloads")
            # Structural shape: every sandbox has at least one anchor
            anchor_sandboxes = {
                row["sandbox"]
                for row in connection.execute(
                    "SELECT DISTINCT sandbox FROM documents WHERE tenant_id = 'fnd' AND is_anchor = 1"
                )
            }
            all_sandboxes = {
                row["sandbox"]
                for row in connection.execute(
                    "SELECT DISTINCT sandbox FROM documents WHERE tenant_id = 'fnd'"
                )
            }
            self.assertEqual(
                anchor_sandboxes,
                all_sandboxes,
                f"sandboxes without an anchor: {all_sandboxes - anchor_sandboxes}",
            )
        finally:
            connection.close()

    # Required invariant. Disk archival landed 2026-05-17; this test must remain green.
    def test_no_orphan_filesystem_datum_documents_under_fnd_data(self) -> None:
        """Inverted from the original FS↔MOS equivalence test. After the
        2026-05-05 MOS migration MOS is the sole datum authority; no
        canonical datum-doc JSON should remain on disk under
        ``data/{system,sandbox,payloads/cache}/``. Files matching the
        datum-doc shapes are forbidden; compiled UI payloads under
        ``data/payloads/compiled/`` are exempt.

        Currently expected to FAIL: ~141 on-disk datum-doc artifacts
        still present (see audit_report.md §1.1). Goes GREEN after
        Phase 7 archival.
        """
        data_dir = self._require_live_fnd_data_dir()
        forbidden_dirs = ["system", "sandbox", "payloads/cache"]
        forbidden_prefixes = ("lv.", "sc.", "cptr.", "stl.", "rf.", "tool.")
        forbidden_specific = {"anthology.json", "system_log.json"}
        violations: list[str] = []
        for forbidden_dir in forbidden_dirs:
            root = data_dir / forbidden_dir
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix not in {".json", ".bin"}:
                    continue
                name = path.name
                if name in forbidden_specific or any(name.startswith(p) for p in forbidden_prefixes):
                    violations.append(str(path.relative_to(data_dir)))
        self.assertEqual(
            violations,
            [],
            f"{len(violations)} on-disk datum-doc artifacts (first 5: {violations[:5]})",
        )

    def test_row_graph_referential_integrity_is_clean_for_every_canonical_document(self) -> None:
        """Sandbox-agnostic referential integrity. For every canonical
        ``lv.*`` document in MOS:

        - every row has non-empty semantic_hash and hyphae_hash
        - warnings_json is empty
        - every local_references target is a peer datum_address within the
          same document

        Replaces the cts_gis-specific cardinality test (which had hard-coded
        counts and only walked legacy-form ``sandbox:cts_gis:*`` IDs).
        """
        db_file = self._require_live_fnd_db()
        connection = sqlite3.connect(db_file)
        try:
            connection.row_factory = sqlite3.Row
            row_addresses_by_document: dict[str, set[str]] = {}
            for row in connection.execute(
                """
                SELECT document_id, datum_address
                FROM datum_row_semantics
                WHERE tenant_id = 'fnd' AND document_id LIKE 'lv.%'
                """
            ):
                row_addresses_by_document.setdefault(row["document_id"], set()).add(row["datum_address"])
            failures: list[str] = []
            for row in connection.execute(
                """
                SELECT document_id, datum_address, semantic_hash, hyphae_hash, local_references_json, warnings_json
                FROM datum_row_semantics
                WHERE tenant_id = 'fnd' AND document_id LIKE 'lv.%'
                """
            ):
                if not row["semantic_hash"]:
                    failures.append(f"{row['document_id']}:{row['datum_address']} missing semantic_hash")
                    continue
                if not row["hyphae_hash"]:
                    failures.append(f"{row['document_id']}:{row['datum_address']} missing hyphae_hash")
                    continue
                warnings = json.loads(row["warnings_json"] or "[]")
                if warnings:
                    failures.append(f"{row['document_id']}:{row['datum_address']} has warnings={warnings}")
                    continue
                local_references = json.loads(row["local_references_json"] or "[]")
                known_rows = row_addresses_by_document.get(row["document_id"], set())
                for reference in local_references:
                    if reference not in known_rows:
                        failures.append(
                            f"{row['document_id']}:{row['datum_address']} dangling ref -> {reference}"
                        )
                        break
        finally:
            connection.close()
        self.assertEqual(failures, [], f"{len(failures)} ref-integrity violations (first 5: {failures[:5]})")

    def test_fnd_authoritative_catalog_snapshot_uses_data_dir_relative_paths(self) -> None:
        db_file = self._require_live_fnd_db()
        connection = sqlite3.connect(db_file)
        try:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT payload_json
                FROM authoritative_catalog_snapshots
                WHERE tenant_id = 'fnd'
                """
            ).fetchone()
            self.assertIsNotNone(row)
            payload = json.loads(row["payload_json"])
        finally:
            connection.close()

        source_files = payload["source_files"]
        self.assertEqual(source_files["anthology"], "system/anthology.json")
        for key, value in source_files.items():
            items = value if isinstance(value, list) else [value]
            for item in items:
                self.assertFalse(str(item).startswith("/srv/repo/"), f"{key}: {item}")
                self.assertFalse(str(item).startswith("/srv/webapps/mycite/"), f"{key}: {item}")

    # Required invariant. After 2026-05-17 reconciliation no row in
    # datum_*_semantics uses legacy `sandbox:`/`system:` primary IDs.
    def test_no_legacy_compatibility_document_keys_remain_as_primary_ids(self) -> None:
        """Inverted from the original. After the one-cycle compatibility
        window closes (2026-06-05 per
        cts_gis_legacy_alias_retirement_timeline.md), the live FND DB must
        carry ZERO ``sandbox:%`` or ``system:%`` form document_ids as the
        primary key of ``datum_document_semantics`` or
        ``datum_row_semantics``. Only canonical ``lv.``/``stl.``/``cptr.``
        IDs are allowed.

        Currently expected to FAIL: 117 cts_gis docs still carry
        ``sandbox:cts_gis:%`` primary keys in datum_row_semantics. Goes
        GREEN after the MOS internal rekey + legacy_alias drop.
        """
        db_file = self._require_live_fnd_db()
        connection = sqlite3.connect(db_file)
        try:
            connection.row_factory = sqlite3.Row
            legacy_in_semantics = int(
                connection.execute(
                    "SELECT COUNT(DISTINCT document_id) AS count "
                    "FROM datum_document_semantics "
                    "WHERE tenant_id = 'fnd' AND (document_id LIKE 'sandbox:%' OR document_id LIKE 'system:%')"
                ).fetchone()["count"]
            )
            legacy_in_rows = int(
                connection.execute(
                    "SELECT COUNT(DISTINCT document_id) AS count "
                    "FROM datum_row_semantics "
                    "WHERE tenant_id = 'fnd' AND (document_id LIKE 'sandbox:%' OR document_id LIKE 'system:%')"
                ).fetchone()["count"]
            )
        finally:
            connection.close()
        self.assertEqual(legacy_in_semantics, 0, "datum_document_semantics still uses legacy primary IDs")
        self.assertEqual(legacy_in_rows, 0, "datum_row_semantics still uses legacy primary IDs")

    def test_required_authority_contracts_exist(self) -> None:
        """Positive-whitelist replacement for the closure-checklist enumerator.
        The old test failed any time a new markdown landed under
        docs/audits or docs/plans without being added to the YAML. This
        replacement asserts only that the SHORT, FIXED list of binding
        authority contracts continues to exist on disk and contains the
        canonical MOS-authority statement. New docs may be added freely.
        """
        required_paths = [
            "docs/contracts/datum_document_naming_taxonomy.md",
            "docs/contracts/cts_gis_legacy_alias_retirement_timeline.md",
            "docs/contracts/mos_database_schema_addendum.md",
            "docs/contracts/samras_structural_model.md",
        ]
        for rel in required_paths:
            path = REPO_ROOT / rel
            self.assertTrue(path.exists(), f"required contract missing: {rel}")
        taxonomy = _read_text(REPO_ROOT / "docs" / "contracts" / "datum_document_naming_taxonomy.md")
        normalized = re.sub(r"\s+", " ", taxonomy)
        self.assertIn("MOS authority database", normalized)
        self.assertIn("single runtime source of truth", normalized)

    @unittest.skip(
        "Original enumerator-style closure-checklist test. Replaced by "
        "test_required_authority_contracts_exist (positive whitelist). "
        "Kept skipped as a historical artifact for one cycle then to be "
        "deleted entirely; see audit_report.md §1.4."
    )
    def test_closure_checklist_covers_every_plan_and_report_artifact(self) -> None:
        checklist_path = REPO_ROOT / "docs" / "audits" / "reports" / "mos_program_closure_audit_checklist_2026-04-21.md"
        checklist_text = _read_text(checklist_path)
        entries: dict[str, tuple[str, str]] = {}
        for line in checklist_text.splitlines():
            if not line.startswith("| `docs/"):
                continue
            parts = [part.strip() for part in line.strip().strip("|").split("|")]
            if len(parts) != 4:
                continue
            path = parts[0].strip("`")
            entries[path] = (parts[1].strip("`"), parts[3])

        expected_paths = {
            path.relative_to(REPO_ROOT).as_posix()
            for root in (REPO_ROOT / "docs" / "plans", REPO_ROOT / "docs" / "audits" / "reports")
            for path in root.iterdir()
            if path.is_file()
        }
        self.assertEqual(set(entries), expected_paths)

        for path, (classification, note) in entries.items():
            self.assertIn(classification, {"authoritative", "supporting-current", "historical-superseded"})
            if classification != "historical-superseded":
                continue
            full_path = REPO_ROOT / path
            has_marker = full_path.suffix == ".md" and (
                "Historical status:" in _read_text(full_path) or "Supersession Note" in _read_text(full_path)
            )
            self.assertTrue(has_marker or "immutable evidence" in note.lower(), path)

    def test_active_mos_docs_drop_outdated_legacy_authority_phrases(self) -> None:
        master_plan = _read_text(REPO_ROOT / "docs" / "plans" / "master_plan_mos.md")
        index_yaml = _read_text(REPO_ROOT / "docs" / "plans" / "master_plan_mos.index.yaml")
        legacy_report = _read_text(
            REPO_ROOT / "docs" / "audits" / "reports" / "mos_sql_only_authority_activation_and_legacy_retirement_2026-04-21.md"
        )
        runtime_reality_report = _read_text(
            REPO_ROOT / "docs" / "audits" / "reports" / "mos_runtime_authority_and_access_reality_report_2026-04-21.md"
        )
        cts_gis_runtime_report = _read_text(
            REPO_ROOT / "docs" / "audits" / "reports" / "cts_gis_runtime_readiness_report_2026-04-25.md"
        )

        self.assertNotIn("keep filesystem adapters available as compatibility projections", master_plan)
        self.assertNotIn("filesystem adapters remain available as compatibility projections", master_plan)
        self.assertNotIn("while filesystem projections remain available", index_yaml)
        self.assertNotIn("rollback-safe filesystem projections remain available", index_yaml)
        self.assertNotIn("/srv/repo/mycite-core/deployed/fnd/private/mos_authority.sqlite3", master_plan)
        self.assertNotIn("deployed/fnd/private/mos_authority.sqlite3", legacy_report)
        self.assertNotIn("deployed/fnd/private/mos_authority.sqlite3", runtime_reality_report)
        self.assertNotIn("deployed/fnd/data/sandbox/cts-gis", cts_gis_runtime_report)
        self.assertIn("non-authoritative", master_plan)
        self.assertIn("non-authoritative", index_yaml)
        self.assertIn("non-authoritative", legacy_report)

    def test_migrated_system_runtime_defaults_are_sql_only(self) -> None:
        shell_runtime = _read_text(REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "portal_shell_runtime.py")
        workspace_runtime = _read_text(
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "portal_system_workspace_runtime.py"
        )

        self.assertIn('authority_mode: str = "sql_primary"', shell_runtime)
        self.assertNotIn('authority_mode: str = "filesystem"', shell_runtime)
        self.assertNotIn('authority_mode: str = "shadow"', shell_runtime)
        self.assertIn('authority_mode: str = "sql_primary"', workspace_runtime)
        self.assertNotIn('authority_mode: str = "filesystem"', workspace_runtime)
        self.assertNotIn('authority_mode: str = "shadow"', workspace_runtime)

    def test_python_source_drops_obsolete_filesystem_and_shadow_authority_modes(self) -> None:
        pattern = re.compile(r"authority_mode\s*[:=][^#\n]*[\"'](?:filesystem|shadow)[\"']")
        for path in (REPO_ROOT / "MyCiteV2").rglob("*.py"):
            if path.name == "test_mos_program_closure.py":
                continue
            self.assertIsNone(pattern.search(_read_text(path)), path.relative_to(REPO_ROOT).as_posix())

    def test_obsolete_mvp_runtime_is_removed(self) -> None:
        self.assertFalse((REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "mvp_runtime.py").exists())


if __name__ == "__main__":
    unittest.main()
