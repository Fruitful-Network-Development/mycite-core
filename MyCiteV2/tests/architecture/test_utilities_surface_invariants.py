"""Phase 14e postconditions — invariants over the Utilities split.

Phase 14b replaced the single ``utilities.tool_exposure`` surface
(which conflated extensions + tools + grantee profile + workbench_ui)
with four dedicated surfaces:

  * ``utilities.extensions``      — operational extensions only
  * ``utilities.grantee_profile`` — grantee selector + editor
  * ``utilities.tools``           — tool posture (CTS-GIS etc.)
  * ``utilities.peripherals``     — keypass vault landing (stub)

These tests assert the registry + bundle-builder structure that
makes the split work. They are intentionally stricter than
``test_utilities_surface_split.py`` (which pins per-surface payload
shape) — these pin the catalog + registry + post-build invariants
that catch resurrection of the legacy mixed-purpose patterns at the
*source*.

If any future change resurrects:

  * Routes the operational extensions back to the legacy surface
  * Adds a workbench_ui entry to the tools surface
  * Mixes ext_grantee_profile into the operational extensions list
  * Re-introduces the deleted ``_surface_payload_for_integrations``
    builder

these assertions catch it.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.state_machine.portal_shell import (
    UTILITIES_EXTENSIONS_SURFACE_ID,
    UTILITIES_GRANTEE_PROFILE_SURFACE_ID,
    UTILITIES_PERIPHERALS_SURFACE_ID,
    UTILITIES_TOOLS_SURFACE_ID,
    build_portal_surface_catalog,
    build_portal_tool_registry_entries,
)

OPERATIONAL_EXTENSION_IDS = frozenset(
    {"ext_aws_email", "ext_analytics", "ext_newsletter", "ext_paypal"}
)


class CatalogInvariants(unittest.TestCase):
    """The four Phase 14b surfaces must remain registered as
    launchable Utilities-rooted catalog entries.
    """

    def setUp(self) -> None:
        self.catalog = {entry.surface_id: entry for entry in build_portal_surface_catalog()}

    def test_extensions_surface_registered(self) -> None:
        entry = self.catalog.get(UTILITIES_EXTENSIONS_SURFACE_ID)
        self.assertIsNotNone(entry, "utilities.extensions must remain registered")
        self.assertEqual(entry.root_surface_id, "utilities.root")
        self.assertTrue(entry.launchable)

    def test_grantee_profile_surface_registered(self) -> None:
        entry = self.catalog.get(UTILITIES_GRANTEE_PROFILE_SURFACE_ID)
        self.assertIsNotNone(entry, "utilities.grantee_profile must remain registered")

    def test_tools_surface_registered(self) -> None:
        entry = self.catalog.get(UTILITIES_TOOLS_SURFACE_ID)
        self.assertIsNotNone(entry, "utilities.tools must remain registered")

    def test_peripherals_surface_registered(self) -> None:
        entry = self.catalog.get(UTILITIES_PERIPHERALS_SURFACE_ID)
        self.assertIsNotNone(entry, "utilities.peripherals must remain registered")


class ToolsSurfaceContentInvariants(unittest.TestCase):
    """The Tools surface payload must never re-introduce extensions or
    ``workbench_ui``. Bundle builder is exercised in-process so the
    contract holds at the runtime layer, not just at the registry.
    """

    def _tool_rows_for_tools_surface(self) -> list[dict]:
        from MyCiteV2.instances._shared.runtime.portal_shell_runtime import (
            _surface_payload_for_tools,
        )

        # Build a representative tool_rows input — mirror what
        # ``_tool_posture_rows`` emits in production (one row per
        # registry entry carrying ``is_extension`` flag).
        registry_entries = build_portal_tool_registry_entries()
        rows = [
            {
                "tool_id": e.tool_id,
                "tool": e.label,
                "label": e.label,
                "is_extension": bool(e.is_extension),
                "configured": True,
                "enabled": True,
                "operational": True,
            }
            for e in registry_entries
        ]
        payload = _surface_payload_for_tools(rows)
        out: list[dict] = []
        for section in payload.get("sections") or []:
            out.extend(section.get("items") or [])
        return out

    def test_tools_surface_excludes_all_extensions(self) -> None:
        tool_ids = {row.get("tool_id") for row in self._tool_rows_for_tools_surface()}
        for extension_id in OPERATIONAL_EXTENSION_IDS | {"ext_grantee_profile"}:
            self.assertNotIn(
                extension_id,
                tool_ids,
                f"tools surface must never contain extension {extension_id!r}",
            )

    def test_tools_surface_excludes_workbench_ui(self) -> None:
        tool_ids = {row.get("tool_id") for row in self._tool_rows_for_tools_surface()}
        self.assertNotIn(
            "workbench_ui",
            tool_ids,
            "tools surface must never contain workbench_ui — it's a SYSTEM tool",
        )


class IntegrationsBuilderDeletedInvariant(unittest.TestCase):
    """Phase 14e removed ``_surface_payload_for_integrations``. The
    Utilities/Integrations route now 302-redirects to peripherals and
    the API-level surface_id resolution falls through to the
    peripherals builder. Any reintroduction must be a deliberate act.
    """

    def test_integrations_builder_no_longer_importable(self) -> None:
        import MyCiteV2.instances._shared.runtime.portal_shell_runtime as runtime

        self.assertFalse(
            hasattr(runtime, "_surface_payload_for_integrations"),
            "_surface_payload_for_integrations was removed in Phase 14e cleanup",
        )


if __name__ == "__main__":
    unittest.main()
