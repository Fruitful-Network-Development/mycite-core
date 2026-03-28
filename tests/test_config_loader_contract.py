from __future__ import annotations

import importlib
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def _load_config_loader_module():
    portals_root = Path(__file__).resolve().parents[1] / "portals"
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return importlib.import_module("_shared.portal.core_services.config_loader")


class ConfigLoaderContractTests(unittest.TestCase):
    def test_load_active_private_config_normalizes_tools_configuration(self):
        mod = _load_config_loader_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            (private_dir / "config.json").write_text(
                json.dumps(
                    {
                        "msn_id": "3-2-3",
                        "tools_configuration": [
                            {"tool_id": "AGRO_ERP", "status": "ENABLED", "mount_target": "Peripherals.Tools"},
                            {"name": "fnd-ebi"},
                            {"id": "fnd-ebi"},
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            payload = mod.load_active_private_config(private_dir, "3-2-3")
            tools_cfg = payload.get("tools_configuration") if isinstance(payload.get("tools_configuration"), list) else []
            self.assertEqual(len(tools_cfg), 2)
            self.assertEqual(tools_cfg[0].get("name"), "agro_erp")
            self.assertEqual(tools_cfg[0].get("status"), "enabled")
            self.assertEqual(tools_cfg[0].get("mount_target"), "peripherals.tools")
            self.assertEqual(tools_cfg[1].get("name"), "fnd-ebi")
            self.assertEqual(tools_cfg[1].get("status"), "enabled")

    def test_load_active_private_config_backfills_references_from_refferences(self):
        mod = _load_config_loader_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            expected = [{"name": "msn", "mss_form": "ref.a.msn.json"}]
            (private_dir / "config.json").write_text(
                json.dumps({"msn_id": "3-2-3", "refferences": expected}) + "\n",
                encoding="utf-8",
            )
            payload = mod.load_active_private_config(private_dir, "3-2-3")
            self.assertEqual(payload.get("refferences"), expected)
            self.assertEqual(payload.get("references"), expected)


if __name__ == "__main__":
    unittest.main()
