from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.modules.cross_domain.network_root import NetworkRootReadModelService
from MyCiteV2.packages.ports.network_root_read_model import (
    NetworkRootReadModelResult,
    NetworkRootReadModelSource,
)


class _FakeNetworkRootPort:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.requests = []

    def read_network_root_model(self, request):
        self.requests.append(request)
        return NetworkRootReadModelResult(source=NetworkRootReadModelSource(payload=self.payload))


class NetworkRootReadModelUnitTests(unittest.TestCase):
    def test_service_builds_contract_first_tab_panels(self) -> None:
        payload = {
            "portal_instance": {
                "portal_instance_id": "fnd",
                "domain": "fruitfulnetworkdevelopment.com",
                "audience": "trusted_tenant_plus_internal_admin",
                "runtime_flavor": "v2_native",
                "deployment_state": "live_state_present",
                "msn_id": "3-2-3-17-77-1-6-4-1-4",
            },
            "host_aliases": [
                {
                    "host_alias_id": "alias-fnd-tff-member",
                    "alias_kind": "member_alias",
                    "projection_state": "active",
                    "host_title": "trapp_family_farm",
                    "contract_id": "contract-fnd-tff-member-001",
                }
            ],
            "progeny_links": [
                {
                    "progeny_link_id": "msn-fnd.member-tff",
                    "relationship_kind": "member",
                    "contract_state": "pending",
                    "target_portal_instance_id": "3-2-3-17-77-2-6-3-1-6",
                }
            ],
            "p2p_contracts": [
                {
                    "p2p_contract_id": "contract-fnd-tff-member-001",
                    "relationship_kind": "portal_data_exchange",
                    "enforcement_state": "pending",
                    "counterparty_msn_id": "3-2-3-17-77-2-6-3-1-6",
                    "evidence_state": "request_log_present",
                }
            ],
            "external_service_bindings": [
                {
                    "binding_id": "fnd.aws",
                    "binding_family": "aws_mail_transport",
                    "provider_kind": "aws",
                    "binding_state": "forwarder_only",
                }
            ],
            "profile_projections": [
                {
                    "projection_id": "alias-fnd-tff-member",
                    "projection_kind": "host_alias_projection",
                    "state": "active",
                    "title": "trapp_family_farm",
                    "contract_ref": "contract-fnd-tff-member-001",
                }
            ],
            "request_log_summary": {
                "state": "ready",
                "request_log_dir": "/tmp/request_log",
                "external_event_dir": "/tmp/external_events",
                "file_count": 1,
                "event_count": 3,
                "latest_event_at": "2026-04-13T10:00:00Z",
                "top_event_types": [{"type": "contract_proposal", "count": 2}],
                "counterparties": [{"counterparty": "3-2-3-17-77-2-6-3-1-6", "count": 3}],
                "recent_events": [
                    {
                        "timestamp": "2026-04-13T10:00:00Z",
                        "type": "contract_proposal.confirmed",
                        "status": "ok",
                        "counterparty": "3-2-3-17-77-2-6-3-1-6",
                    }
                ],
            },
            "local_audit_summary": {
                "path": "/tmp/admin.ndjson",
                "state": "present",
                "line_count": 2,
            },
            "hosted_manifest_summary": {
                "layout": "subject_congregation",
                "orientation_title": "Member Orientation",
                "subject_tabs": ["Stream", "Workflow"],
                "default_hosted_count": 1,
                "channel_count": 2,
            },
            "warnings": [],
        }
        service = NetworkRootReadModelService(_FakeNetworkRootPort(payload))

        result = service.read_surface(
            portal_tenant_id="fnd",
            portal_domain="fruitfulnetworkdevelopment.com",
        )

        self.assertEqual(result["network_state"], "contract_first_read_model")
        self.assertEqual(result["summary"]["host_alias_count"], 1)
        self.assertEqual(result["summary"]["request_log_event_count"], 3)
        self.assertEqual(result["tab_panels"]["hosted"]["sections"][0]["facts"][0]["label"], "portal_instance_id")
        self.assertEqual(result["tab_panels"]["messages"]["sections"][1]["rows"][0]["type"], "contract_proposal")
        self.assertEqual(result["tab_panels"]["profile"]["sections"][1]["entries"][0]["label"], "Stream")
        self.assertEqual(result["tab_panels"]["contracts"]["sections"][2]["facts"][3]["value"], "present")


if __name__ == "__main__":
    unittest.main()
