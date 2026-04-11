from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = PROJECT_ROOT / "packages" / "ports" / "datum_store"

FORBIDDEN_IMPORT_PREFIXES = (
    "MyCiteV2.instances",
    "instances",
    "MyCiteV2.packages.adapters",
    "MyCiteV2.packages.modules",
    "MyCiteV2.packages.tools",
    "MyCiteV2.packages.sandboxes",
    "mycite_core",
)

FORBIDDEN_TEXT_TOKENS = (
    "pathlib",
    "filesystem",
    "append_",
    "update_",
    "shell_state",
)


def _is_allowed_absolute_import(module_name: str) -> bool:
    root_name = module_name.split(".", 1)[0]
    if root_name == "__future__":
        return True
    if root_name in getattr(sys, "stdlib_module_names", set()):
        return True
    return module_name.startswith("MyCiteV2.packages.ports.datum_store")


class DatumStorePortBoundaryTests(unittest.TestCase):
    def test_imports_remain_port_only(self) -> None:
        violations: list[str] = []

        for path in sorted(PACKAGE_DIR.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name
                        if module_name.startswith(FORBIDDEN_IMPORT_PREFIXES):
                            violations.append(f"{path.name}: forbidden import {module_name}")
                        elif not _is_allowed_absolute_import(module_name):
                            violations.append(f"{path.name}: non-port import {module_name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        continue
                    module_name = node.module or ""
                    if module_name.startswith(FORBIDDEN_IMPORT_PREFIXES):
                        violations.append(f"{path.name}: forbidden import {module_name}")
                    elif module_name and not _is_allowed_absolute_import(module_name):
                        violations.append(f"{path.name}: non-port import {module_name}")

        self.assertEqual(violations, [])

    def test_source_contains_no_filesystem_or_write_ownership_leakage(self) -> None:
        violations: list[str] = []

        for path in sorted(PACKAGE_DIR.glob("*.py")):
            text = path.read_text(encoding="utf-8").lower()
            for token in FORBIDDEN_TEXT_TOKENS:
                if token in text:
                    violations.append(f"{path.name}: forbidden token {token!r}")

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
