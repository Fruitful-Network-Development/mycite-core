from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

HOST_DIR = REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host"


def _module_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


class V2NativePortalHostBoundaryTests(unittest.TestCase):
    def test_host_uses_v2_runtime_and_adapters_without_v1_imports(self) -> None:
        violations: list[str] = []

        for path in sorted(HOST_DIR.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            imports = _module_imports(path)
            for module_name in imports:
                if module_name.startswith("MyCiteV1"):
                    violations.append(f"{path.name}: forbidden V1 import {module_name}")
            for token in ("MyCiteV1", "v1_host_bridge", "register_v2_admin_bridge_routes"):
                if token in source:
                    violations.append(f"{path.name}: forbidden token {token}")

        self.assertEqual(violations, [])

    def test_host_does_not_expose_the_shape_b_health_route(self) -> None:
        source = (HOST_DIR / "app.py").read_text(encoding="utf-8")
        self.assertNotIn("/portal/api/v2/admin/bridge/health", source)
        self.assertIn("/portal/status", source)
        self.assertIn("/portal/activity", source)
        self.assertIn("/portal/api/v2/admin/shell", source)
        self.assertIn("/portal/api/v2/tenant/home", source)
        self.assertIn("/portal/api/v2/tenant/operational-status", source)
        self.assertIn("/portal/api/v2/tenant/audit-activity", source)
        self.assertIn("/portal/api/v2/data/system/resource-workbench", source)

    def test_portal_shell_js_has_no_fallback_catalog_nav(self) -> None:
        js = (HOST_DIR / "static" / "v2_portal_shell.js").read_text(encoding="utf-8")
        self.assertNotIn("buildFallbackNav", js)
        self.assertNotIn("admin_band0.home_status", js)
        self.assertNotIn("SLICE_", js)


if __name__ == "__main__":
    unittest.main()
