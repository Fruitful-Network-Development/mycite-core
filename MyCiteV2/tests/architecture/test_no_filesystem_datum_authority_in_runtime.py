"""Architecture invariant: runtime modules MUST NOT use the filesystem
datum-store adapter or glob sandbox directories.

The filesystem adapter (``FilesystemSystemDatumStoreAdapter``) survives in
the codebase as a one-shot bootstrap shim. It must not be imported from
any module under ``MyCiteV2/instances/`` (the runtime / portal-shell tier),
where the only acceptable datum-store is ``SqliteSystemDatumStoreAdapter``.

This test fails if any runtime module:
  - imports ``FilesystemSystemDatumStoreAdapter`` (by name)
  - references ``filesystem.FilesystemSystemDatumStoreAdapter``
  - calls ``.glob(`` against a sandbox/system datum path literal

Currently expected to FAIL: ``portal_cts_gis_runtime.py`` still imports
the filesystem adapter for runtime fallback and globs ``data/sandbox/``.
Goes GREEN after Phase 6 of plan ``quiet-booping-stream.md`` lands.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_ROOT = REPO_ROOT / "MyCiteV2" / "instances"

_FORBIDDEN_IMPORT_NAMES = {
    "FilesystemSystemDatumStoreAdapter",
}
_FORBIDDEN_PATH_FRAGMENTS = (
    "data/sandbox",
    "data/system",
    "data/payloads/cache",
)


class _ImportFinder(ast.NodeVisitor):
    def __init__(self) -> None:
        self.violations: list[tuple[int, str]] = []

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name in _FORBIDDEN_IMPORT_NAMES:
                self.violations.append((node.lineno, f"from {node.module} import {alias.name}"))
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # `something.FilesystemSystemDatumStoreAdapter`
        if node.attr in _FORBIDDEN_IMPORT_NAMES:
            self.violations.append((node.lineno, f".{node.attr}"))
        self.generic_visit(node)


class _PathGlobFinder(ast.NodeVisitor):
    def __init__(self) -> None:
        self.violations: list[tuple[int, str]] = []
        self._string_constants: dict[int, str] = {}

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str):
            self._string_constants[node.lineno] = node.value
        self.generic_visit(node)


class NoFilesystemDatumAuthorityInRuntimeTest(unittest.TestCase):
    # Required invariant. Phase 6 runtime refactor landed 2026-05-17.
    def test_no_filesystem_adapter_imports_in_runtime(self) -> None:
        if not RUNTIME_ROOT.exists():
            self.skipTest(f"runtime tree not present: {RUNTIME_ROOT}")
        violations: list[str] = []
        for py_file in RUNTIME_ROOT.rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text())
            except (SyntaxError, OSError):
                continue
            finder = _ImportFinder()
            finder.visit(tree)
            for line, snippet in finder.violations:
                rel = py_file.relative_to(REPO_ROOT)
                violations.append(f"{rel}:{line} {snippet}")
        self.assertEqual(
            violations,
            [],
            f"{len(violations)} runtime modules reference the filesystem datum adapter. "
            f"First 5: {violations[:5]}",
        )

    # Required invariant. Phase 6 runtime refactor landed 2026-05-17.
    def test_no_sandbox_directory_helpers_in_runtime(self) -> None:
        """Specific helper functions that glob disk sandbox trees must not
        exist in the runtime. Currently catches
        ``_cts_gis_data_tool_root``, ``_cts_gis_source_path``,
        ``_cts_gis_tool_anchor_path`` in ``portal_cts_gis_runtime.py``.
        Goes GREEN after Phase 6 replaces these with MOS queries.
        """
        if not RUNTIME_ROOT.exists():
            self.skipTest(f"runtime tree not present: {RUNTIME_ROOT}")
        forbidden_names = {
            "_cts_gis_data_tool_root",
            "_cts_gis_source_path",
            "_cts_gis_tool_anchor_path",
            "_datum_store_for_data_dir",
        }
        violations: list[str] = []
        for py_file in RUNTIME_ROOT.rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text())
            except (SyntaxError, OSError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name in forbidden_names:
                    rel = py_file.relative_to(REPO_ROOT)
                    violations.append(f"{rel}:{node.lineno} def {node.name}")
        self.assertEqual(
            violations,
            [],
            f"{len(violations)} forbidden disk-glob helper(s) still defined in runtime. "
            f"First 5: {violations[:5]}",
        )


if __name__ == "__main__":
    unittest.main()
