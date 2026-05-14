"""Phase 12a postcondition: the two dataclasses the audit flagged as
phase-by-phase drift sources are defined in exactly one file each.

`PortalToolRegistryEntry` and `build_shell_composition_payload` used to
live in two files each, and every schema change had to be applied to
both copies. Phase 12a consolidates them to a single canonical home.

Scope is narrow on purpose: the broader portal_shell package contains
additional duplication (shell.py is a 1,750-LOC monolithic aggregator
with ~30 wrapper/duplicate definitions across siblings). Cleaning that
up is a larger refactor that needs its own plan; this test pins only
the two specific drift sources that bit recent phases.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_DIR = REPO_ROOT / "MyCiteV2" / "packages" / "state_machine" / "portal_shell"


def _files_defining(symbol_name: str, *, kind: str) -> list[str]:
    """Return relative paths of files in PACKAGE_DIR that define a top-level
    class (kind="class") or function (kind="function") with this name.
    """
    target_node_type = ast.ClassDef if kind == "class" else ast.FunctionDef
    matches: list[str] = []
    for path in sorted(PACKAGE_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, target_node_type) and node.name == symbol_name:
                matches.append(path.relative_to(PACKAGE_DIR).as_posix())
                break
    return matches


class DriftSourcesAreConsolidatedTests(unittest.TestCase):
    def test_portal_tool_registry_entry_defined_once(self) -> None:
        files = _files_defining("PortalToolRegistryEntry", kind="class")
        self.assertEqual(
            files,
            ["shell.py"],
            "PortalToolRegistryEntry was duplicated across shell.py and "
            "shell_state.py through Phase 11. Phase 12a consolidated it to "
            "shell.py only. If a new copy appears, every dataclass field "
            "addition will silently break the other consumer.",
        )

    def test_build_shell_composition_payload_defined_once(self) -> None:
        files = _files_defining("build_shell_composition_payload", kind="function")
        self.assertEqual(
            files,
            ["shell.py"],
            "build_shell_composition_payload was duplicated across shell.py "
            "and shell_composition.py through Phase 11. Phase 12b consolidates "
            "it to shell.py only.",
        )


if __name__ == "__main__":
    unittest.main()
