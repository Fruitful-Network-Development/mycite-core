from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


BRIDGE_MODULE = REPO_ROOT / "MyCiteV2" / "packages" / "adapters" / "portal_runtime" / "v1_host_bridge.py"
FND_APP = REPO_ROOT / "MyCiteV1" / "instances" / "_shared" / "runtime" / "flavors" / "fnd" / "app.py"
TFF_APP = REPO_ROOT / "MyCiteV1" / "instances" / "_shared" / "runtime" / "flavors" / "tff" / "app.py"


def _module_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


class V2DeploymentBridgeBoundaryTests(unittest.TestCase):
    def test_bridge_uses_explicit_runtime_entrypoints_without_discovery_modules(self) -> None:
        source = BRIDGE_MODULE.read_text(encoding="utf-8")
        imports = _module_imports(BRIDGE_MODULE)

        self.assertIn("MyCiteV2.instances._shared.runtime.admin_runtime", imports)
        self.assertIn("MyCiteV2.instances._shared.runtime.admin_aws_runtime", imports)
        self.assertNotIn("importlib", imports)
        self.assertNotIn("pkgutil", imports)
        self.assertNotIn("os", imports)
        self.assertNotIn("walk_packages", source)
        self.assertNotIn("glob(", source)
        self.assertNotIn("aws_platform_admin", source)
        self.assertNotIn("agro", source.lower())
        self.assertNotIn("maps", source.lower())

    def test_v1_host_mount_is_limited_to_v2_bridge_registration(self) -> None:
        for app_path in (FND_APP, TFF_APP):
            source = app_path.read_text(encoding="utf-8")
            imports = _module_imports(app_path)
            self.assertIn("MyCiteV2.packages.adapters.portal_runtime", imports)
            self.assertIn("register_v2_admin_bridge_routes", source)
            self.assertIn("V2AdminBridgeConfig", source)
            self.assertNotIn("run_admin_shell_entry", source)
            self.assertNotIn("run_admin_aws_read_only", source)
            self.assertNotIn("run_admin_aws_narrow_write", source)


if __name__ == "__main__":
    unittest.main()
