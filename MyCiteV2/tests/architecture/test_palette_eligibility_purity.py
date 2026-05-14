"""Phase 12e postcondition: tool_eligibility.py is a pure function with
no I/O, no environment dependencies, no HTTP, no SQL, no filesystem.

The palette eligibility predicate (recognize_applicable_tools) is the
sole canonical filter that decides which tools surface in the palette.
Per portal_tool_surface_contract.md it must be pure — same inputs
always produce the same outputs, no side effects. If a future change
adds I/O (a database lookup, an HTTP call, a filesystem read), the
palette stops being deterministic and the contract erodes.

This test AST-scans tool_eligibility.py for imports from forbidden
modules. State-machine architectural tests cover the broader package
boundary; this one is targeted at the eligibility module specifically.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ELIGIBILITY_MODULE = (
    REPO_ROOT
    / "MyCiteV2"
    / "packages"
    / "state_machine"
    / "portal_shell"
    / "tool_eligibility.py"
)

# Modules that perform I/O or external interaction. Importing any of
# these into tool_eligibility.py would break the purity contract.
FORBIDDEN_MODULES = frozenset(
    {
        "os",
        "io",
        "sys",
        "pathlib",
        "shutil",
        "tempfile",
        "subprocess",
        "socket",
        "urllib",
        "urllib.request",
        "urllib.parse",
        "http",
        "http.client",
        "requests",
        "httpx",
        "sqlite3",
        "psycopg2",
        "pymysql",
        # MyCiteV2 packages that read/write external state.
        "MyCiteV2.packages.adapters",
        "MyCiteV2.packages.ports",
        "MyCiteV2.instances",
    }
)


def _imported_module_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if not node.level:  # absolute import only
                names.add(module)
    return names


class PaletteEligibilityPurityTests(unittest.TestCase):
    def test_module_exists(self) -> None:
        self.assertTrue(
            ELIGIBILITY_MODULE.exists(),
            "tool_eligibility.py must exist at the expected path",
        )

    def test_no_forbidden_imports(self) -> None:
        source = ELIGIBILITY_MODULE.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(ELIGIBILITY_MODULE))
        imports = _imported_module_names(tree)
        violations: list[str] = []
        for module_name in imports:
            for forbidden in FORBIDDEN_MODULES:
                if module_name == forbidden or module_name.startswith(forbidden + "."):
                    violations.append(f"forbidden import: {module_name}")
                    break
        self.assertEqual(
            violations,
            [],
            "tool_eligibility.py must remain pure. Imports from I/O / "
            "external modules break the determinism contract documented "
            "in portal_tool_surface_contract.md.",
        )

    def test_recognize_applicable_tools_is_a_function_not_a_class(self) -> None:
        source = ELIGIBILITY_MODULE.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(ELIGIBILITY_MODULE))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "recognize_applicable_tools":
                return
        self.fail(
            "recognize_applicable_tools must be a top-level function in "
            "tool_eligibility.py. A class with state would erode purity."
        )

    def test_no_global_state_assignment(self) -> None:
        source = ELIGIBILITY_MODULE.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(ELIGIBILITY_MODULE))
        suspicious: list[str] = []
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in {
                        "_cache",
                        "_state",
                        "_store",
                        "_db",
                        "_client",
                        "_session",
                    }:
                        suspicious.append(target.id)
        self.assertEqual(
            suspicious,
            [],
            "tool_eligibility.py has top-level state assignments that "
            "look like caches / handles / sessions. Pure functions should "
            "not carry state across calls.",
        )


if __name__ == "__main__":
    unittest.main()
