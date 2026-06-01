"""Boundary guard: NOTHING in ``core`` may depend on an outer layer.

``core`` is the innermost layer of the hexagon: it may import the standard
library, third-party packages, other ``core`` modules, and the ``ports``
contracts — and nothing else. In particular it must never import from
``adapters``, ``instances``, ``modules``, ``state_machine``, ``tools``, or
``sandboxes``.

History: the datum-address / hyphae / MSS-semantics engine used to live at
``adapters.sql.datum_semantics`` (``core/datum_ops`` imported it from there),
and ``core/analytics/derivations`` imported a filesystem adapter directly —
both inverting the dependency direction. Those are now fixed (the engine lives
at ``core.datum_semantics``; analytics resolves through the
``ports.analytics_events`` protocol). This guard now covers **all** of ``core``
so no future commit can quietly re-introduce an inversion in any core package.

It does NOT forbid ``ports``: core legitimately depends on the ``ports`` value
types / protocols. (The stricter per-package guards for the *pure* packages
``datum_refs`` / ``datum_rules`` additionally forbid ``ports`` and live in their
own test modules.)
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_DIR = PROJECT_ROOT / "packages" / "core"

FORBIDDEN_IMPORT_PREFIXES = (
    "MyCiteV2.instances",
    "instances",
    "MyCiteV2.packages.adapters",
    "MyCiteV2.packages.modules",
    "MyCiteV2.packages.state_machine",
    "MyCiteV2.packages.tools",
    "MyCiteV2.packages.sandboxes",
)


def _guarded_paths() -> list[Path]:
    return sorted(CORE_DIR.rglob("*.py"))


def _violations_for(module_name: str, path: Path) -> list[str]:
    if module_name.startswith(FORBIDDEN_IMPORT_PREFIXES):
        return [f"{path.relative_to(CORE_DIR)}: forbidden import {module_name}"]
    return []


class CoreLayerBoundaryTests(unittest.TestCase):
    def test_core_never_imports_from_an_outer_layer(self) -> None:
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
