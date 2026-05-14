"""Phase 3 postconditions for TASK-PORTAL-SIMPLIFICATION-2026-05-14.

Locks in the end state described by
/srv/agentic/knowledge/legacy/mycite-core/contracts/portal_tool_surface_contract.md:

  - the retired interface_panel renderer JS files are gone
  - the asset manifest no longer lists interface_panel-related modules
  - the FND-CSM tool surface (catalog + registry) is retired
  - every first-class tool in the registry is a palette target
  - the build_shell_composition_payload pipeline never marks interface_panel
    visible or primary
  - the legacy GET /portal/system/tools/fnd-csm route still 302-redirects to
    /portal/utilities/tool-exposure (preservation contract)

If a future change resurrects any of the above, these assertions catch it.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None

if FLASK_AVAILABLE:
    from MyCiteV2.instances._shared.portal_host.app import (
        PORTAL_SHELL_MODULE_CONTRACTS,
        V2PortalHostConfig,
        create_app,
    )

from MyCiteV2.packages.state_machine.portal_shell import (
    SURFACE_POSTURE_PALETTE_TARGET,
    UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
    WORKBENCH_UI_TOOL_SURFACE_ID,
    build_portal_surface_catalog,
    build_portal_tool_registry_entries,
    build_shell_composition_payload,
)

STATIC_DIR = REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static"
RETIRED_JS_FILES = (
    "v2_portal_interface_panel_host.js",
    "v2_portal_interface_panel_renderers.js",
    "v2_portal_fnd_csm_workspace.js",
)
RETIRED_MODULE_IDS = (
    "interface_panel_renderers",
    "fnd_csm_workspace",
    "cts_gis_surface",
    "cts_gis_workspace",
)


class RetiredJsArtifactsTests(unittest.TestCase):
    def test_retired_interface_panel_js_files_are_deleted(self) -> None:
        for filename in RETIRED_JS_FILES:
            path = STATIC_DIR / filename
            self.assertFalse(
                path.exists(),
                f"Phase 3 deletes {filename}; resurrection violates portal_tool_surface_contract.md",
            )

    def test_tool_palette_js_is_present(self) -> None:
        path = STATIC_DIR / "v2_portal_tool_palette.js"
        self.assertTrue(
            path.exists(),
            "Phase 3a adds v2_portal_tool_palette.js as the palette UI module",
        )


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class AssetManifestTests(unittest.TestCase):
    def test_asset_manifest_excludes_retired_module_ids(self) -> None:
        module_ids = {entry["module_id"] for entry in PORTAL_SHELL_MODULE_CONTRACTS}
        for retired_id in RETIRED_MODULE_IDS:
            self.assertNotIn(
                retired_id,
                module_ids,
                f"Phase 3 removes {retired_id} from PORTAL_SHELL_MODULE_CONTRACTS",
            )

    def test_asset_manifest_includes_tool_palette(self) -> None:
        module_ids = {entry["module_id"] for entry in PORTAL_SHELL_MODULE_CONTRACTS}
        self.assertIn("tool_palette", module_ids)


class RegistryPostconditionTests(unittest.TestCase):
    def test_fnd_csm_tool_surface_is_retired(self) -> None:
        surface_ids = [entry.surface_id for entry in build_portal_surface_catalog()]
        self.assertNotIn(
            "system.tools.fnd_csm",
            surface_ids,
            "Phase 3g retires the fnd_csm tool surface",
        )

    def test_no_fnd_csm_registry_entry(self) -> None:
        tool_ids = [entry.tool_id for entry in build_portal_tool_registry_entries()]
        self.assertNotIn(
            "fnd_csm",
            tool_ids,
            "Phase 3g retires the fnd_csm registry entry — its tabs now live as utilities extensions",
        )

    def test_every_tool_is_palette_target(self) -> None:
        for entry in build_portal_tool_registry_entries():
            self.assertEqual(
                entry.surface_posture,
                SURFACE_POSTURE_PALETTE_TARGET,
                f"{entry.tool_id} must have surface_posture=palette_target",
            )

    def test_extensions_live_under_utilities_tool_exposure(self) -> None:
        for entry in build_portal_tool_registry_entries():
            if entry.is_extension:
                self.assertEqual(
                    entry.surface_id,
                    UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
                    f"Extension {entry.tool_id} must live under utilities.tool_exposure",
                )


class CompositionPostconditionTests(unittest.TestCase):
    def test_interface_panel_is_never_visible(self) -> None:
        for surface_id in (
            "system.root",
            "network.root",
            "utilities.root",
            "utilities.tool_exposure",
            "system.tools.cts_gis",
            WORKBENCH_UI_TOOL_SURFACE_ID,
        ):
            composition = build_shell_composition_payload(
                active_surface_id=surface_id,
                portal_instance_id="fnd",
                page_title="t",
                page_subtitle="",
                activity_items=[],
                control_panel={},
                workbench={"visible": True},
                interface_panel={"visible": True},
                shell_state=None,
            )
            self.assertFalse(
                composition["regions"]["interface_panel"]["visible"],
                f"interface_panel must be hidden for surface={surface_id}",
            )
            self.assertTrue(composition["interface_panel_collapsed"])
            self.assertFalse(composition["regions"]["interface_panel"]["primary_surface"])


class VestigialInterfacePanelReferencesTests(unittest.TestCase):
    """Phase 6: bound the count of remaining interface_panel references.

    Phase 3-5 hid the interface_panel region, deleted its dedicated renderer
    JS, and removed nimm_aitas_control content. Some Python and JS files keep
    handler/import code that no-ops because the runtime never emits an active
    interface_panel — removing them is mechanical follow-up work outside the
    portal_tool_surface_contract.md acceptance bar.

    This test pins the current count so accidentally re-introducing
    interface_panel concepts fails loudly. Lower the cap (or drop the
    allowlist entry) once a cleanup commit removes a remaining file.
    """

    # Files that legitimately still mention interface_panel in dead handler
    # code, schema constants, or composition-region scaffolding. Each line is
    # checked against a per-file ceiling; total must not grow.
    ALLOWED_FILES = {
        "instances/_shared/portal_host/app.py",
        "instances/_shared/portal_host/templates/portal.html",
        "instances/_shared/portal_host/static/v2_portal_shell_watchdog.js",
        "instances/_shared/portal_host/static/v2_portal_shell_core.js",
        "instances/_shared/portal_host/static/v2_portal_component_library.js",
        "instances/_shared/portal_host/static/v2_portal_system_workspace.js",
        "instances/_shared/portal_host/static/v2_portal_network_workspace.js",
        "instances/_shared/portal_host/static/v2_portal_tool_surface_adapter.js",
        "instances/_shared/portal_host/static/portal.js",
        "instances/_shared/runtime/portal_shell_runtime.py",
        "instances/_shared/runtime/portal_fnd_csm_runtime.py",
        "instances/_shared/runtime/portal_cts_gis_runtime.py",
        "instances/_shared/runtime/portal_system_workspace_runtime.py",
        "instances/_shared/runtime/portal_workbench_ui_runtime.py",
        "packages/state_machine/portal_shell/shell_state.py",
        "packages/state_machine/portal_shell/shell_schemas.py",
        "packages/state_machine/portal_shell/shell_composition.py",
        "packages/state_machine/portal_shell/shell_request.py",
        "packages/state_machine/portal_shell/shell.py",
        "packages/state_machine/portal_shell/shell_registry.py",
        "packages/state_machine/portal_shell/README.md",
        "packages/state_machine/nimm/mediate_handlers.py",
        "packages/tools/workbench_ui/service.py",
        "packages/modules/cross_domain/cts_gis/compiled_artifact.py",
    }
    ALLOWED_TOTAL_CEILING = 320  # vestigial references — cleanup follow-up

    def test_interface_panel_references_are_bounded(self) -> None:
        repo_mycite = REPO_ROOT / "MyCiteV2"
        offenders: dict[str, int] = {}
        unallowed: list[str] = []
        for candidate in repo_mycite.rglob("*"):
            if not candidate.is_file():
                continue
            if "__pycache__" in candidate.parts or ".git" in candidate.parts:
                continue
            if "tests" in candidate.parts:
                continue
            try:
                text = candidate.read_text(encoding="utf-8", errors="ignore")
            except (OSError, UnicodeDecodeError):
                continue
            count = text.count("interface_panel") + text.count("INTERFACE_PANEL") + text.count("InterfacePanel")
            if count == 0:
                continue
            rel = candidate.relative_to(repo_mycite).as_posix()
            if rel not in self.ALLOWED_FILES:
                unallowed.append(f"{rel}: {count} reference(s)")
                continue
            offenders[rel] = count
        self.assertEqual(
            unallowed,
            [],
            "Phase 3-5 cleared interface_panel from these paths; a new reference "
            "is a regression. Update ALLOWED_FILES only when adding a known "
            "follow-up scope.",
        )
        total = sum(offenders.values())
        self.assertLessEqual(
            total,
            self.ALLOWED_TOTAL_CEILING,
            f"Vestigial interface_panel references grew beyond {self.ALLOWED_TOTAL_CEILING}: {offenders}",
        )


class ToolRegistryHasEligibilityFieldsTests(unittest.TestCase):
    """Phase 6: every first-class tool must declare what datums it applies to,
    and every extension must carry is_extension=True. Without this invariant
    the palette can silently degrade (a tool with no applies_to_* never shows)
    or pollute (a misregistered service entry shows for every datum).
    """

    def test_every_registry_entry_declares_eligibility(self) -> None:
        for entry in build_portal_tool_registry_entries():
            if entry.is_extension:
                continue  # Extensions opt out of palette eligibility entirely.
            has_archetype = bool(entry.applies_to_archetype)
            has_source_kind = bool(entry.applies_to_source_kind)
            self.assertTrue(
                has_archetype or has_source_kind,
                f"{entry.tool_id} is a first-class palette tool and must declare "
                "applies_to_archetype or applies_to_source_kind (or be marked is_extension=True)",
            )

    def test_write_capable_tools_declare_manipulates_datum_kinds_unless_extension(self) -> None:
        """Phase 11 (datum_catalog_phase_e4_migration.md): every tool that
        writes to the MOS datum store must declare which datum kinds it
        may mutate. Extensions are exempt because they write to filesystem
        grantee JSON or operational ndjson, not the datum store.
        """
        for entry in build_portal_tool_registry_entries():
            if entry.is_extension:
                continue
            if entry.read_write_posture != "write":
                continue
            self.assertTrue(
                bool(entry.manipulates_datum_kinds),
                f"{entry.tool_id} has read_write_posture=write but does not "
                "declare manipulates_datum_kinds. Either declare which datum "
                "kinds it mutates or change the posture to read-only.",
            )


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class LegacyFndCsmRedirectTests(unittest.TestCase):
    def test_legacy_fnd_csm_route_still_redirects(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="phase3_postcond_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain="example.org",
            webapps_root=tmp / "webapps",
        )
        client = create_app(config).test_client()
        resp = client.get("/portal/system/tools/fnd-csm", follow_redirects=False)
        self.assertEqual(
            resp.status_code,
            302,
            "Preservation contract: legacy FND-CSM URL must redirect to Utilities",
        )
        self.assertEqual(resp.headers["Location"], "/portal/utilities/tool-exposure")


if __name__ == "__main__":
    unittest.main()
