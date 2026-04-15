from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_FILE = PROJECT_ROOT / "packages" / "adapters" / "filesystem" / "aws_read_only_status.py"

FORBIDDEN_IMPORT_PREFIXES = (
    "MyCiteV2.instances",
    "instances",
    "MyCiteV2.packages.modules",
    "MyCiteV2.packages.tools",
    "MyCiteV2.packages.sandboxes",
    "mycite_core",
)

FORBIDDEN_TEXT_TOKENS = (
    "smtp_password",
    "secret_access_key",
    "/portal/api/admin/",
)


def _is_allowed_absolute_import(module_name: str) -> bool:
    root_name = module_name.split(".", 1)[0]
    if root_name == "__future__":
        return True
    if root_name in getattr(sys, "stdlib_module_names", set()):
        return True
    return module_name.startswith("MyCiteV2.packages.adapters.filesystem") or module_name.startswith(
        "MyCiteV2.packages.ports.aws_read_only_status"
    )


class FilesystemAwsReadOnlyStatusBoundaryTests(unittest.TestCase):
    def test_imports_remain_adapter_side_without_semantic_ownership(self) -> None:
        violations: list[str] = []
        tree = ast.parse(PACKAGE_FILE.read_text(encoding="utf-8"), filename=str(PACKAGE_FILE))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    if module_name.startswith(FORBIDDEN_IMPORT_PREFIXES):
                        violations.append(f"aws_read_only_status.py: forbidden import {module_name}")
                    elif not _is_allowed_absolute_import(module_name):
                        violations.append(f"aws_read_only_status.py: non-adapter import {module_name}")
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    continue
                module_name = node.module or ""
                if module_name.startswith(FORBIDDEN_IMPORT_PREFIXES):
                    violations.append(f"aws_read_only_status.py: forbidden import {module_name}")
                elif module_name and not _is_allowed_absolute_import(module_name):
                    violations.append(f"aws_read_only_status.py: non-adapter import {module_name}")

        self.assertEqual(violations, [])

    def test_source_contains_no_provider_route_or_secret_surface_knowledge(self) -> None:
        text = PACKAGE_FILE.read_text(encoding="utf-8")
        violations = [f"aws_read_only_status.py: forbidden token {token!r}" for token in FORBIDDEN_TEXT_TOKENS if token in text]
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
