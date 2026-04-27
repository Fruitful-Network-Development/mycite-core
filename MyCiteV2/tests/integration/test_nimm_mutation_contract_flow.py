from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import run_portal_cts_gis, run_portal_cts_gis_action
from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
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


class NimmMutationContractIntegrationTests(unittest.TestCase):
    def _seed_db(self, db_file: Path) -> None:
        SqliteSystemDatumStoreAdapter(db_file).store_authoritative_catalog(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(_document(),),
                source_files={"sandbox/cts-gis/sources/sc.example.json": {"exists": True}},
                readiness_status={"authoritative_catalog": "loaded"},
            )
        )

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

    def _action_request(self, tool_state: dict[str, object] | None, action_kind: str, action_payload: dict[str, object]) -> dict[str, object]:
        return {
            "schema": "mycite.v2.portal.system.tools.cts_gis.action.request.v1",
            "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
            "runtime_mode": "audit_forensic",
            "tool_state": tool_state
            or {
                "selected_node_id": "3-2-3-17-77-1",
                "source": {"attention_document_id": "sandbox:cts_gis:sc.example.json"},
            },
            "action_kind": action_kind,
            "action_payload": action_payload,
        }

    def _seed_data_dir(self, data_dir: Path) -> None:
        (data_dir / "sandbox" / "cts-gis" / "sources" / "precincts").mkdir(parents=True, exist_ok=True)
        payload = {
            "datum_addressing_abstraction_space": {
                "4-2-1": _row("4-2-1", "3-2-3-17-77-1", "ALPHA STREET").raw,
                "4-2-2": _row("4-2-2", "3-2-3-17-77-2", "BETA STREET").raw,
                "4-2-3": _row("4-2-3", "3-2-3-17-77-2", "GAMMA STREET").raw,
            }
        }
        (data_dir / "sandbox" / "cts-gis" / "sources" / "sc.example.json").write_text(
            json.dumps(payload) + "\n",
            encoding="utf-8",
        )

    def test_stage_preview_apply_clears_stage_and_updates_authoritative_rows(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            db_file = Path(temp_dir) / "authority.sqlite3"
            self._seed_db(db_file)
            self._seed_data_dir(data_dir)

            staged = run_portal_cts_gis_action(
                self._action_request(None, "stage_insert_yaml", {"stage_document": self._stage_document()}),
                data_dir=data_dir,
                authority_db_file=db_file,
            )
            staged_tool_state = staged["surface_payload"]["tool_state"]
            self.assertEqual(
                staged["surface_payload"]["nimm_envelope"]["schema"],
                "mycite.v2.nimm.envelope.v1",
            )
            self.assertIn(
                "Validate Stage",
                [item["label"] for item in staged["shell_composition"]["regions"]["control_panel"]["actions"]],
            )

            preview = run_portal_cts_gis_action(
                self._action_request(staged_tool_state, "preview_apply", {}),
                data_dir=data_dir,
                authority_db_file=db_file,
            )
            self.assertTrue(preview["shell_composition"]["regions"]["workbench"]["visible"])
            self.assertEqual(
                preview["shell_composition"]["regions"]["workbench"]["surface_payload"]["stage_preview"]["proposed_inserted_rows"][0][
                    "datum_address"
                ],
                "4-2-2",
            )

            applied = run_portal_cts_gis_action(
                self._action_request(preview["surface_payload"]["tool_state"], "apply_stage", {}),
                data_dir=data_dir,
                authority_db_file=db_file,
            )
            self.assertEqual(applied["surface_payload"]["action_result"]["status"], "accepted")
            self.assertEqual(
                applied["surface_payload"]["tool_state"]["staged_insert"]["normalized_payload"],
                {},
            )

            store = SqliteSystemDatumStoreAdapter(db_file)
            catalog = store.read_authoritative_datum_documents({"tenant_id": "fnd"})
            self.assertEqual(catalog.documents[0].row_count, 4)

    def test_navigation_request_keeps_cts_gis_state_runtime_owned(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "authority.sqlite3"
            self._seed_db(db_file)
            envelope = run_portal_cts_gis(
                {
                    "schema": "mycite.v2.portal.system.tools.cts_gis.request.v1",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                    "selected_document_id": "sandbox:cts_gis:sc.example.json",
                    "tool_state": {
                        "selected_node_id": "3-2-3-17-77-1",
                        "aitas": {"intention_rule_id": "self"},
                    },
                },
                data_dir=None,
                authority_db_file=db_file,
            )
            self.assertEqual(envelope["surface_payload"]["request_contract"]["schema"], "mycite.v2.portal.system.tools.cts_gis.request.v1")
            self.assertIn("action_contract", envelope["surface_payload"]["request_contract"])
            self.assertIn("navigation_canvas", envelope["shell_composition"]["regions"]["interface_panel"]["interface_body"])


if __name__ == "__main__":
    unittest.main()
