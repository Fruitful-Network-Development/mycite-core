from __future__ import annotations

import ast
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

ENABLE_HISTORICAL_BRIDGE_TESTS = os.environ.get("MYCITE_ENABLE_HISTORICAL_BRIDGE_TESTS") == "1"
BRIDGE_MODULE = REPO_ROOT / "MyCiteV2" / "packages" / "adapters" / "portal_runtime" / "v1_host_bridge.py"


def _module_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


@unittest.skipUnless(
    ENABLE_HISTORICAL_BRIDGE_TESTS,
    "historical bridge tests disabled; set MYCITE_ENABLE_HISTORICAL_BRIDGE_TESTS=1",
)
class HistoricalV2DeploymentBridgeBoundaryTests(unittest.TestCase):
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

    def test_bridge_module_is_marked_as_quarantined_history(self) -> None:
        source = BRIDGE_MODULE.read_text(encoding="utf-8")
        self.assertIn("Historical V1-host bridge retained only for retirement evidence.", source)
        self.assertIn("quarantined", source)
        self.assertIn("/portal/api/v2/admin/bridge/health", source)


if __name__ == "__main__":
    unittest.main()
