from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.filesystem import FilesystemNetworkRootReadModelAdapter
from MyCiteV2.packages.ports.network_root_read_model import NetworkRootReadModelRequest


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


class FilesystemNetworkRootReadModelAdapterTests(unittest.TestCase):
    def test_reads_hosted_alias_contract_and_request_log_state(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            private_dir = root / "private"
            _write_json(
                private_dir / "config.json",
                {
                    "msn_id": "3-2-3-17-77-1-6-4-1-4",
                    "hosted": {"hosting_type": "subject_congregation"},
                },
            )
            _write_json(
                private_dir / "network" / "hosted.json",
                {
                    "type": "subject_congregation",
                    "aws": {"email_transport_mode": "forwarder_only"},
                    "workflow": {"analytics_provider": "nginx_hosted"},
                    "broadcaster": {"enabled": True},
                    "subject_congregation": {
                        "hero_title": "Member Orientation",
                        "tabs": [
                            {"id": "stream", "label": "Stream"},
                            {"id": "workflow", "label": "Workflow"},
                        ],
                    },
                    "type_values": {
                        "default_hosted": [{"stream": "classroom/stream.json"}],
                        "channels": ["contracts.json", "request_log.json"],
                        "orientation": {"hero_title": "Member Orientation"},
                    },
                },
            )
            _write_json(
                private_dir / "network" / "aliases" / "alias-fnd-tff-member.json",
                {
                    "host_title": "trapp_family_farm",
                    "contract_id": "contract-fnd-tff-member-001",
                    "progeny_type": "member",
                    "status": "active",
                },
            )
            _write_json(
                private_dir / "network" / "progeny" / "msn-fnd.member-tff.json",
                {
                    "profile_type": "member",
                    "msn_id": "3-2-3-17-77-2-6-3-1-6",
                    "title": "trapp_family_farm",
                    "contract": {
                        "contract_id": "contract-fnd-tff-member-001",
                        "counterparty_msn_id": "3-2-3-17-77-2-6-3-1-6",
                        "status": "pending",
                    },
                },
            )
            _write_json(
                private_dir / "contracts" / "contract-fnd-tff-member-001.json",
                {
                    "contract_id": "contract-fnd-tff-member-001",
                    "contract_type": "portal_data_exchange",
                    "counterparty_msn_id": "3-2-3-17-77-2-6-3-1-6",
                    "status": "pending",
                    "tracked_resource_ids": ["rc.1"],
                },
            )
            (private_dir / "network" / "request_log").mkdir(parents=True, exist_ok=True)
            (private_dir / "network" / "request_log" / "request_log.ndjson").write_text(
                json.dumps(
                    {
                        "type": "contract_proposal.confirmed",
                        "status": "ok",
                        "receiver": "msn-3-2-3-17-77-2-6-3-1-6",
                        "ts_unix_ms": 1774822828451,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            admin_audit = private_dir / "local_audit" / "v2_admin_native.ndjson"
            admin_audit.parent.mkdir(parents=True, exist_ok=True)
            admin_audit.write_text('{"event":"admin.network.viewed"}\n', encoding="utf-8")

            result = FilesystemNetworkRootReadModelAdapter(
                private_dir=private_dir,
                local_audit_file=admin_audit,
            ).read_network_root_model(
                NetworkRootReadModelRequest(
                    portal_tenant_id="fnd",
                    portal_domain="fruitfulnetworkdevelopment.com",
                )
            )

            payload = result.source.payload
            self.assertEqual(payload["portal_instance"]["portal_instance_id"], "fnd")
            self.assertEqual(payload["portal_instance"]["domain"], "fruitfulnetworkdevelopment.com")
            self.assertEqual(len(payload["host_aliases"]), 1)
            self.assertEqual(payload["host_aliases"][0]["projection_state"], "active")
            self.assertEqual(len(payload["progeny_links"]), 1)
            self.assertEqual(payload["progeny_links"][0]["contract_state"], "pending")
            self.assertEqual(len(payload["p2p_contracts"]), 1)
            self.assertEqual(payload["p2p_contracts"][0]["evidence_state"], "request_log_present")
            self.assertEqual(len(payload["external_service_bindings"]), 4)
            self.assertEqual(payload["request_log_summary"]["event_count"], 1)
            self.assertEqual(payload["request_log_summary"]["counterparties"][0]["counterparty"], "3-2-3-17-77-2-6-3-1-6")
            self.assertEqual(payload["local_audit_summary"]["line_count"], 1)
            self.assertEqual(payload["hosted_manifest_summary"]["subject_tabs"], ["Stream", "Workflow"])


if __name__ == "__main__":
    unittest.main()
