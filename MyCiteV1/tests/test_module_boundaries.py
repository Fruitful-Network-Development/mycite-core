from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest import mock


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _add_repo_paths() -> Path:
    repo_root = _repo_root()
    for path in (repo_root, repo_root / "instances", repo_root / "packages"):
        token = str(path)
        if token not in sys.path:
            sys.path.insert(0, token)
    return repo_root


def _load_portal_build_module():
    _add_repo_paths()
    path = _repo_root() / "instances" / "scripts" / "portal_build.py"
    spec = importlib.util.spec_from_file_location("portal_build_boundary_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ModuleBoundaryTests(unittest.TestCase):
    def test_runtime_paths_wrapper_points_to_canonical_module(self):
        _add_repo_paths()
        legacy = importlib.import_module("_shared.portal.runtime_paths")
        canonical = importlib.import_module("mycite_core.runtime_paths")
        self.assertIs(legacy.utility_tools_dir, canonical.utility_tools_dir)
        self.assertEqual(canonical.instance_state_root("fnd"), Path("/srv/mycite-state/instances/fnd"))

    def test_instance_context_wrapper_derives_canonical_state_root(self):
        _add_repo_paths()
        legacy = importlib.import_module("_shared.portal.application.runtime.instance_context")
        state_root = Path("/srv/mycite-state/instances/fnd")
        with mock.patch.dict(
            os.environ,
            {
                "PORTAL_INSTANCE_ID": "fnd",
                "PUBLIC_DIR": str(state_root / "public"),
                "PRIVATE_DIR": str(state_root / "private"),
                "DATA_DIR": str(state_root / "data"),
            },
            clear=False,
        ):
            context = legacy.build_instance_context_from_env(
                default_portals_root=_repo_root() / "instances",
                default_public_dir=state_root / "public",
                default_private_dir=state_root / "private",
                default_data_dir=state_root / "data",
                default_portal_instance_id="fnd",
                default_portal_runtime_flavor="fnd",
            )
        self.assertEqual(context.state_root, state_root)
        self.assertEqual(context.instances_root, Path("/srv/mycite-state/instances"))

    def test_shell_and_tool_runtime_wrappers_point_to_canonical_modules(self):
        _add_repo_paths()
        legacy_shell = importlib.import_module("_shared.portal.application.shell.tools")
        canonical_shell = importlib.import_module("mycite_core.state_machine.tool_capabilities")
        legacy_runtime = importlib.import_module("_shared.portal.tools.runtime")
        canonical_runtime = importlib.import_module("tools._shared.tool_state_api.runtime")
        self.assertIs(legacy_shell.normalize_tool_capability, canonical_shell.normalize_tool_capability)
        self.assertIs(legacy_runtime.read_enabled_tools, canonical_runtime.read_enabled_tools)
        self.assertIs(legacy_runtime._discover_sandbox_icon_url, canonical_runtime._discover_sandbox_icon_url)

    def test_tool_state_adapters_are_instance_scoped(self):
        _add_repo_paths()
        analytics_paths = importlib.import_module("tools.analytics.state_adapter.paths")
        aws_paths = importlib.import_module("tools.aws_csm.state_adapter.paths")
        paypal_paths = importlib.import_module("tools.paypal_csm.state_adapter.paths")
        private_dir = Path("/srv/mycite-state/instances/fnd/private")
        self.assertEqual(analytics_paths.analytics_state_root(private_dir), private_dir / "utilities" / "tools" / "fnd-ebi")
        self.assertEqual(aws_paths.aws_csm_state_root(private_dir), private_dir / "utilities" / "tools" / "aws-csm")
        self.assertEqual(paypal_paths.paypal_csm_tenants_dir(private_dir), private_dir / "utilities" / "tools" / "paypal-csm" / "tenants")

    def test_portal_build_defaults_come_from_instance_declarations(self):
        module = _load_portal_build_module()
        self.assertEqual(module._state_root_for("mycite-le_fnd"), Path("/srv/mycite-state/instances/fnd"))
        self.assertEqual(module._portal_instance_id_for("mycite-le_tff"), "tff")
        self.assertEqual(module._runtime_flavor_for("mycite-le_fnd"), "fnd")


if __name__ == "__main__":
    unittest.main()
