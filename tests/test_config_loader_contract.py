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
            references = payload.get("references") if isinstance(payload.get("references"), list) else []
            self.assertEqual(len(references), 1)
            self.assertEqual(references[0].get("name"), "msn")
            self.assertEqual(references[0].get("mss_form"), "ref.a.msn.json")
            self.assertEqual(references[0].get("title"), "ref.a.msn")
            self.assertEqual(references[0].get("source_msn_id"), "a")
            self.assertNotIn("refferences", payload)

    def test_reference_normalization_prefers_provider_from_contract(self):
        mod = _load_config_loader_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            (private_dir / "config.json").write_text(
                json.dumps(
                    {
                        "msn_id": "3-2-3-17-77-2-6-3-1-6",
                        "references": [
                            {
                                "managing_contract": "contract.3-2-3-17-77-1-6-4-1-4.3-2-3-17-77-2-6-3-1-6.json",
                                "title": "ref.3-2-3-17-77-2-6-3-1-6.msn",
                                "mss_form": "ref.3-2-3-17-77-2-6-3-1-6.msn.json",
                                "name": "msn",
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            payload = mod.load_active_private_config(private_dir, "3-2-3-17-77-2-6-3-1-6")
            references = payload.get("references") if isinstance(payload.get("references"), list) else []
            self.assertEqual(len(references), 1)
            self.assertEqual(references[0].get("source_msn_id"), "3-2-3-17-77-1-6-4-1-4")
            self.assertEqual(references[0].get("mss_form"), "ref.3-2-3-17-77-1-6-4-1-4.msn.json")
            self.assertEqual(references[0].get("legacy_mss_form"), "ref.3-2-3-17-77-2-6-3-1-6.msn.json")


if __name__ == "__main__":
    unittest.main()
