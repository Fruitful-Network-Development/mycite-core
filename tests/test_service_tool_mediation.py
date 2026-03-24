from __future__ import annotations

import importlib
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def _load_service_tools_module():
    portals_root = Path(__file__).resolve().parents[1] / "portals"
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return importlib.import_module("_shared.portal.application.service_tools")


class ServiceToolMediationTests(unittest.TestCase):
    def test_service_tool_meta_exposes_shared_config_context_contract(self):
        module = _load_service_tools_module()
        meta = module.build_service_tool_meta("website_analytics")
        self.assertTrue(meta.get("config_context_support"))
        self.assertEqual(
            ((meta.get("inspector_card_contribution") or {}).get("config_context_route")),
            "/portal/api/data/system/config_context/website_analytics",
        )
        self.assertEqual(
            ((meta.get("workbench_contribution") or {}).get("default_mode")),
            "profiles",
        )

    def test_service_tool_config_context_reads_tool_owned_collections(self):
        module = _load_service_tools_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir) / "private"
            root = private_dir / "utilities" / "tools" / "fnd-ebi"
            root.mkdir(parents=True, exist_ok=True)
            (root / "web-analytics.json").write_text(
                json.dumps({"1-0-1": [["1-0-1", "[]", "[\"[]\"]"], ["fnd-ebi.fnd.json"]]}) + "\n",
                encoding="utf-8",
            )
            (root / "fnd-ebi.fnd.json").write_text(
                json.dumps({"domain": "fruitfulnetworkdevelopment.com", "analytics": {"enabled": True}}) + "\n",
                encoding="utf-8",
            )
            payload = module.build_service_tool_config_context(
                "website_analytics",
                private_dir=private_dir,
                tool_tabs=[{"tool_id": "website_analytics", **module.build_service_tool_meta("website_analytics")}],
                portal_instance_id="fnd",
                msn_id="3-2-3",
            )
            self.assertTrue(payload.get("ok"))
            self.assertEqual(payload.get("tool_namespace"), "fnd-ebi")
            self.assertEqual(len(payload.get("collection_files") or []), 2)
            self.assertTrue(any(str(item.get("title") or "") == "fruitfulnetworkdevelopment.com" for item in payload.get("profile_cards") or []))


if __name__ == "__main__":
    unittest.main()
