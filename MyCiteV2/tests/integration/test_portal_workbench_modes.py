"""Three-mode workbench + product_profile end-to-end tests (2026-05-17).

Pins the user-facing simplification:

* The unified workbench bundle changes its labels, posture, document
  filter, and Author-mode form availability based on the resolved
  sandbox — there is no separate "WORKBENCH UI" vs. "Agro-ERP"
  divergence in the runtime.
* The control panel emits exactly three mode tabs (Docs, Datums,
  Author) plus mode-filtered navigation_groups and collapsed
  disclosure_groups (Display options, Inspector).
* The `product_profile` template, once registered, appears in the
  agro_erp sandbox's new_source_document_form and round-trips
  through the stage → preview → apply scaffold pipeline as a new
  MOS document.
"""

from __future__ import annotations

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
from MyCiteV2.instances._shared.runtime.portal_workbench_ui_runtime import (
    build_portal_workbench_ui_bundle,
)
from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.datum_templates import TemplateRegistry
from MyCiteV2.packages.ports.datum_store import AuthoritativeDatumDocumentRequest
from MyCiteV2.packages.state_machine.portal_shell import PortalScope

LIVE_DB = Path("/srv/webapps/mycite/fnd/private/mos_authority.sqlite3")
_MSN = "3-2-3-17-77-1-6-4-1-4"


def _build(sandbox=None, *, db, query=None):
    return build_portal_workbench_ui_bundle(
        portal_scope=PortalScope(scope_id="fnd"),
        portal_domain="fnd",
        shell_state=None,
        authority_db_file=db,
        surface_query=query,
        sandbox=sandbox,
    )


