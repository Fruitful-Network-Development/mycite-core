"""Postcondition: every module_id referenced from JS resolves either in the
asset manifest or via a clean fallback path.

Phase 3-7 deleted several shell module files (v2_portal_interface_panel_
renderers.js, v2_portal_cts_gis_workspace.js, v2_portal_fnd_csm_workspace.js,
v2_portal_cts_gis_surface.js). The shell core + watchdog + tool-surface
adapter all carried hard references to those module_ids after the files
disappeared, surfacing as "Shell hydration failed" / "module unavailable"
error cards at runtime. We fixed the live ones in commit 9abb4d2 + the
hazards-cleanup commit; this test pins the invariant so it doesn't drift.

What it checks
==============
For every JS file under MyCiteV2/instances/_shared/portal_host/static/:

  1. ``resolveRegisteredModuleExport("<module_id>", ...)`` calls reference
     only module_ids that appear in PORTAL_SHELL_MODULE_CONTRACTS.

  2. The shell_watchdog's ``firstRegistrationFailure`` allowlist is a
     subset of PORTAL_SHELL_MODULE_CONTRACTS module_ids.

  3. ``moduleId: "<module_id>"`` entries in the tool-surface adapter's
     moduleSpecs reference only module_ids that exist in the manifest
     (so resolveReflectiveWorkspaceMode never routes to a phantom
     "registered_workspace" renderer).

A failure here means a JS file is asking the shell to register a module
that no longer ships — same class of bug that produced the Phase 12h
hydration failure.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.portal_host.app import PORTAL_SHELL_MODULE_CONTRACTS

STATIC_DIR = (
    Path(__file__).resolve().parents[2]
    / "instances"
    / "_shared"
    / "portal_host"
    / "static"
)

_RESOLVE_MODULE_RE = re.compile(r'resolveRegisteredModuleExport\(\s*"([^"]+)"')
_MODULE_ID_LITERAL_RE = re.compile(r'moduleId:\s*"([^"]+)"')


def _manifest_module_ids() -> set[str]:
    return {contract["module_id"] for contract in PORTAL_SHELL_MODULE_CONTRACTS}


def _watchdog_allowlist() -> set[str]:
    """Pull the firstRegistrationFailure([...]) list out of v2_portal_shell_watchdog.js."""
    source = (STATIC_DIR / "v2_portal_shell_watchdog.js").read_text(encoding="utf-8")
    match = re.search(
        r"firstRegistrationFailure\(\[\s*([^\]]+)\]",
        source,
    )
    if not match:
        return set()
    raw = match.group(1)
    return set(re.findall(r'"([^"]+)"', raw))


class ShellModuleReferencesResolveTests(unittest.TestCase):
    def test_resolve_registered_module_export_uses_manifest_ids(self) -> None:
        manifest = _manifest_module_ids()
        # Every static .js file in the portal host directory.
        offenders: list[str] = []
        for js_path in sorted(STATIC_DIR.glob("*.js")):
            source = js_path.read_text(encoding="utf-8")
            for module_id in _RESOLVE_MODULE_RE.findall(source):
                if module_id not in manifest:
                    offenders.append(f"{js_path.name}: {module_id}")
        self.assertEqual(
            offenders,
            [],
            f"resolveRegisteredModuleExport references a module_id absent from "
            f"PORTAL_SHELL_MODULE_CONTRACTS: {offenders}",
        )

    def test_watchdog_required_modules_subset_of_manifest(self) -> None:
        manifest = _manifest_module_ids()
        watchdog = _watchdog_allowlist()
        self.assertTrue(
            watchdog,
            "watchdog firstRegistrationFailure([...]) call could not be parsed",
        )
        extra = watchdog - manifest
        self.assertEqual(
            extra,
            set(),
            f"shell_watchdog requires module_ids absent from manifest: {extra}",
        )

    def test_tool_surface_adapter_moduleid_literals_use_manifest_ids(self) -> None:
        manifest = _manifest_module_ids()
        source = (
            STATIC_DIR / "v2_portal_tool_surface_adapter.js"
        ).read_text(encoding="utf-8")
        offenders = [
            module_id
            for module_id in _MODULE_ID_LITERAL_RE.findall(source)
            if module_id not in manifest
        ]
        self.assertEqual(
            offenders,
            [],
            f"tool_surface_adapter declares moduleSpec for module_ids absent "
            f"from manifest: {offenders}",
        )


if __name__ == "__main__":
    unittest.main()
