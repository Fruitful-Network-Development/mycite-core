from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MYCITE_V2_ROOT = REPO_ROOT / "MyCiteV2"
PORTAL_RUNTIME_PACKAGE_ROOT = MYCITE_V2_ROOT / "packages" / "adapters" / "portal_runtime" / "__init__.py"
FND_APP = REPO_ROOT / "MyCiteV1" / "instances" / "_shared" / "runtime" / "flavors" / "fnd" / "app.py"
TFF_APP = REPO_ROOT / "MyCiteV1" / "instances" / "_shared" / "runtime" / "flavors" / "tff" / "app.py"
ALLOWED_HISTORICAL_IMPORTERS = {
    MYCITE_V2_ROOT / "packages" / "adapters" / "portal_runtime" / "v1_host_bridge.py",
    MYCITE_V2_ROOT / "tests" / "integration" / "test_v2_deployment_bridge_shape_b.py",
    MYCITE_V2_ROOT / "tests" / "architecture" / "test_v2_deployment_bridge_boundaries.py",
}
DOC_DISALLOWED_PHRASES = {
    REPO_ROOT / "docs" / "plans" / "post_mvp_rollout" / "agent_prompt_templates.md": (
        "Implement The V2 Deployment Bridge",
        "Pick Shape B",
    ),
    REPO_ROOT
    / "docs"
    / "plans"
    / "post_mvp_rollout"
    / "post_aws_tool_platform"
    / "deployment_bridge_contract.md": (
        "Choose exactly one.",
        "Pick Shape B",
    ),
    REPO_ROOT
    / "docs"
    / "plans"
    / "post_mvp_rollout"
    / "slice_registry"
    / "admin_band0_v2_deployment_bridge.md": (
        "may receive a tiny bridge mount only if Shape B is chosen",
        "Shape B is implemented first.",
    ),
    REPO_ROOT
    / "docs"
    / "plans"
    / "post_mvp_rollout"
    / "post_aws_tool_platform"
    / "live_state_authority_and_mapping.md": (
        "Shape B bridge",
        "The bridge implementation must choose exactly one mapping",
    ),
    REPO_ROOT
    / "docs"
    / "plans"
    / "post_mvp_rollout"
    / "post_aws_tool_platform"
    / "cutover_execution_sequence.md": (
        "implement Shape B first",
    ),
}


def _module_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


class V1RetirementBoundaryTests(unittest.TestCase):
    def test_v1_fnd_and_tff_apps_no_longer_mount_the_bridge(self) -> None:
        for app_path in (FND_APP, TFF_APP):
            source = app_path.read_text(encoding="utf-8")
            imports = _module_imports(app_path)
            self.assertNotIn("MyCiteV2.packages.adapters.portal_runtime", imports)
            self.assertNotIn("register_v2_admin_bridge_routes", source)
            self.assertNotIn("V2AdminBridgeConfig", source)

    def test_no_active_mycitev2_code_imports_the_quarantined_bridge(self) -> None:
        violations: list[str] = []

        for path in sorted(MYCITE_V2_ROOT.rglob("*.py")):
            if path in ALLOWED_HISTORICAL_IMPORTERS:
                continue
            imports = _module_imports(path)
            for module_name in imports:
                if module_name == "MyCiteV2.packages.adapters.portal_runtime" or module_name.startswith(
                    "MyCiteV2.packages.adapters.portal_runtime."
                ):
                    violations.append(f"{path.relative_to(REPO_ROOT)} imports {module_name}")

        self.assertEqual(violations, [])

    def test_portal_runtime_package_root_exports_no_bridge_symbols(self) -> None:
        source = PORTAL_RUNTIME_PACKAGE_ROOT.read_text(encoding="utf-8")
        self.assertNotIn("from .v1_host_bridge import", source)
        self.assertNotIn("V2AdminBridgeConfig", source)
        self.assertNotIn("register_v2_admin_bridge_routes", source)
        self.assertNotIn("run_v2_admin_bridge_entrypoint", source)

    def test_active_docs_no_longer_instruct_bridge_first_work(self) -> None:
        violations: list[str] = []

        for path, phrases in DOC_DISALLOWED_PHRASES.items():
            text = path.read_text(encoding="utf-8")
            for phrase in phrases:
                if phrase in text:
                    violations.append(f"{path.relative_to(REPO_ROOT)} still contains {phrase!r}")

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
