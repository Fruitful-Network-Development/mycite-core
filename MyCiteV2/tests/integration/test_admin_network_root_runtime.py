from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.admin_runtime import run_admin_shell_entry
from MyCiteV2.packages.state_machine.hanus_shell import (
    ADMIN_NETWORK_ROOT_SLICE_ID,
    ADMIN_SHELL_REQUEST_SCHEMA,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


class AdminNetworkRootRuntimeIntegrationTests(unittest.TestCase):
    def test_network_root_reads_hosted_entity_model_from_private_state(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            private_dir = root / "private"
            admin_audit = private_dir / "local_audit" / "v2_admin_native.ndjson"

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
            admin_audit.parent.mkdir(parents=True, exist_ok=True)
            admin_audit.write_text('{"event":"admin.network.viewed"}\n', encoding="utf-8")

            result = run_admin_shell_entry(
                {
                    "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                    "requested_slice_id": ADMIN_NETWORK_ROOT_SLICE_ID,
                    "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
                    "root_tab": "hosted",
                },
                audit_storage_file=admin_audit,
                portal_tenant_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
                private_dir=private_dir,
            )

            self.assertEqual(result["slice_id"], ADMIN_NETWORK_ROOT_SLICE_ID)
            self.assertEqual(result["surface_payload"]["network_state"], "contract_first_read_model")
            self.assertEqual(result["surface_payload"]["summary"]["host_alias_count"], 1)
            self.assertEqual(result["surface_payload"]["summary"]["contract_count"], 1)
            self.assertEqual(result["surface_payload"]["summary"]["request_log_event_count"], 1)
            hosted_panel = result["surface_payload"]["tab_panels"]["hosted"]
            self.assertEqual(hosted_panel["sections"][0]["facts"][0]["value"], "fnd")
            self.assertEqual(hosted_panel["sections"][1]["rows"][0]["projection_state"], "active")
            inspector = result["shell_composition"]["regions"]["inspector"]
            self.assertEqual(inspector["kind"], "network_summary")
            self.assertEqual(inspector["portal_instance"]["domain"], "fruitfulnetworkdevelopment.com")
            self.assertEqual(result["shell_composition"]["regions"]["workbench"]["subtitle"], "Portal-instance and relationship read model")


if __name__ == "__main__":
    unittest.main()
