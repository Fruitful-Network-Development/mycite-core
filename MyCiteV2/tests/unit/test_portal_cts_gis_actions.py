from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import dataclasses

from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import run_portal_cts_gis_action
from MyCiteV2.packages.adapters.sql import SqliteAuditLogAdapter, SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.adapters.sql.datum_semantics import build_document_semantics
from MyCiteV2.packages.core.document_naming import derive_canonical_id_from_legacy
from MyCiteV2.packages.ports.audit_log import AuditLogRecentWindowRequest
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentCatalogResult,
    AuthoritativeDatumDocumentRow,
)


def _canonical(document: AuthoritativeDatumDocument, *, msn_id: str = "3-2-3") -> AuthoritativeDatumDocument:
    """Rewrite a legacy-id fixture document to its canonical ``lv.`` id, keyed
    by the document's own content hash. Apply-path tests need this because the
    runtime persists under the canonical-only write posture; read/stage-only
    fixtures keep their legacy ids (reads do not validate canonicality)."""
    version_hash = build_document_semantics(document)["document"]["version_hash"]
    canonical_id = derive_canonical_id_from_legacy(
        document.document_id, msn_id=msn_id, version_hash=version_hash
    )
    return dataclasses.replace(document, document_id=canonical_id)


def _ascii_bits(value: str, *, width: int = 256) -> str:
    bitstream = "".join(format(ord(char), "08b") for char in value)
    return bitstream.ljust(width, "0")


def _row(datum_address: str, node_address: str, title: str, *, width: int = 256) -> AuthoritativeDatumDocumentRow:
    return AuthoritativeDatumDocumentRow(
        datum_address=datum_address,
        raw=[
            [datum_address, "rf.3-1-2", node_address, "rf.3-1-3", _ascii_bits(title, width=width)],
            [title.replace(" ", "_")],
        ],
    )


def _document() -> AuthoritativeDatumDocument:
    return AuthoritativeDatumDocument(
        document_id="sandbox:cts_gis:sc.example.json",
        source_kind="sandbox_source",
        document_name="sc.example.json",
        relative_path="sandbox/cts-gis/sources/sc.example.json",
        tool_id="cts_gis",
        rows=(
            _row("4-2-1", "3-2-3-17-77-1", "ALPHA STREET"),
            _row("4-2-2", "3-2-3-17-77-2", "BETA STREET"),
            _row("4-2-3", "3-2-3-17-77-2", "GAMMA STREET"),
        ),
    )


def _document_with_duplicate_target_group() -> AuthoritativeDatumDocument:
    return AuthoritativeDatumDocument(
        document_id="sandbox:cts_gis:sc.duplicate.json",
        source_kind="sandbox_source",
        document_name="sc.duplicate.json",
        relative_path="sandbox/cts-gis/sources/sc.duplicate.json",
        tool_id="cts_gis",
        rows=(
            _row("4-2-1", "3-2-3-17-77-1", "ALPHA STREET"),
            _row("4-2-2", "3-2-3-17-77-2", "BETA STREET"),
            _row("4-2-3", "3-2-3-17-77-1", "GAMMA STREET"),
        ),
    )


def _document_with_narrow_local_template() -> AuthoritativeDatumDocument:
    return AuthoritativeDatumDocument(
        document_id="sandbox:cts_gis:sc.narrow.json",
        source_kind="sandbox_source",
        document_name="sc.narrow.json",
        relative_path="sandbox/cts-gis/sources/sc.narrow.json",
        tool_id="cts_gis",
        rows=(
            _row("4-2-1", "3-2-3-17-77-1-6", "SHORT ROAD", width=88),
            _row("4-2-2", "3-2-3-17-77-1-2", "WIDE TEMPLATE STREET", width=256),
        ),
    )


def _document_with_sparse_family() -> AuthoritativeDatumDocument:
    return AuthoritativeDatumDocument(
        document_id="sandbox:cts_gis:sc.sparse.json",
        source_kind="sandbox_source",
        document_name="sc.sparse.json",
        relative_path="sandbox/cts-gis/sources/sc.sparse.json",
        tool_id="cts_gis",
        rows=(
            _row("4-2-1", "3-2-3-17-77-1-6", "FIRST ROAD"),
            _row("4-2-3", "3-2-3-17-77-1-2", "THIRD ROAD"),
        ),
    )


