from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import run_portal_cts_gis_action
from MyCiteV2.packages.adapters.sql import SqliteAuditLogAdapter, SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.ports.audit_log import AuditLogRecentWindowRequest
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentCatalogResult,
    AuthoritativeDatumDocumentRow,
)


def _ascii_bits(value: str, *, width: int = 256) -> str:
    bitstream = "".join(format(ord(char), "08b") for char in value)
    return bitstream.ljust(width, "0")


def _row(datum_address: str, node_address: str, title: str) -> AuthoritativeDatumDocumentRow:
    return AuthoritativeDatumDocumentRow(
        datum_address=datum_address,
        raw=[
            [datum_address, "rf.3-1-2", node_address, "rf.3-1-3", _ascii_bits(title)],
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


class PortalCtsGisActionRuntimeTests(unittest.TestCase):
    def _stage_document(self) -> dict[str, object]:
        return {
            "schema": "mycite.v2.cts_gis.stage_insert.v1",
            "document_id": "sandbox:cts_gis:sc.example.json",
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
        SqliteSystemDatumStoreAdapter(db_file).store_authoritative_catalog(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(_document(),),
                source_files={"sandbox/cts-gis/sources/sc.example.json": {"exists": True}},
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

    def test_stage_preview_apply_and_discard_flow_round_trips_through_runtime(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "authority.sqlite3"
            self._seed_db(db_file)

            staged = run_portal_cts_gis_action(
                self._request(None, "stage_insert_yaml", {"stage_document": self._stage_document()}),
                data_dir=None,
                authority_db_file=db_file,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            self.assertEqual(staged["entrypoint_id"], "portal.system.tools.cts_gis.actions")
            self.assertEqual(staged["surface_payload"]["action_result"]["status"], "accepted")
            self.assertEqual(
                staged["shell_composition"]["regions"]["interface_panel"]["interface_body"]["staging_widget"]["document_id"],
                "sandbox:cts_gis:sc.example.json",
            )
            self.assertIn(
                "Validate Stage",
                [item["label"] for item in staged["shell_composition"]["regions"]["control_panel"]["actions"]],
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
                preview["shell_composition"]["regions"]["workbench"]["surface_payload"]["stage_preview"]["proposed_inserted_rows"][0]["datum_address"],
                "4-2-2",
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


if __name__ == "__main__":
    unittest.main()
