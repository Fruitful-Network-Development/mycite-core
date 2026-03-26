from __future__ import annotations

import importlib
import json
import os
import sys
import unittest
from datetime import datetime, timezone
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
        meta = module.build_service_tool_meta("fnd_ebi")
        self.assertTrue(meta.get("config_context_support"))
        self.assertEqual(
            ((meta.get("inspector_card_contribution") or {}).get("config_context_route")),
            "/portal/api/data/system/config_context/fnd_ebi",
        )
        self.assertEqual(
            ((meta.get("workbench_contribution") or {}).get("default_mode")),
            "overview",
        )
        self.assertEqual(meta.get("surface_mode"), "mediation_only")
        self.assertFalse(meta.get("owns_shell_state"))
        self.assertEqual(((meta.get("service_contract") or {}).get("mediation_host_path")), "/portal/system")
        self.assertEqual(((meta.get("service_contract") or {}).get("config_datum") or {}).get("content_kind"), "json")
        self.assertIn(
            "tool.*.fnd-ebi.json",
            (((meta.get("service_contract") or {}).get("config_datum") or {}).get("patterns") or []),
        )
        self.assertEqual(
            ((meta.get("service_contract") or {}).get("collection_view_contract") or {}).get("default_mode"),
            "overview",
        )
        self.assertEqual(
            ((meta.get("service_contract") or {}).get("internal_source_contract") or {}).get("mode"),
            "read_only",
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
            client_root = Path(temp_dir) / "clients" / "fruitfulnetworkdevelopment.com"
            frontend_root = client_root / "frontend"
            analytics_root = client_root / "analytics"
            (analytics_root / "nginx").mkdir(parents=True, exist_ok=True)
            (analytics_root / "events").mkdir(parents=True, exist_ok=True)
            frontend_root.mkdir(parents=True, exist_ok=True)
            (analytics_root / "nginx" / "access.log").write_text(
                '127.0.0.1 - - [24/Mar/2026:00:00:01 +0000] "GET / HTTP/1.1" 200 123\n',
                encoding="utf-8",
            )
            (analytics_root / "nginx" / "error.log").write_text(
                "[error] 1#1: *1 upstream timed out\n",
                encoding="utf-8",
            )
            (root / "web-analytics.json").write_text(
                json.dumps({"1-0-1": [["1-0-1", "[]", "[\"[]\"]"], ["fnd-ebi.fnd.json"]]}) + "\n",
                encoding="utf-8",
            )
            (root / "fnd-ebi.fnd.json").write_text(
                json.dumps(
                    {
                        "domain": "fruitfulnetworkdevelopment.com",
                        "site_root": str(frontend_root),
                        "analytics": {"enabled": True},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            previous_roots = os.environ.get("MYCITE_INTERNAL_FILE_ROOTS")
            os.environ["MYCITE_INTERNAL_FILE_ROOTS"] = str(client_root.parent)
            try:
                payload = module.build_service_tool_config_context(
                    "fnd_ebi",
                    private_dir=private_dir,
                    tool_tabs=[{"tool_id": "fnd_ebi", **module.build_service_tool_meta("fnd_ebi")}],
                    portal_instance_id="fnd",
                    msn_id="3-2-3",
                )
            finally:
                if previous_roots is None:
                    os.environ.pop("MYCITE_INTERNAL_FILE_ROOTS", None)
                else:
                    os.environ["MYCITE_INTERNAL_FILE_ROOTS"] = previous_roots
            self.assertTrue(payload.get("ok"))
            self.assertEqual(payload.get("tool_namespace"), "fnd-ebi")
            self.assertGreaterEqual(len(payload.get("collection_files") or []), 5)
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
            snapshots = payload.get("analytics_snapshots") or []
            self.assertEqual(len(snapshots), 1)
            self.assertEqual((snapshots[0].get("access_log") or {}).get("present"), True)
            self.assertEqual((snapshots[0].get("error_log") or {}).get("present"), True)
            self.assertIn("traffic", snapshots[0])
            self.assertIn("events_summary", snapshots[0])

    def test_fnd_ebi_legacy_events_path_is_consumed_with_warning(self):
        module = _load_service_tools_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir) / "private"
            root = private_dir / "utilities" / "tools" / "fnd-ebi"
            root.mkdir(parents=True, exist_ok=True)
            client_root = Path(temp_dir) / "clients" / "legacy-domain.test"
            frontend_root = client_root / "frontend"
            analytics_root = client_root / "analytics"
            (analytics_root / "nginx").mkdir(parents=True, exist_ok=True)
            (analytics_root / "evnts").mkdir(parents=True, exist_ok=True)
            frontend_root.mkdir(parents=True, exist_ok=True)
            (analytics_root / "nginx" / "access.log").write_text(
                '127.0.0.1 - - [24/Mar/2026:00:00:01 +0000] "GET / HTTP/1.1" 200 123 "-" "Mozilla/5.0"\n',
                encoding="utf-8",
            )
            (analytics_root / "nginx" / "error.log").write_text("", encoding="utf-8")
            month_token = datetime.now(timezone.utc).strftime("%Y-%m")
            (analytics_root / "evnts" / f"{month_token}.ndjson").write_text(
                '{"event_type":"page_view","timestamp":"2026-03-24T00:00:01Z","session_id":"s1"}\n',
                encoding="utf-8",
            )
            (root / "web-analytics.json").write_text(
                json.dumps({"1-0-1": [["1-0-1", "[]", "[\"[]\"]"], ["fnd-ebi.legacy.json"]]}) + "\n",
                encoding="utf-8",
            )
            (root / "fnd-ebi.legacy.json").write_text(
                json.dumps({"domain": "legacy-domain.test", "site_root": str(frontend_root)}) + "\n",
                encoding="utf-8",
            )
            previous_roots = os.environ.get("MYCITE_INTERNAL_FILE_ROOTS")
            os.environ["MYCITE_INTERNAL_FILE_ROOTS"] = str(client_root.parent)
            try:
                payload = module.build_service_tool_config_context(
                    "fnd_ebi",
                    private_dir=private_dir,
                    tool_tabs=[{"tool_id": "fnd_ebi", **module.build_service_tool_meta("fnd_ebi")}],
                    portal_instance_id="fnd",
                    msn_id="3-2-3",
                )
            finally:
                if previous_roots is None:
                    os.environ.pop("MYCITE_INTERNAL_FILE_ROOTS", None)
                else:
                    os.environ["MYCITE_INTERNAL_FILE_ROOTS"] = previous_roots
            snapshots = payload.get("analytics_snapshots") or []
            self.assertEqual(len(snapshots), 1)
            self.assertEqual((snapshots[0].get("events_file") or {}).get("present"), True)
            self.assertIn("using legacy events path", " ".join(list(snapshots[0].get("warnings") or [])))


if __name__ == "__main__":
    unittest.main()
