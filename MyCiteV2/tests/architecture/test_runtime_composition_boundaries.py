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

GENERAL_FORBIDDEN_TEXT_TOKENS = (
    "FastAPI",
    "flask",
    "http://",
    "https://",
)

ADMIN_RUNTIME_FORBIDDEN_TEXT_TOKENS = (
    "newsletter-admin",
    "newsletter_admin",
    "paypal",
    "keycloak",
    "analytics",
    "progeny_workbench",
    "portal/api/admin/",
    "packages/tools",
)

AWS_RUNTIME_FORBIDDEN_TEXT_TOKENS = (
    "newsletter-admin",
    "newsletter_admin",
    "paypal",
    "keycloak",
    "maps",
    "agro",
    "/portal/api/admin/",
    "write_capability\": \"available\"",
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
        violations: list[str] = []

        for runtime_file in sorted(RUNTIME_DIR.glob("*.py")):
            tree = ast.parse(runtime_file.read_text(encoding="utf-8"), filename=str(runtime_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name
                        if module_name.startswith(FORBIDDEN_IMPORT_PREFIXES):
                            violations.append(f"{runtime_file.name}: forbidden import {module_name}")
                        elif not _is_allowed_absolute_import(module_name):
                            violations.append(f"{runtime_file.name}: non-runtime import {module_name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        continue
                    module_name = node.module or ""
                    if module_name.startswith(FORBIDDEN_IMPORT_PREFIXES):
                        violations.append(f"{runtime_file.name}: forbidden import {module_name}")
                    elif module_name and not _is_allowed_absolute_import(module_name):
                        violations.append(f"{runtime_file.name}: non-runtime import {module_name}")

        self.assertEqual(violations, [])

    def test_runtime_surface_stays_single_path_without_flavor_expansion(self) -> None:
        runtime_python_files = sorted(path.name for path in RUNTIME_DIR.glob("*.py"))
        flavor_python_files = sorted(path.name for path in FLAVORS_DIR.glob("*.py"))

        self.assertEqual(runtime_python_files, ["admin_aws_runtime.py", "admin_runtime.py", "mvp_runtime.py"])
        self.assertEqual(flavor_python_files, [])

    def test_runtime_source_contains_no_framework_or_legacy_provider_logic(self) -> None:
        violations: list[str] = []

        for runtime_file in sorted(RUNTIME_DIR.glob("*.py")):
            text = runtime_file.read_text(encoding="utf-8")
            for token in GENERAL_FORBIDDEN_TEXT_TOKENS:
                if token in text:
                    violations.append(f"{runtime_file.name}: forbidden token {token!r}")
            if runtime_file.name == "admin_runtime.py":
                for token in ADMIN_RUNTIME_FORBIDDEN_TEXT_TOKENS:
                    if token in text:
                        violations.append(f"{runtime_file.name}: forbidden token {token!r}")
            if runtime_file.name == "admin_aws_runtime.py":
                for token in AWS_RUNTIME_FORBIDDEN_TEXT_TOKENS:
                    if token in text:
                        violations.append(f"{runtime_file.name}: forbidden token {token!r}")

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
