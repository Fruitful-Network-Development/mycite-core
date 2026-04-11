from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOL_SANDBOX_DIR = PROJECT_ROOT / "packages" / "sandboxes" / "tool"

FORBIDDEN_IMPORT_PREFIXES = (
    "MyCiteV2.instances",
    "instances",
    "MyCiteV2.packages.modules",
    "MyCiteV2.packages.tools",
    "mycite_core",
)


def _is_allowed_absolute_import(module_name: str) -> bool:
    root_name = module_name.split(".", 1)[0]
    if root_name == "__future__":
        return True
    if root_name in getattr(sys, "stdlib_module_names", set()):
        return True
    return (
        module_name.startswith("MyCiteV2.packages.adapters.filesystem")
        or module_name.startswith("MyCiteV2.packages.sandboxes.tool")
    )


class SandboxesToolBoundaryTests(unittest.TestCase):
    def test_tool_sandbox_imports_stay_orchestration_only(self) -> None:
        violations: list[str] = []
        for path in sorted(TOOL_SANDBOX_DIR.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name
                        if module_name.startswith(FORBIDDEN_IMPORT_PREFIXES):
                            violations.append(f"{path.name}: forbidden import {module_name}")
                        elif not _is_allowed_absolute_import(module_name):
                            violations.append(f"{path.name}: non-orchestration import {module_name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        continue
                    module_name = node.module or ""
                    if module_name.startswith(FORBIDDEN_IMPORT_PREFIXES):
                        violations.append(f"{path.name}: forbidden import {module_name}")
                    elif module_name and not _is_allowed_absolute_import(module_name):
                        violations.append(f"{path.name}: non-orchestration import {module_name}")

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
