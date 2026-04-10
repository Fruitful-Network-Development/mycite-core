from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = PROJECT_ROOT / "packages" / "state_machine"

FORBIDDEN_IMPORT_PREFIXES = (
    "MyCiteV2.instances",
    "instances",
    "MyCiteV2.packages.adapters",
    "MyCiteV2.packages.modules",
    "MyCiteV2.packages.ports",
    "MyCiteV2.packages.tools",
    "MyCiteV2.packages.sandboxes",
    "mycite_core",
)

FORBIDDEN_TEXT_TOKENS = (
    "instances/_shared",
    "runtime_paths",
    "service_tools",
    "tool_capabilities",
    "SandboxEngine",
    "/network/",
    "http://",
    "https://",
    "pkgutil",
    "importlib",
    ".glob(",
    ".rglob(",
)


def _is_allowed_absolute_import(module_name: str) -> bool:
    root_name = module_name.split(".", 1)[0]
    if root_name == "__future__":
        return True
    if root_name in getattr(sys, "stdlib_module_names", set()):
        return True
    return module_name.startswith("MyCiteV2.packages.core") or module_name.startswith("MyCiteV2.packages.state_machine")


class StateMachineBoundaryTests(unittest.TestCase):
    def test_imports_remain_inward_core_or_state_machine_only(self) -> None:
        violations: list[str] = []

        for path in sorted(PACKAGE_DIR.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name
                        if module_name.startswith(FORBIDDEN_IMPORT_PREFIXES):
                            violations.append(f"{path.relative_to(PACKAGE_DIR)}: forbidden import {module_name}")
                        elif not _is_allowed_absolute_import(module_name):
                            violations.append(f"{path.relative_to(PACKAGE_DIR)}: non-state-machine import {module_name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        continue
                    module_name = node.module or ""
                    if module_name.startswith(FORBIDDEN_IMPORT_PREFIXES):
                        violations.append(f"{path.relative_to(PACKAGE_DIR)}: forbidden import {module_name}")
                    elif module_name and not _is_allowed_absolute_import(module_name):
                        violations.append(f"{path.relative_to(PACKAGE_DIR)}: non-state-machine import {module_name}")

        self.assertEqual(violations, [])

    def test_source_contains_no_runtime_tool_or_sandbox_leakage(self) -> None:
        violations: list[str] = []

        for path in sorted(PACKAGE_DIR.rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            for token in FORBIDDEN_TEXT_TOKENS:
                if token in text:
                    violations.append(f"{path.relative_to(PACKAGE_DIR)}: forbidden token {token!r}")

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