def _address_nodes_document() -> AuthoritativeDatumDocument:
    return AuthoritativeDatumDocument(
        document_id="sandbox:cts_gis:sc.example.msn-address_nodes.json",
        source_kind="sandbox_source",
        document_name="sc.example.msn-address_nodes.json",
        relative_path="sandbox/cts-gis/sources/sc.example.msn-address_nodes.json",
        tool_id="cts_gis",
        rows=(
            AuthoritativeDatumDocumentRow(
                datum_address="4-2-1",
                raw=[
                    ["4-2-1", "rf.3-1-2", "3-2-3-17-18-1-1-1-1", "rf.3-1-3", _ascii_bits("FIRST ADDRESS")],
                    ["first_address"],
                ],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="4-2-2",
                raw=[
                    [
                        "4-2-2",
                        "rf.3-1-2",
                        "3-2-3-17-18-1-1-2-1",
                        "rf.3-1-3",
                        _ascii_bits("QUALIFIED REF"),
                        "3-2-3-17-28-3-4-2-1",
                    ],
                    ["qualified_ref"],
                ],
            ),
        ),
    )


class PortalCtsGisActionRuntimeTests(unittest.TestCase):
    def _stage_document(self, document_id: str = "sandbox:cts_gis:sc.example.json") -> dict[str, object]:
        return {
            "schema": "mycite.v2.cts_gis.stage_insert.v1",
            "document_id": document_id,
            "document_name": "sc.example.json",
            "operation": "insert_datums",
            "datums": [
                {
                    "family": "administrative_street",
                    "valueGroup": 2,
                    "targetNodeAddress": "3-2-3-17-77-1",
                    "title": "MAIN STREET",
                    "references": [
                        {"type": "title", "text": "MAIN STREET"},
                        {"type": "msn-samras", "nodeAddress": "3-2-3-17-77-1"},
                    ],
                }
            ],
        }

    def _seed_db(self, db_file: Path) -> None:
        SqliteSystemDatumStoreAdapter(db_file, allow_legacy_writes=True).store_authoritative_catalog(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(_document(),),
                source_files={"sandbox/cts-gis/sources/sc.example.json": {"exists": True}},
                readiness_status={"authoritative_catalog": "loaded"},
            )
        )

    def _seed_db_canonical(self, db_file: Path) -> str:
        """Seed the example document with a canonical id and return that id.

        The apply path re-persists the catalog, which the canonical-only write
        posture rejects for legacy ids; this is the seed for the round-trip
        apply test."""
        document = _canonical(_document())
        SqliteSystemDatumStoreAdapter(db_file, allow_legacy_writes=True).store_authoritative_catalog(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(document,),
                source_files={"sandbox/cts-gis/sources/sc.example.json": {"exists": True}},
                readiness_status={"authoritative_catalog": "loaded"},
            )
        )
        return document.document_id

    def _seed_document(self, db_file: Path, document: AuthoritativeDatumDocument) -> None:
        SqliteSystemDatumStoreAdapter(db_file, allow_legacy_writes=True).store_authoritative_catalog(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(document,),
                source_files={document.relative_path: {"exists": True}},
                readiness_status={"authoritative_catalog": "loaded"},
            )
        )

    def _request(self, tool_state: dict[str, object] | None, action_kind: str, action_payload: dict[str, object]) -> dict[str, object]:
        return {
            "schema": "mycite.v2.portal.system.tools.cts_gis.action.request.v1",
            "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
            "tool_state": tool_state
            or {
                "selected_node_id": "3-2-3-17-77-1",
                "source": {"attention_document_id": "sandbox:cts_gis:sc.example.json"},
            },
            "action_kind": action_kind,
            "action_payload": action_payload,
        }

    def test_stage_accepts_structure_operation_for_compound_directives(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "authority.sqlite3"
            self._seed_db(db_file)
            staged = run_portal_cts_gis_action(
                self._request(
                    None,
                    "stage_insert_yaml",
                    {
                        "stage_document": self._stage_document(),
                        "structure_operation": {
                            "operation": "expand_samras",
                            "target_node_address": "3-2-3-17-77-1",
                            "new_node_addresses": ["3-2-3-17-77-1-99"],
                        },
                    },
                ),
                data_dir=None,
                authority_db_file=db_file,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            compound = staged["surface_payload"]["staged_insert"]["compiled_nimm_envelope"]["compound_directives"]
            self.assertEqual(compound["schema"], "mycite.v2.nimm.compound.v1")
            self.assertEqual(len(compound["steps"]), 2)

    def test_preview_apply_accepts_duplicate_target_node_bindings(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "authority.sqlite3"
            self._seed_document(db_file, _document_with_duplicate_target_group())
            staged = run_portal_cts_gis_action(
                self._request(
                    {
                        "selected_node_id": "3-2-3-17-77-1",
                        "source": {"attention_document_id": "sandbox:cts_gis:sc.duplicate.json"},
                    },
                    "stage_insert_yaml",
                    {
                        "stage_document": {
                            "schema": "mycite.v2.cts_gis.stage_insert.v1",
                            "document_id": "sandbox:cts_gis:sc.duplicate.json",
                            "document_name": "sc.duplicate.json",
                            "operation": "insert_datums",
                            "datums": [
                                {
                                    "family": "administrative_street",
                                    "valueGroup": 2,
                                    "targetNodeAddress": "3-2-3-17-77-1",
                                    "title": "MAIN STREET",
                                    "references": [
                                        {"type": "title", "text": "MAIN STREET"},
                                        {"type": "msn-samras", "nodeAddress": "3-2-3-17-77-1"},
                                    ],
                                }
                            ],
                        }
                    },
                ),
                data_dir=None,
                authority_db_file=db_file,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            preview = run_portal_cts_gis_action(
                self._request(staged["surface_payload"]["tool_state"], "preview_apply", {}),
                data_dir=None,
                authority_db_file=db_file,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            self.assertEqual(preview["surface_payload"]["action_result"]["status"], "accepted")
            self.assertEqual(
                preview["surface_payload"]["staged_insert"]["last_preview"]["proposed_inserted_rows"][0]["datum_address"],
                "4-2-4",
            )

    def test_preview_apply_supports_address_node_rows_with_hyphen_qualified_refs(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "authority.sqlite3"
            self._seed_document(db_file, _address_nodes_document())
            staged = run_portal_cts_gis_action(
                self._request(
                    {
                        "selected_node_id": "3-2-3-17-18-1-1-1-1",
                        "source": {"attention_document_id": "sandbox:cts_gis:sc.example.msn-address_nodes.json"},
                    },
                    "stage_insert_yaml",
                    {
                        "stage_document": {
                            "schema": "mycite.v2.cts_gis.stage_insert.v1",
                            "document_id": "sandbox:cts_gis:sc.example.msn-address_nodes.json",
                            "document_name": "sc.example.msn-address_nodes.json",
                            "operation": "insert_datums",
                            "datums": [
                                {
                                    "family": "administrative_street",
                                    "valueGroup": 2,
                                    "targetNodeAddress": "3-2-3-17-77-1-6-999-2",
                                    "title": "999_ZZ_TEST_ROAD",
                                    "references": [
                                        {"type": "title", "text": "999_ZZ_TEST_ROAD"},
                                        {"type": "msn-samras", "nodeAddress": "3-2-3-17-77-1-6-999-2"},
                                    ],
                                }
                            ],
                        }
                    },
                ),
                data_dir=None,
                authority_db_file=db_file,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            preview = run_portal_cts_gis_action(
                self._request(staged["surface_payload"]["tool_state"], "preview_apply", {}),
                data_dir=None,
                authority_db_file=db_file,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            self.assertEqual(preview["surface_payload"]["action_result"]["status"], "accepted")
            self.assertEqual(
                preview["surface_payload"]["staged_insert"]["last_preview"]["proposed_inserted_rows"][0]["datum_address"],
                "4-2-3",
            )

    def test_preview_apply_uses_wider_template_when_local_title_capacity_is_too_small(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "authority.sqlite3"
            self._seed_document(db_file, _document_with_narrow_local_template())
            staged = run_portal_cts_gis_action(
                self._request(
                    {
                        "selected_node_id": "3-2-3-17-77-1-6-999",
                        "source": {"attention_document_id": "sandbox:cts_gis:sc.narrow.json"},
                    },
                    "stage_insert_yaml",
                    {
                        "stage_document": {
                            "schema": "mycite.v2.cts_gis.stage_insert.v1",
                            "document_id": "sandbox:cts_gis:sc.narrow.json",
                            "document_name": "sc.narrow.json",
                            "operation": "insert_datums",
                            "datums": [
                                {
                                    "family": "administrative_street",
                                    "valueGroup": 2,
                                    "targetNodeAddress": "3-2-3-17-77-1-6-999",
                                    "title": "EAST BOSTON MILLS ROAD",
                                    "references": [
                                        {"type": "title", "text": "EAST BOSTON MILLS ROAD"},
                                        {"type": "msn-samras", "nodeAddress": "3-2-3-17-77-1-6-999"},
                                    ],
                                }
                            ],
                        }
                    },
                ),
                data_dir=None,
                authority_db_file=db_file,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            preview = run_portal_cts_gis_action(
                self._request(staged["surface_payload"]["tool_state"], "preview_apply", {}),
                data_dir=None,
                authority_db_file=db_file,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            self.assertEqual(preview["surface_payload"]["action_result"]["status"], "accepted")
            inserted = preview["surface_payload"]["staged_insert"]["last_preview"][
                "proposed_inserted_rows"
            ][0]
            self.assertEqual(inserted["datum_address"], "4-2-3")
            self.assertEqual(len(inserted["raw"][0][4]), 256)

    def test_preview_apply_allows_append_on_sparse_family(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "authority.sqlite3"
            self._seed_document(db_file, _document_with_sparse_family())
            staged = run_portal_cts_gis_action(
                self._request(
                    {
                        "selected_node_id": "3-2-3-17-77-1-6-999",
                        "source": {"attention_document_id": "sandbox:cts_gis:sc.sparse.json"},
                    },
                    "stage_insert_yaml",
                    {
                        "stage_document": {
                            "schema": "mycite.v2.cts_gis.stage_insert.v1",
                            "document_id": "sandbox:cts_gis:sc.sparse.json",
                            "document_name": "sc.sparse.json",
                            "operation": "insert_datums",
                            "datums": [
                                {
                                    "family": "administrative_street",
                                    "valueGroup": 2,
                                    "targetNodeAddress": "3-2-3-17-77-1-6-999",
                                    "title": "SPARSE APPEND ROAD",
                                    "references": [
                                        {"type": "title", "text": "SPARSE APPEND ROAD"},
                                        {"type": "msn-samras", "nodeAddress": "3-2-3-17-77-1-6-999"},
                                    ],
                                }
                            ],
                        }
                    },
                ),
                data_dir=None,
                authority_db_file=db_file,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            preview = run_portal_cts_gis_action(
                self._request(staged["surface_payload"]["tool_state"], "preview_apply", {}),
                data_dir=None,
                authority_db_file=db_file,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            self.assertEqual(preview["surface_payload"]["action_result"]["status"], "accepted")
            inserted = preview["surface_payload"]["staged_insert"]["last_preview"][
                "proposed_inserted_rows"
            ][0]
            self.assertEqual(inserted["datum_address"], "4-2-4")

    def test_stage_preview_apply_and_discard_flow_round_trips_through_runtime(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "authority.sqlite3"
            canonical_id = self._seed_db_canonical(db_file)
            canonical_tool_state = {
                "selected_node_id": "3-2-3-17-77-1",
                "source": {"attention_document_id": canonical_id},
            }

            staged = run_portal_cts_gis_action(
                self._request(canonical_tool_state, "stage_insert_yaml", {"stage_document": self._stage_document(canonical_id)}),
                data_dir=None,
                authority_db_file=db_file,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            self.assertEqual(staged["entrypoint_id"], "portal.system.tools.cts_gis.actions")
            self.assertEqual(staged["surface_payload"]["action_result"]["status"], "accepted")
            self.assertEqual(
                staged["shell_composition"]["regions"]["interface_panel"]["interface_body"]["staging_widget"]["document_id"],
                canonical_id,
            )
            self.assertIn(
                "Validate Stage",
                [item["label"] for item in staged["shell_composition"]["regions"]["control_panel"]["actions"]],
            )
            self.assertEqual(
                staged["surface_payload"]["staged_insert"]["compiled_nimm_envelope"]["schema"],
                "mycite.v2.nimm.envelope.v1",
            )
            self.assertEqual(
                staged["shell_composition"]["regions"]["interface_panel"]["interface_body"]["staging_widget"]["compiled_nimm_envelope"][
                    "schema"
                ],
                "mycite.v2.nimm.envelope.v1",
            )

            preview = run_portal_cts_gis_action(
                self._request(
                    staged["surface_payload"]["tool_state"],
                    "preview_apply",
                    {},
                ),
                data_dir=None,
                authority_db_file=db_file,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            self.assertTrue(preview["shell_composition"]["regions"]["workbench"]["visible"])
            self.assertEqual(
                preview["surface_payload"]["staged_insert"]["last_preview"]["proposed_inserted_rows"][0]["datum_address"],
                "4-2-2",
            )
            self.assertEqual(
                preview["surface_payload"]["nimm_envelope"]["schema"],
                "mycite.v2.nimm.envelope.v1",
            )

            applied = run_portal_cts_gis_action(
                self._request(
                    preview["surface_payload"]["tool_state"],
                    "apply_stage",
                    {},
                ),
                data_dir=None,
                authority_db_file=db_file,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            self.assertEqual(applied["surface_payload"]["action_result"]["action_kind"], "apply_stage")
            self.assertEqual(
                applied["surface_payload"]["action_result"]["details"]["persisted_version_hash"][:7],
                "sha256:",
            )
            self.assertEqual(
                applied["surface_payload"]["tool_state"]["staged_insert"]["normalized_payload"],
                {},
            )

            discarded = run_portal_cts_gis_action(
                self._request(
                    staged["surface_payload"]["tool_state"],
                    "discard_stage",
                    {},
                ),
                data_dir=None,
                authority_db_file=db_file,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            self.assertEqual(discarded["surface_payload"]["action_result"]["action_kind"], "discard_stage")
            self.assertEqual(discarded["surface_payload"]["tool_state"]["staged_insert"]["normalized_payload"], {})

            audit_records = SqliteAuditLogAdapter(db_file).read_recent_audit_records(
                AuditLogRecentWindowRequest(limit=20)
            )
            event_types = [record.record.get("event_type") for record in audit_records.records]
            self.assertIn("portal.cts_gis.stage_insert_yaml.accepted", event_types)
            self.assertIn("portal.cts_gis.apply_stage.accepted", event_types)
            self.assertIn("portal.cts_gis.discard_stage.accepted", event_types)

    def test_select_district_row_records_district_into_tool_state_selection(self) -> None:
        """Garland cascade Phase 2: select_district_row must persist its
        row_address payload into tool_state.selection.selected_district_id
        (a dedicated field that survives mediation untouched — unlike
        selected_row_address which the finalize step rewrites to a render
        row). The handler must also clear any prior selected_feature_id so
        a new district selection doesn't carry a stale precinct highlight."""
        with TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "authority.sqlite3"
            self._seed_db(db_file)

            # Tool state seeded with a stale precinct selection to assert the
            # handler clears it on district selection.
            seed_state = {
                "selected_node_id": "3-2-3-17",
                "active_path": ["3", "3-2", "3-2-3", "3-2-3-17"],
                "aitas": {"attention_node_id": "3-2-3-17", "intention_rule_id": "self", "time_directive": "current"},
                "source": {"attention_document_id": "sandbox:cts_gis:sc.example.json"},
                "selection": {
                    "selected_row_address": "",
                    "selected_feature_id": "stale-precinct-247-17-77-999",
                    "selected_district_id": "",
                    "selected_row_explicit": False,
                    "selected_feature_explicit": True,
                },
            }

            result = run_portal_cts_gis_action(
                self._request(seed_state, "select_district_row", {"row_address": "23_present-district_31"}),
                data_dir=None,
                authority_db_file=db_file,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            payload = result["surface_payload"]
            action_result = payload["action_result"]
            self.assertEqual(action_result["action_kind"], "select_district_row")
            self.assertEqual(action_result["status"], "accepted")
            self.assertEqual(
                action_result["details"]["selected_district_id"],
                "23_present-district_31",
            )

            selection = payload["tool_state"]["selection"]
            self.assertEqual(selection["selected_district_id"], "23_present-district_31")
            self.assertEqual(
                selection["selected_feature_id"],
                "",
                "select_district_row must clear any prior precinct selection",
            )
            self.assertFalse(selection["selected_feature_explicit"])

    def test_select_district_row_without_payload_is_rejected(self) -> None:
        """When the payload is missing the row_address, the handler must
        report 'rejected' so the client knows the selection didn't take.
        State is otherwise left in a consistent (cleared) shape."""
        with TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "authority.sqlite3"
            self._seed_db(db_file)
            result = run_portal_cts_gis_action(
                self._request(None, "select_district_row", {}),
                data_dir=None,
                authority_db_file=db_file,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            action_result = result["surface_payload"]["action_result"]
            self.assertEqual(action_result["status"], "rejected")
            self.assertIn("row_address", action_result["message"])

    def test_select_precinct_row_records_precinct_into_tool_state_selection(self) -> None:
        """Garland cascade Phase 4 follow-up: select_precinct_row must
        persist the precinct id into the DEDICATED
        tool_state.selection.selected_precinct_id field (NOT
        selected_feature_id, which mediation's finalize_selection owns
        and overwrites with SAMRAS-derived ids). The handler must NOT
        touch selected_feature_id or selected_row_address — those are
        mediation-owned. Accepts both `precinct_id` (canonical) and
        `feature_id` (Phase 2 compat) in the payload."""
        with TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "authority.sqlite3"
            self._seed_db(db_file)
            result = run_portal_cts_gis_action(
                self._request(
                    None,
                    "select_precinct_row",
                    {"precinct_id": "247-17-77-121"},
                ),
                data_dir=None,
                authority_db_file=db_file,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            payload = result["surface_payload"]
            action_result = payload["action_result"]
            self.assertEqual(action_result["action_kind"], "select_precinct_row")
            self.assertEqual(action_result["status"], "accepted")
            self.assertEqual(action_result["details"]["selected_precinct_id"], "247-17-77-121")

            selection = payload["tool_state"]["selection"]
            self.assertEqual(selection["selected_precinct_id"], "247-17-77-121")

    def test_select_precinct_row_accepts_feature_id_alias(self) -> None:
        """The action handler accepts the Phase 2 `feature_id` payload
        key as an alias for `precinct_id` — backwards compatibility
        for any listing rows still emitting the old shape."""
        with TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "authority.sqlite3"
            self._seed_db(db_file)
            result = run_portal_cts_gis_action(
                self._request(None, "select_precinct_row", {"feature_id": "247-17-77-121"}),
                data_dir=None,
                authority_db_file=db_file,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            selection = result["surface_payload"]["tool_state"]["selection"]
            self.assertEqual(selection["selected_precinct_id"], "247-17-77-121")

    def test_select_precinct_row_does_not_touch_mediation_owned_selection(self) -> None:
        """The new handler must NOT write to selected_feature_id or
        selected_row_address. Those fields are mediation-owned (their
        values are derived from finalize_selection on the next cycle);
        overloading them was the root cause of the precinct-click
        panel reset in the Phase 4 initial deploy."""
        with TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "authority.sqlite3"
            self._seed_db(db_file)
            seed_state = {
                "selected_node_id": "3-2-3-17",
                "active_path": ["3", "3-2", "3-2-3", "3-2-3-17"],
                "aitas": {"attention_node_id": "3-2-3-17", "intention_rule_id": "self", "time_directive": "current"},
                "source": {"attention_document_id": "sandbox:cts_gis:sc.example.json"},
                "selection": {
                    "selected_row_address": "5-0-26",
                    "selected_feature_id": "prior_feature_id",
                    "selected_row_explicit": True,
                    "selected_feature_explicit": True,
                },
            }
            result = run_portal_cts_gis_action(
                self._request(seed_state, "select_precinct_row", {"precinct_id": "247-17-77-121"}),
                data_dir=None,
                authority_db_file=db_file,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            selection = result["surface_payload"]["tool_state"]["selection"]
            self.assertEqual(selection["selected_precinct_id"], "247-17-77-121")
            # selected_feature_id / selected_row_address may be rewritten
            # by mediation finalize, but the action handler itself must
            # not have changed them — they should at least carry the
            # prior values (or a downstream mediation result).
            # The KEY assertion: selected_feature_id is NOT the precinct id.
            self.assertNotEqual(selection.get("selected_feature_id"), "247-17-77-121")

    def test_canonical_mutation_lifecycle_names_are_accepted_as_cts_gis_aliases(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "authority.sqlite3"
            self._seed_db(db_file)

            staged = run_portal_cts_gis_action(
                self._request(None, "stage", {"stage_document": self._stage_document()}),
                data_dir=None,
                authority_db_file=db_file,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            action_contract = staged["surface_payload"]["request_contract"]["action_contract"]
            self.assertEqual(staged["surface_payload"]["action_result"]["action_kind"], "stage_insert_yaml")
            self.assertEqual(staged["surface_payload"]["action_result"]["mutation_lifecycle_action"], "stage")
            self.assertEqual(action_contract["compatibility_action_aliases"]["stage_insert_yaml"], "stage")
            self.assertIn("stage", action_contract["canonical_lifecycle_actions"])
            self.assertIn(
                "stage",
                staged["shell_composition"]["regions"]["interface_panel"]["interface_body"]["staging_widget"]["actions"],
            )


if __name__ == "__main__":
    unittest.main()
