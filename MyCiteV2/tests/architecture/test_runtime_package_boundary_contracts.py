from __future__ import annotations

import ast
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = PROJECT_ROOT / "instances" / "_shared" / "runtime"


class RuntimePackageBoundaryContractTests(unittest.TestCase):
    def test_runtime_does_not_import_domain_service_modules_directly(self) -> None:
        violations: list[str] = []

        for path in sorted(RUNTIME_DIR.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name
                        if module_name.startswith("MyCiteV2.packages.modules.domains.") and module_name.endswith(".service"):
                            violations.append(f"{path.name}: forbidden import {module_name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        continue
                    module_name = node.module or ""
                    if module_name.startswith("MyCiteV2.packages.modules.domains.") and module_name.endswith(".service"):
                        violations.append(f"{path.name}: forbidden import {module_name}")

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