@unittest.skipUnless(LIVE_DB.exists(), "live MOS authority db not present")
class PortalWorkbenchModesTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = Path(tempfile.mkdtemp(prefix="workbench_modes_"))
        self._db = self._tmpdir / "mos.sqlite3"
        self._db.write_bytes(LIVE_DB.read_bytes())

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    # --- Template availability -----------------------------------------

    def test_product_profile_template_registered_for_agro_erp(self) -> None:
        registry = TemplateRegistry()
        template = registry.get("product_profile")
        self.assertIsNotNone(template, "product_profile template should be loadable")
        self.assertEqual(template.sandbox, "agro_erp")
        self.assertEqual(template.archetype, "agro_erp_product_profile_row")
        self.assertGreaterEqual(len(template.header_rows), 4)
        agro_templates = {t.template_id for t in registry.all() if t.sandbox == "agro_erp"}
        self.assertIn("product_profile", agro_templates)
        self.assertIn("agro_erp_taxonomy_source", agro_templates)

    # --- Sandbox parameterisation --------------------------------------

    def test_every_sandbox_is_writable(self) -> None:
        # Every sandbox is writable. The Author tab is always available,
        # both author forms are always emitted, and read_write_posture is
        # always "write". This replaces the prior assumption that system
        # (and any non-agro_erp sandbox) was read-only.
        for sandbox in ("system", "agro_erp", "cts_gis", "fnd_csm"):
            bundle = _build(sandbox, db=self._db)
            self.assertEqual(bundle["read_write_posture"], "write", sandbox)
            self.assertEqual(bundle["sandbox_id"], sandbox)
            self.assertIsNotNone(
                bundle["surface_payload"].get("new_source_document_form"),
                f"new_source_document_form should be populated for {sandbox}",
            )
            self.assertIsNotNone(
                bundle["surface_payload"].get("new_datum_form"),
                f"new_datum_form should be populated for {sandbox}",
            )
            mode = bundle["control_panel"]["workbench_mode"] or {}
            self.assertTrue(mode.get("writable"), sandbox)
            tabs_by_mode = {t["mode"]: t for t in mode.get("tabs") or []}
            self.assertTrue(
                tabs_by_mode["author"]["available"],
                f"Author tab should be available for {sandbox}",
            )
            self.assertIn(
                "new_source_document",
                mode.get("author_forms") or {},
                f"author_forms.new_source_document should be present for {sandbox}",
            )
            self.assertIn(
                "new_datum",
                mode.get("author_forms") or {},
                f"author_forms.new_datum should be present for {sandbox}",
            )
            ndf = bundle["surface_payload"]["new_datum_form"]
            self.assertEqual(ndf["operation"], "insert_datum")
            self.assertEqual(ndf["target_authority"], "datum_workbench")
            self.assertIn("composer", ndf)

    def test_every_sandbox_has_at_least_one_template_registered(self) -> None:
        # The Datum Document Create button only enables when the sandbox
        # has at least one DatumTemplate registered. After
        # system_scratchpad + cts_gis_scratchpad land, all four sandboxes
        # carry baseline templates so the Create button works everywhere.
        registry = TemplateRegistry()
        templates_by_sandbox: dict[str, list[str]] = {}
        for template in registry.all():
            templates_by_sandbox.setdefault(template.sandbox, []).append(
                template.template_id
            )
        for sandbox in ("system", "agro_erp", "cts_gis", "fnd_csm"):
            template_ids = templates_by_sandbox.get(sandbox) or []
            self.assertGreaterEqual(
                len(template_ids),
                1,
                f"{sandbox} should have ≥1 template registered "
                f"(got {template_ids})",
            )
        self.assertIn("system_scratchpad", templates_by_sandbox.get("system", []))
        self.assertIn("cts_gis_scratchpad", templates_by_sandbox.get("cts_gis", []))

        # And confirm the workbench surface payload exposes those
        # template ids in available_templates for the create-doc form.
        for sandbox, expected_id in (
            ("system", "system_scratchpad"),
            ("cts_gis", "cts_gis_scratchpad"),
        ):
            bundle = _build(sandbox, db=self._db)
            form = bundle["surface_payload"]["new_source_document_form"]
            template_ids = {
                t["template_id"]
                for t in form.get("available_templates") or []
            }
            self.assertIn(
                expected_id,
                template_ids,
                f"{sandbox} new_source_document_form should advertise "
                f"{expected_id} (got {template_ids})",
            )

    def test_agro_erp_sandbox_is_writable_with_author_tab(self) -> None:
        bundle = _build("agro_erp", db=self._db)
        self.assertEqual(bundle["read_write_posture"], "write")
        self.assertEqual(bundle["sandbox_id"], "agro_erp")
        self.assertEqual(bundle["sandbox_label"], "Agro-ERP")
        # Document collection filtered to agro_erp.
        docs = bundle["workbench"]["document_collection"]["documents"]
        self.assertTrue(docs, "agro_erp sandbox should have bootstrapped docs")
        for doc in docs:
            self.assertIn(".agro_erp.", doc.get("document_id", ""))
        # Author forms present with both templates.
        form = bundle["surface_payload"].get("new_source_document_form")
        self.assertIsNotNone(form)
        template_ids = {t["template_id"] for t in form.get("available_templates", [])}
        self.assertIn("product_profile", template_ids)
        self.assertIn("agro_erp_taxonomy_source", template_ids)
        # Mode payload exposes the Author tab as available.
        mode = bundle["control_panel"]["workbench_mode"] or {}
        tabs_by_mode = {t["mode"]: t for t in mode.get("tabs") or []}
        self.assertTrue(tabs_by_mode["author"]["available"])
        self.assertTrue(mode.get("writable"))
        # Author forms lifted onto control panel for the renderer.
        self.assertIn("new_source_document", mode.get("author_forms") or {})
        self.assertIn("new_datum", mode.get("author_forms") or {})

    def test_sandbox_filter_via_surface_query_matches_kwarg(self) -> None:
        kwarg_bundle = _build("agro_erp", db=self._db)
        query_bundle = _build(db=self._db, query={"sandbox_filter": "agro_erp"})
        self.assertEqual(kwarg_bundle["sandbox_id"], query_bundle["sandbox_id"])
        self.assertEqual(kwarg_bundle["read_write_posture"], query_bundle["read_write_posture"])
        self.assertEqual(
            len(kwarg_bundle["workbench"]["document_collection"]["documents"]),
            len(query_bundle["workbench"]["document_collection"]["documents"]),
        )

    # --- Three-mode panel composition ----------------------------------

    def test_default_landing_is_docs_mode(self) -> None:
        bundle = _build("agro_erp", db=self._db)
        cp = bundle["control_panel"]
        self.assertEqual((cp.get("workbench_mode") or {}).get("active"), "docs")
        nav_titles = [g.get("title") for g in cp.get("navigation_groups") or []]
        self.assertIn("Documents", nav_titles)
        # Display options disclosure is present and collapsed by default.
        discl = {g.get("title"): g for g in cp.get("disclosure_groups") or []}
        self.assertIn("Display options", discl)
        self.assertFalse(discl["Display options"].get("expanded"))

    def test_docs_mode_writable_sandbox_surfaces_create_button(self) -> None:
        # The user's #2 complaint after v1 shipped: the create affordance
        # is invisible from Docs mode. Pin the v2 fix: writable sandboxes
        # get a "Create" nav group whose single entry shell_requests
        # mode=author so clicking lands in the Author tab with the form.
        bundle = _build("agro_erp", db=self._db)
        cp = bundle["control_panel"]
        groups = cp.get("navigation_groups") or []
        titles = [g.get("title") for g in groups]
        self.assertEqual(titles[0], "Create", "Create group should be the first nav group in Docs mode")
        self.assertEqual(titles[1], "Documents")
        create_entries = groups[0].get("entries") or []
        self.assertEqual(len(create_entries), 1)
        self.assertEqual(create_entries[0].get("label"), "+ New document")
        shell_request = create_entries[0].get("shell_request") or {}
        self.assertEqual(
            (shell_request.get("surface_query") or {}).get("mode"),
            "author",
            "+ New document entry should switch the workbench into Author mode",
        )

    def test_docs_mode_every_sandbox_surfaces_create_button(self) -> None:
        # Every sandbox is writable; even system shows the Create group in
        # Docs mode so the create affordance is always discoverable.
        bundle = _build(db=self._db)  # default sandbox=system
        cp = bundle["control_panel"]
        titles = [g.get("title") for g in cp.get("navigation_groups") or []]
        self.assertEqual(titles[0], "Create")
        self.assertEqual(titles[1], "Documents")

    def test_docs_nav_filters_documents_to_effective_sandbox(self) -> None:
        # The control-panel Documents nav group used to leak the entire
        # catalog when the sandbox filter was active. v2 pins the filter
        # so the panel and the workbench region stay in sync.
        sys_bundle = _build(db=self._db)
        agro_bundle = _build("agro_erp", db=self._db)

        def _docs_count(bundle):
            nav = bundle["control_panel"]["navigation_groups"]
            docs_group = next(g for g in nav if g.get("title") == "Documents")
            return len(docs_group.get("entries") or [])

        sys_count = _docs_count(sys_bundle)
        agro_count = _docs_count(agro_bundle)
        self.assertGreater(sys_count, 0)
        self.assertGreater(agro_count, 0)
        self.assertLess(
            agro_count, sys_count,
            f"agro_erp Documents nav ({agro_count}) should be a strict subset of system ({sys_count})",
        )
        # And it should match the workbench region's filtered collection.
        agro_workbench_docs = len(agro_bundle["workbench"]["document_collection"]["documents"])
        self.assertEqual(agro_count, agro_workbench_docs)

    def test_explicit_mode_author_activates_inline_forms(self) -> None:
        bundle = _build("agro_erp", db=self._db, query={"mode": "author"})
        cp = bundle["control_panel"]
        mode = cp.get("workbench_mode") or {}
        self.assertEqual(mode.get("active"), "author")
        forms = mode.get("author_forms") or {}
        self.assertIn("new_source_document", forms)
        nsf = forms["new_source_document"]
        self.assertEqual(nsf.get("sandbox_id"), "agro_erp")
        self.assertEqual(nsf.get("msn_id_default"), _MSN)
        template_ids = {t["template_id"] for t in nsf.get("available_templates") or []}
        self.assertIn("product_profile", template_ids)

    def test_datums_mode_emits_inspector_disclosure(self) -> None:
        # Need an explicit document query so the runtime lands in Datums mode.
        store = SqliteSystemDatumStoreAdapter(self._db)
        catalog = store.read_authoritative_datum_documents(
            AuthoritativeDatumDocumentRequest(tenant_id="fnd")
        )
        agro_docs = [d for d in catalog.documents if ".agro_erp." in d.document_id]
        self.assertTrue(agro_docs)
        target_id = agro_docs[0].document_id
        bundle = _build("agro_erp", db=self._db, query={"document": target_id})
        cp = bundle["control_panel"]
        self.assertEqual((cp.get("workbench_mode") or {}).get("active"), "datums")
        discl = {g.get("title"): g for g in cp.get("disclosure_groups") or []}
        self.assertIn("Display options", discl)
        self.assertIn("Inspector", discl)
        inspector_labels = {
            c.get("label") for c in (discl["Inspector"].get("context_conditions") or [])
        }
        for expected_label in {"Version", "Row Identity", "Resolved Lens", "Document Sort"}:
            self.assertIn(expected_label, inspector_labels)

    def test_context_conditions_are_slim(self) -> None:
        # Pre-refactor: Version, Row Identity, Resolved Lens, Document
        # Sort etc. all crowded the chrome. New chrome keeps only Sandbox
        # (always), Document (when selected_document_id), Selected Row
        # (when selected_row_address).
        bundle = _build("agro_erp", db=self._db)
        cp = bundle["control_panel"]
        labels = {c.get("label") for c in cp.get("context_conditions") or []}
        for moved_to_inspector in {"Version", "Row Identity", "Resolved Lens"}:
            self.assertNotIn(moved_to_inspector, labels)

    # --- End-to-end product_profile scaffold ---------------------------

    def test_product_profile_scaffold_round_trip(self) -> None:
        document_name = "product_profiles_test"
        payload = {
            "target_authority": "datum_workbench",
            "sandbox_id": "agro_erp",
            "operation": "scaffold_datum",
            "template_id": "product_profile",
            "msn_id": _MSN,
            "document_name": document_name,
            "canonical_name": document_name,
        }
        stage = run_datum_workbench_mutation_action(
            "stage", payload, authority_db_file=self._db, portal_instance_id="fnd",
        )
        self.assertTrue(stage.get("ok"), f"stage failed: {stage}")

        preview = run_datum_workbench_mutation_action(
            "preview", payload, authority_db_file=self._db, portal_instance_id="fnd",
        )
        self.assertTrue(preview.get("ok"), f"preview failed: {preview}")
        preview_body = preview.get("preview") or {}
        self.assertEqual(preview_body.get("status"), "previewed")
        new_id = preview_body.get("document_id") or ""
        self.assertIn(".agro_erp.", new_id)
        self.assertIn(f".{document_name}.", new_id)

        apply_result = run_datum_workbench_mutation_action(
            "apply", payload, authority_db_file=self._db, portal_instance_id="fnd",
        )
        self.assertTrue(apply_result.get("ok"))

        store = SqliteSystemDatumStoreAdapter(self._db, allow_legacy_writes=True)
        catalog = store.read_authoritative_datum_documents(
            AuthoritativeDatumDocumentRequest(tenant_id="fnd")
        )
        new_doc = next(
            (d for d in catalog.documents if d.document_id == apply_result["preview"]["document_id"]),
            None,
        )
        self.assertIsNotNone(new_doc, "product_profile doc should land in catalog")
        addresses = {row.datum_address for row in new_doc.rows}
        for expected in ("0-0-1", "0-0-2", "0-0-3", "0-0-4"):
            self.assertIn(expected, addresses, f"product_profile header row {expected} missing")

        # After scaffolding, the workbench builder should surface the new
        # document in the agro_erp document_collection.
        bundle = _build("agro_erp", db=self._db)
        post_doc_ids = {
            d.get("document_id") for d in bundle["workbench"]["document_collection"]["documents"]
        }
        self.assertIn(new_doc.document_id, post_doc_ids)


if __name__ == "__main__":
    unittest.main()
