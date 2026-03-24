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
        self.assertEqual(meta.get("surface_mode"), "mediation_only")
        self.assertFalse(meta.get("owns_shell_state"))
        self.assertEqual(((meta.get("service_contract") or {}).get("mediation_host_path")), "/portal/system")
        self.assertEqual(((meta.get("service_contract") or {}).get("config_datum") or {}).get("content_kind"), "json")
        self.assertEqual(
            ((meta.get("service_contract") or {}).get("collection_view_contract") or {}).get("default_mode"),
            "profiles",
        )

    def test_service_tool_registration_has_no_shell_home(self):
        module = _load_service_tools_module()
        tool = module.build_service_tool_registration("operations", "Operations")
        self.assertEqual(tool.get("tool_id"), "operations")
        self.assertEqual(tool.get("route_prefix"), "")
        self.assertEqual(tool.get("home_path"), "")
        self.assertEqual(tool.get("surface_mode"), "mediation_only")
        self.assertFalse(tool.get("owns_shell_state"))

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
            self.assertEqual(((payload.get("config_datum") or {}).get("file_name")), "fnd-ebi.fnd.json")
            self.assertEqual(((payload.get("collection_datum") or {}).get("file_name")), "web-analytics.json")
            self.assertEqual(((payload.get("service_contract") or {}).get("schema")), "mycite.service_tool.contract.v1")
            self.assertEqual(((payload.get("activation") or {}).get("default_verb")), "mediate")
            self.assertEqual(((payload.get("activation") or {}).get("host_path")), "/portal/system")
            self.assertEqual(
                ((payload.get("activation") or {}).get("request_payload") or {}).get("shell_verb"),
                "mediate",
            )
            self.assertTrue(any(str(item.get("title") or "") == "fruitfulnetworkdevelopment.com" for item in payload.get("profile_cards") or []))


if __name__ == "__main__":
    unittest.main()
