from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.filesystem.network_root_read_model import FilesystemNetworkRootReadModelAdapter
from MyCiteV2.packages.ports.network_root_read_model import NetworkRootReadModelRequest


class NetworkRootReadModelTests(unittest.TestCase):
    def test_default_projection_uses_one_shell_surface_model(self) -> None:
        adapter = FilesystemNetworkRootReadModelAdapter(data_dir=None, private_dir=None)
        result = adapter.read_network_root_model(
            NetworkRootReadModelRequest(portal_tenant_id="fnd", portal_domain="fruitfulnetworkdevelopment.com")
        )
        payload = dict(result.source.payload)
        portal_instance = dict(payload["portal_instance"])
        self.assertEqual(portal_instance["surface_model"], "one_shell_portal")
        self.assertNotIn("audience", portal_instance)
        workbench = dict(payload["system_log_workbench"])
        self.assertEqual(workbench["active_filters"]["view"], "system_logs")
        self.assertEqual(workbench["state"], "not_configured")

    def test_unknown_surface_query_keys_are_ignored_with_warnings(self) -> None:
        adapter = FilesystemNetworkRootReadModelAdapter(data_dir=None, private_dir=None)
        result = adapter.read_network_root_model(
            NetworkRootReadModelRequest(
                portal_tenant_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
                surface_query={"view": "system_logs", "unexpected": "value"},
            )
        )

        payload = dict(result.source.payload)
        warnings = list(payload["warnings"])
        self.assertTrue(any("unsupported NETWORK surface_query" in warning for warning in warnings))


if __name__ == "__main__":
    unittest.main()
