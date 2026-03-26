from __future__ import annotations

import importlib
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def _load_tool_runtime_module():
    portals_root = Path(__file__).resolve().parents[1] / "portals"
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return importlib.import_module("_shared.portal.tools.runtime")


def _load_tool_specs_module():
    portals_root = Path(__file__).resolve().parents[1] / "portals"
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return importlib.import_module("_shared.portal.tools.specs")


class ToolRuntimeTests(unittest.TestCase):
    def test_read_enabled_tools_returns_none_without_config(self):
        runtime = _load_tool_runtime_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            self.assertIsNone(runtime.read_enabled_tools(private_dir, "3-2-3"))

    def test_read_enabled_tools_returns_empty_list_when_config_has_no_field(self):
        runtime = _load_tool_runtime_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            (private_dir / "config.json").write_text(json.dumps({"msn_id": "3-2-3"}) + "\n", encoding="utf-8")
            self.assertEqual(runtime.read_enabled_tools(private_dir, "3-2-3"), [])

    def test_read_enabled_tools_prefers_tools_configuration(self):
        runtime = _load_tool_runtime_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            (private_dir / "config.json").write_text(
                json.dumps(
                    {
                        "msn_id": "3-2-3",
                        "tools_configuration": [
                            {"tool_id": "operations", "mount_target": "utilities"},
                            {"tool_id": "fnd_ebi", "mount_target": "peripherals.tools"},
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            self.assertEqual(runtime.read_enabled_tools(private_dir, "3-2-3"), ["operations", "fnd_ebi"])

    def test_read_enabled_tools_ignores_legacy_enabled_tools(self):
        runtime = _load_tool_runtime_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            (private_dir / "config.json").write_text(
                json.dumps({"msn_id": "3-2-3", "enabled_tools": ["operations"]}) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(runtime.read_enabled_tools(private_dir, "3-2-3"), [])

    def test_read_enabled_tools_accepts_manifest_name_with_hyphen(self):
        runtime = _load_tool_runtime_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            (private_dir / "config.json").write_text(
                json.dumps(
                    {
                        "msn_id": "3-2-3",
                        "tools_configuration": [
                            {"name": "agro-erp", "mount_target": "peripherals.tools"},
                            {"name": "fnd-ebi", "mount_target": "peripherals.tools"},
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            self.assertEqual(runtime.read_enabled_tools(private_dir, "3-2-3"), ["agro_erp", "fnd_ebi"])

    def test_read_enabled_tools_filters_disabled_status(self):
        runtime = _load_tool_runtime_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            (private_dir / "config.json").write_text(
                json.dumps(
                    {
                        "msn_id": "3-2-3",
                        "tools_configuration": [
                            {"name": "agro-erp", "status": "disabled"},
                            {"name": "fnd-ebi", "status": "enabled"},
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            self.assertEqual(runtime.read_enabled_tools(private_dir, "3-2-3"), ["fnd_ebi"])

    def test_tool_spec_loader_prefers_sandbox_spec_json(self):
        specs = _load_tool_specs_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir) / "private"
            sandbox_dir = private_dir / "utilities" / "tools" / "agro-erp"
            sandbox_dir.mkdir(parents=True, exist_ok=True)
            (sandbox_dir / "spec.json").write_text(
                json.dumps(
                    {
                        "schema": "mycite.portal.tool_spec.v1",
                        "tool_id": "agro-erp",
                        "inherited_inputs": [],
                        "outputs": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            loaded = specs.load_tool_spec_for_id(private_dir, "agro_erp")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.tool_id, "agro-erp")


if __name__ == "__main__":
    unittest.main()
