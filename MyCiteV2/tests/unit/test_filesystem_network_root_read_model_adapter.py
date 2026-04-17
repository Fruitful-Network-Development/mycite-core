from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.filesystem.network_root_read_model import (  # noqa: E402
    FilesystemNetworkRootReadModelAdapter,
    build_system_log_document,
    rebuild_network_system_log_document,
)
from MyCiteV2.packages.ports.network_root_read_model import (  # noqa: E402
    NetworkRootReadModelRequest,
    validate_network_hops_address,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


class FilesystemNetworkRootReadModelAdapterTests(unittest.TestCase):
    def _write_chronology_authority(self, data_dir: Path) -> None:
        (data_dir / "system").mkdir(parents=True, exist_ok=True)
        _write_json(
            data_dir / "system" / "anthology.json",
            {
                "1-1-1": [
                    [
                        "1-1-1",
                        "0-0-1",
                        "00000010000110000000110011010101111000011011001100011101111001111101000111110100011111010001011011010111000111100111100",
                    ],
                    ["HOPS-chornological"],
                ]
            },
        )
        _write_json(
            data_dir / "system" / "sources" / "sc.fnd.quadrennium_cycle.json",
            {
                "datum_addressing_abstraction_space": {
                    "1-1-1": [["1-1-1", "rf.0-0-1", "00000100011100000101100100011011111101110110110101110001111001111001111101000"], ["HOPS-quadrennium_cycle"]],
                    "2-0-1": [["2-0-1", "~", "1-1-1"], ["HOPS-space-quadrennium"]],
                    "3-1-1": [["3-1-1", "2-0-1", "0"], ["HOPS-babelette-quadrennium_cycle"]],
                }
            },
        )

    def test_reads_canonical_system_log_and_transition_filters(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            private_dir = root / "private"
            self._write_chronology_authority(data_dir)
            canonical_doc = build_system_log_document(
                records=[
                    {
                        "source_key": "canonical-general",
                        "source_kind": "canonical_seed",
                        "source_timestamp": "2026-07-04T00:00:00Z",
                        "title": "americas_250th_anniversary_2026_07_04",
                        "label": "americas_250th_anniversary_2026_07_04",
                        "event_type_slug": "general_event",
                        "event_type_label": "general_event",
                        "status": "scheduled",
                        "counterparty": "",
                        "contract_id": "",
                        "hops_timestamp": "0-0-0-507-916-0-0-0",
                        "raw": {"kind": "calendar"},
                    }
                ],
                preserved_kind_labels={"general_event": "general_event"},
            )
            _write_json(data_dir / "system" / "system_log.json", canonical_doc)
            _write_json(
                private_dir / "config.json",
                {"msn_id": "3-2-3-17-77-1-6-4-1-4"},
            )
            _write_json(
                private_dir / "contracts" / "contract-fnd-tff-member-001.json",
                {
                    "contract_id": "contract-fnd-tff-member-001",
                    "contract_type": "portal_data_exchange",
                    "counterparty_msn_id": "3-2-3-17-77-2-6-3-1-6",
                    "status": "active",
                    "owner_selected_refs": ["1-1-1"],
                    "owner_mss": {"owner": "mss"},
                    "counterparty_mss": {"counterparty": "mss"},
                    "tracked_resource_ids": ["rc.1"],
                    "created_unix_ms": 1773340548126,
                    "updated_unix_ms": 1773340548126,
                },
            )
            (private_dir / "network" / "request_log").mkdir(parents=True, exist_ok=True)
            (private_dir / "network" / "request_log" / "request_log.ndjson").write_text(
                json.dumps(
                    {
                        "type": "contract_proposal.confirmed",
                        "status": "ok",
                        "receiver": "msn-3-2-3-17-77-2-6-3-1-6",
                        "contract_id": "contract-fnd-tff-member-001",
                        "ts_unix_ms": 1773340548610,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            portal_audit = private_dir / "local_audit" / "v2_portal_native.ndjson"
            portal_audit.parent.mkdir(parents=True, exist_ok=True)
            portal_audit.write_text('{"event":"portal.network.viewed"}\n', encoding="utf-8")

            adapter = FilesystemNetworkRootReadModelAdapter(
                data_dir=data_dir,
                private_dir=private_dir,
                local_audit_file=portal_audit,
            )
            initial = adapter.read_network_root_model(
                NetworkRootReadModelRequest(
                    portal_tenant_id="fnd",
                    portal_domain="fruitfulnetworkdevelopment.com",
                )
            ).source.payload

            workspace = dict(initial["system_log_workbench"])
            self.assertEqual(workspace["state"], "ready")
            self.assertEqual(workspace["summary"]["record_count"], 3)
            self.assertEqual(workspace["summary"]["contract_count"], 1)
            self.assertEqual(workspace["audit_summary"]["line_count"], 1)
            self.assertIn("general_event", [row["slug"] for row in workspace["event_type_filters"]])
            self.assertTrue(
                any(row["contract_id"] == "contract-fnd-tff-member-001" for row in workspace["contract_filters"])
            )
            self.assertTrue(
                any(row["event_type_label"] == "contract_proposal.confirmed" for row in workspace["records"])
            )
            schema_payload = {"ok": True, "schema": dict(workspace["chronology"]["schema"])}
            self.assertTrue(
                bool(validate_network_hops_address(workspace["records"][0]["hops_timestamp"], schema_payload).get("ok"))
            )

            contract_event_type_id = next(
                row["event_type_id"]
                for row in workspace["event_type_filters"]
                if row["slug"] == "contract_proposal.confirmed"
            )
            contract_filtered = adapter.read_network_root_model(
                NetworkRootReadModelRequest(
                    portal_tenant_id="fnd",
                    portal_domain="fruitfulnetworkdevelopment.com",
                    surface_query={
                        "view": "system_logs",
                        "contract": "contract-fnd-tff-member-001",
                        "type": contract_event_type_id,
                    },
                )
            ).source.payload["system_log_workbench"]
            self.assertEqual(len(contract_filtered["records"]), 1)
            self.assertEqual(contract_filtered["records"][0]["contract_id"], "contract-fnd-tff-member-001")
            record_id = contract_filtered["records"][0]["datum_address"]
            selected = adapter.read_network_root_model(
                NetworkRootReadModelRequest(
                    portal_tenant_id="fnd",
                    portal_domain="fruitfulnetworkdevelopment.com",
                    surface_query={
                        "view": "system_logs",
                        "contract": "contract-fnd-tff-member-001",
                        "type": contract_event_type_id,
                        "record": record_id,
                    },
                )
            ).source.payload["system_log_workbench"]
            self.assertEqual(selected["selected_record"]["datum_address"], record_id)
            self.assertEqual(selected["selected_contract"]["contract_id"], "contract-fnd-tff-member-001")

            warned = adapter.read_network_root_model(
                NetworkRootReadModelRequest(
                    portal_tenant_id="fnd",
                    portal_domain="fruitfulnetworkdevelopment.com",
                    surface_query={
                        "view": "system_logs",
                        "contract": "contract-fnd-tff-member-001",
                        "unused_key": "ignored",
                    },
                )
            ).source.payload["system_log_workbench"]
            self.assertTrue(any("unsupported NETWORK surface_query" in warning for warning in warned["warnings"]))

    def test_invalid_canonical_rows_are_excluded_from_workbench(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            private_dir = root / "private"
            self._write_chronology_authority(data_dir)
            _write_json(
                data_dir / "system" / "system_log.json",
                {
                    "datum_addressing_abstraction_space": {
                        "4-2-1": [["4-2-1", "ref.2-1-10", "1", "ref.3-1-4", "01100111011001010110111001100101011100100110000101101100010111110110010101110110011001010110111001110100"], ["general_event"]],
                        "5-0-1": [["5-0-1", "~", "4-2-1"], ["event_type_collection"]],
                        "6-1-1": [["6-1-1", "5-0-1", "0"], ["event_type_babelette"]],
                        "7-3-1": [["7-3-1", "4-2-1", "1", "ref.3-1-1", "4-447-751-507-916", "ref.3-1-4", "01100001011011010110010101110010011010010110001101100001"], ["legacy_invalid"]],
                    }
                },
            )
            _write_json(private_dir / "config.json", {"msn_id": "3-2-3-17-77-1-6-4-1-4"})
            adapter = FilesystemNetworkRootReadModelAdapter(
                data_dir=data_dir,
                private_dir=private_dir,
                local_audit_file=None,
            )
            payload = adapter.read_network_root_model(
                NetworkRootReadModelRequest(
                    portal_tenant_id="fnd",
                    portal_domain="fruitfulnetworkdevelopment.com",
                )
            ).source.payload
            workspace = payload["system_log_workbench"]
            self.assertEqual(workspace["records"], [])
            self.assertTrue(
                any("Ignored 1 invalid canonical system-log row" in warning for warning in workspace["warnings"])
            )

    def test_rebuild_document_imports_legacy_logs_and_drops_invalid_seed_rows(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            private_dir = root / "private"
            self._write_chronology_authority(data_dir)
            _write_json(
                data_dir / "system" / "system_log.json",
                {
                    "datum_addressing_abstraction_space": {
                        "4-2-1": [["4-2-1", "ref.2-1-10", "1", "ref.3-1-4", "01100111011001010110111001100101011100100110000101101100010111110110010101110110011001010110111001110100"], ["general_event"]],
                        "5-0-1": [["5-0-1", "~", "4-2-1"], ["event_type_collection"]],
                        "6-1-1": [["6-1-1", "5-0-1", "0"], ["event_type_babelette"]],
                        "7-3-1": [["7-3-1", "4-2-1", "1", "ref.3-1-1", "4-447-751-507-916", "ref.3-1-4", "01100001011011010110010101110010011010010110001101100001"], ["legacy_invalid"]],
                    }
                },
            )
            _write_json(private_dir / "config.json", {"msn_id": "3-2-3-17-77-1-6-4-1-4"})
            _write_json(
                private_dir / "contracts" / "contract-fnd-tff-member-001.json",
                {
                    "contract_id": "contract-fnd-tff-member-001",
                    "contract_type": "portal_data_exchange",
                    "counterparty_msn_id": "3-2-3-17-77-2-6-3-1-6",
                    "status": "active",
                    "owner_selected_refs": ["1-1-1"],
                    "owner_mss": {"owner": "mss"},
                    "counterparty_mss": {"counterparty": "mss"},
                    "created_unix_ms": 1773340548126,
                    "updated_unix_ms": 1773340548126,
                },
            )
            (private_dir / "network" / "request_log").mkdir(parents=True, exist_ok=True)
            (private_dir / "network" / "request_log" / "request_log.ndjson").write_text(
                json.dumps(
                    {
                        "type": "contract_proposal.confirmed",
                        "status": "ok",
                        "receiver": "msn-3-2-3-17-77-2-6-3-1-6",
                        "contract_id": "contract-fnd-tff-member-001",
                        "ts_unix_ms": 1773340548610,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            rebuilt = rebuild_network_system_log_document(
                data_dir=data_dir,
                private_dir=private_dir,
                portal_tenant_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )

            document = rebuilt["system_log_document"]
            space = document["datum_addressing_abstraction_space"]
            event_rows = [row for key, row in space.items() if str(key).startswith("7-3-")]
            self.assertEqual(rebuilt["record_count"], 2)
            self.assertEqual(len(event_rows), 2)
            self.assertTrue(all(row[0][4] != "4-447-751-507-916" for row in event_rows))
            self.assertTrue(
                all(bool(validate_network_hops_address(row[0][4], rebuilt["schema_payload"]).get("ok")) for row in event_rows)
            )


if __name__ == "__main__":
    unittest.main()
