"""Boundary guard: the datum-semantics / datum-ops / MSS-identity seam in
``core`` must not depend on adapters or instances.

The datum-address / hyphae / MSS-semantics engine used to live at
``MyCiteV2.packages.adapters.sql.datum_semantics`` even though it depends only
on ``ports`` + the standard library. ``core/datum_ops`` (``ops.py`` /
``node_ops.py``) imported it from there, inverting the core->adapter dependency
direction. The engine now lives at ``MyCiteV2.packages.core.datum_semantics``;
this test locks the rule in so these packages never import from ``adapters`` or
``instances`` again.

Scope is the three packages this seam touches — ``datum_semantics``,
``datum_ops``, and ``mss`` — mirroring the per-package convention of the other
``tests/architecture`` boundary guards (e.g. :mod:`test_core_datum_refs_boundaries`,
:mod:`test_state_machine_boundaries`). It does NOT forbid ``ports``: these
packages legitimately depend on the ``ports.datum_store`` value types.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_DIR = PROJECT_ROOT / "packages" / "core"
GUARDED_PACKAGES = ("datum_semantics", "datum_ops", "mss")

FORBIDDEN_IMPORT_PREFIXES = (
    "MyCiteV2.instances",
    "instances",
    "MyCiteV2.packages.adapters",
)


def _guarded_paths() -> list[Path]:
    paths: list[Path] = []
    for package in GUARDED_PACKAGES:
        paths.extend((CORE_DIR / package).rglob("*.py"))
    return sorted(paths)


def _violations_for(module_name: str, path: Path) -> list[str]:
    if module_name.startswith(FORBIDDEN_IMPORT_PREFIXES):
        return [f"{path.relative_to(CORE_DIR)}: forbidden import {module_name}"]
    return []


class CoreDatumOpsBoundaryTests(unittest.TestCase):
    def test_datum_ops_seam_never_imports_from_adapters_or_instances(self) -> None:
        violations: list[str] = []

        for path in _guarded_paths():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        violations.extend(_violations_for(alias.name, path))
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        continue
                    module_name = node.module or ""
                    if module_name:
                        violations.extend(_violations_for(module_name, path))

        self.assertEqual(violations, [])

    def test_datum_semantics_engine_lives_in_core(self) -> None:
        # The relocation target must exist and be importable from core.
        engine = CORE_DIR / "datum_semantics" / "engine.py"
        self.assertTrue(engine.is_file(), f"missing relocated engine: {engine}")

        from MyCiteV2.packages.core.datum_semantics import (
            build_document_semantics,
            build_document_version_identity,
            parse_datum_address,
            preview_document_delete,
            preview_document_insert,
            preview_document_move,
        )


if __name__ == "__main__":
    unittest.main()
