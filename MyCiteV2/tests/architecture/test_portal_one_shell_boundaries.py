from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class PortalOneShellBoundaryTests(unittest.TestCase):
    def test_retired_split_artifacts_are_absent(self) -> None:
        retired_surface_file = REPO_ROOT / "MyCiteV2" / "packages" / "state_machine" / ("trusted" + "_tenant" + "_portal.py")
        retired_runtime_file = REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / ("tenant" + "_portal_runtime.py")
        retired_shell_file = REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / ("admin" + "_runtime.py")
        retired_shell_dir = REPO_ROOT / "MyCiteV2" / "packages" / "state_machine" / ("hanus" + "_shell")
        self.assertFalse(retired_surface_file.exists())
        self.assertFalse(retired_runtime_file.exists())
        self.assertFalse(retired_shell_file.exists())
        self.assertFalse(retired_shell_dir.exists())

    def test_host_and_runtime_use_only_canonical_shell_routes(self) -> None:
        app_source = (REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "app.py").read_text(encoding="utf-8")
        runtime_source = (REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "runtime_platform.py").read_text(encoding="utf-8")
        shell_source = (REPO_ROOT / "MyCiteV2" / "packages" / "state_machine" / "portal_shell" / "shell.py").read_text(encoding="utf-8")

        self.assertIn("/portal/api/v2/shell", app_source)
        self.assertIn("/portal/system/tools/<tool_slug>", app_source)
        self.assertIn("/portal/system", shell_source)
        self.assertIn("/portal/network", shell_source)
        self.assertIn("/portal/utilities", shell_source)
        self.assertNotIn("/portal/api/v2/" + "tenant", app_source)
        self.assertNotIn("/portal/api/v2/" + "admin" + "/shell", app_source)
        self.assertNotIn("/portal/system/activity", app_source)
        self.assertNotIn("/portal/system/profile-basics", app_source)
        self.assertNotIn("trusted" + "_tenant", runtime_source)
        self.assertNotIn("admin" + " shell", shell_source.lower())

    def test_shell_contracts_enforce_workspace_and_tool_behavior(self) -> None:
        shell_source = (REPO_ROOT / "MyCiteV2" / "packages" / "state_machine" / "portal_shell" / "shell.py").read_text(encoding="utf-8")
        self.assertIn('SYSTEM_ANCHOR_FILE_KEY = "anthology"', shell_source)
        self.assertIn("TRANSITION_BACK_OUT", shell_source)
        self.assertIn("SYSTEM_SANDBOX_QUERY_FILE_TOKEN", shell_source)
        self.assertIn("default_workbench_visible: bool = False", shell_source)
        self.assertNotIn("system.activity", shell_source)
        self.assertNotIn("system.profile_basics", shell_source)


if __name__ == "__main__":
    unittest.main()
