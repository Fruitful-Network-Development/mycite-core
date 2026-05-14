"""Phase 11 architecture postcondition: the grantee JSON layer stays
orthogonal to the SQL-backed MOS datum store.

Per datum_catalog_phase_e4_migration.md and grantee_profile_contract.md,
packages/core/grantee/ must not import from packages/adapters/sql/ or
packages/ports/datum_store/. The filesystem-backed operator-credential
surface (grantee.*.json) and the SQL-backed authoritative datum store
are two distinct concerns; coupling them would mean future datum
refactors could break the Utilities form layer.

This test parses every .py file under packages/core/grantee/ via AST
and asserts no Import or ImportFrom node references a forbidden module
prefix. If a future change pulls one in, this test fails before the
coupling lands.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GRANTEE_PACKAGE = REPO_ROOT / "MyCiteV2" / "packages" / "core" / "grantee"

FORBIDDEN_PREFIXES = (
    "MyCiteV2.packages.adapters.sql",
    "MyCiteV2.packages.ports.datum_store",
)


class GranteeOrthogonalToMosTests(unittest.TestCase):
    def test_no_module_imports_from_adapters_sql_or_ports_datum_store(self) -> None:
        self.assertTrue(GRANTEE_PACKAGE.is_dir(), "packages/core/grantee/ must exist")
        violations: list[str] = []
        for path in sorted(GRANTEE_PACKAGE.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            rel = path.relative_to(REPO_ROOT).as_posix()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for prefix in FORBIDDEN_PREFIXES:
                            if alias.name.startswith(prefix):
                                violations.append(f"{rel}: import {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for prefix in FORBIDDEN_PREFIXES:
                        if module.startswith(prefix):
                            violations.append(f"{rel}: from {module} import ...")
        self.assertEqual(
            violations,
            [],
            "packages/core/grantee/ must remain orthogonal to the MOS datum "
            "store. Move adapter-aware code into a runtime module instead.",
        )

    def test_grantee_package_does_exist_and_holds_schema_and_store(self) -> None:
        self.assertTrue((GRANTEE_PACKAGE / "__init__.py").exists())
        self.assertTrue((GRANTEE_PACKAGE / "schema.py").exists())
        self.assertTrue((GRANTEE_PACKAGE / "store.py").exists())


if __name__ == "__main__":
    unittest.main()
