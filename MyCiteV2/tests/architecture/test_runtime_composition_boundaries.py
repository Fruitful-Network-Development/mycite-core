from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = PROJECT_ROOT / "instances" / "_shared" / "runtime"
FLAVORS_DIR = RUNTIME_DIR / "flavors"

FORBIDDEN_IMPORT_PREFIXES = (
    "MyCiteV2.packages.tools",
    "MyCiteV2.packages.sandboxes",
    "mycite_core",
)

FORBIDDEN_TEXT_TOKENS = (
    "FastAPI",
    "flask",
    "sandbox",
    "tool",
    "route",
    "http://",
    "https://",
)


def _is_allowed_absolute_import(module_name: str) -> bool:
    root_name = module_name.split(".", 1)[0]
    if root_name == "__future__":
        return True
    if root_name in getattr(sys, "stdlib_module_names", set()):
        return True
    return module_name.startswith("MyCiteV2.packages.") or module_name.startswith("MyCiteV2.instances._shared.runtime")


class RuntimeCompositionBoundaryTests(unittest.TestCase):
    def test_runtime_imports_compose_inward_layers_only(self) -> None:
        runtime_file = RUNTIME_DIR / "mvp_runtime.py"
        violations: list[str] = []

        tree = ast.parse(runtime_file.read_text(encoding="utf-8"), filename=str(runtime_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    if module_name.startswith(FORBIDDEN_IMPORT_PREFIXES):
                        violations.append(f"mvp_runtime.py: forbidden import {module_name}")
                    elif not _is_allowed_absolute_import(module_name):
                        violations.append(f"mvp_runtime.py: non-runtime import {module_name}")
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    continue
                module_name = node.module or ""
                if module_name.startswith(FORBIDDEN_IMPORT_PREFIXES):
                    violations.append(f"mvp_runtime.py: forbidden import {module_name}")
                elif module_name and not _is_allowed_absolute_import(module_name):
                    violations.append(f"mvp_runtime.py: non-runtime import {module_name}")

        self.assertEqual(violations, [])

    def test_runtime_surface_stays_single_path_without_flavor_expansion(self) -> None:
        runtime_python_files = sorted(path.name for path in RUNTIME_DIR.glob("*.py"))
        flavor_python_files = sorted(path.name for path in FLAVORS_DIR.glob("*.py"))

        self.assertEqual(runtime_python_files, ["mvp_runtime.py"])
        self.assertEqual(flavor_python_files, [])

    def test_runtime_source_contains_no_tool_sandbox_or_route_logic(self) -> None:
        text = (RUNTIME_DIR / "mvp_runtime.py").read_text(encoding="utf-8")
        violations = [token for token in FORBIDDEN_TEXT_TOKENS if token in text]
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
