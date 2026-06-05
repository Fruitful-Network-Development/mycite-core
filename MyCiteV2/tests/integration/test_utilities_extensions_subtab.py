"""Phase 15a — Per-extension subtabs on /portal/utilities/extensions.

The Extensions surface now carries an ``extension_subtab_selector``
sitting below the Phase 12h grantee selector. Each tab posts to
``/portal/api/v2/shell`` with
``surface_query.selected_extension_tool_id``, preserving the active
``selected_grantee_msn`` so the two axes are independent.

Only the active tab's extension card lands in
``payload["extensions"]``. The 4 tab options are
Email / Analytics / Newsletter / PayPal — ``ext_grantee_profile``
lives on its own dedicated surface (Phase 14b) and never appears in
the operational tab strip.

These tests pin:

  1. Default surface (no surface_query) → 4 tabs visible, ext_aws_email
     is the active tab + the only card in payload.extensions.
  2. surface_query.selected_extension_tool_id=ext_newsletter →
     newsletter is active + the only card rendered.
  3. The subtab's select_action preserves the active
     selected_grantee_msn (cross-axis contract).
  4. The grantee selector's select_action now preserves the active
     selected_extension_tool_id (the reverse cross-axis contract).
  5. ext_grantee_profile is NEVER in the tab list.
  6. Invalid/unknown tool_id falls back to ext_aws_email.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry
from MyCiteV2.packages.core.grantee import GRANTEE_PROFILE_SCHEMA
from MyCiteV2.packages.state_machine.portal_shell import (
    PORTAL_SHELL_REQUEST_SCHEMA,
    UTILITIES_EXTENSIONS_SURFACE_ID,
)


def _seed_grantee(grantee_dir: Path, msn_id: str, label: str, domains: list) -> None:
    grantee_dir.mkdir(parents=True, exist_ok=True)
    (grantee_dir / f"grantee.fnd-msn.{msn_id}.json").write_text(
        json.dumps(
            {
                "schema": GRANTEE_PROFILE_SCHEMA,
                "msn_id": msn_id,
                "label": label,
                "short_name": msn_id,
                "domains": domains,
                "users": [],
            }
        ),
        encoding="utf-8",
    )


def _build_tempdirs() -> tuple[Path, Path, Path, Path]:
    root = Path(tempfile.mkdtemp(prefix="phase15a_subtab_"))
    for sub in ("public", "private", "data", "webapps"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    _seed_grantee(
        root / "private" / "utilities" / "tools" / "fnd-csm",
        "alpha",
        "Alpha Grantee",
        ["alpha.example.test"],
    )
    _seed_grantee(
        root / "private" / "utilities" / "tools" / "fnd-csm",
        "beta",
        "Beta Grantee",
        ["beta.example.test"],
    )
    return root / "public", root / "private", root / "data", root / "webapps"


def _surface_payload(**surface_query) -> dict:
    public_dir, private_dir, data_dir, webapps_root = _build_tempdirs()
    body: dict = {
        "schema": PORTAL_SHELL_REQUEST_SCHEMA,
        "requested_surface_id": UTILITIES_EXTENSIONS_SURFACE_ID,
    }
    if surface_query:
        body["surface_query"] = surface_query
    response = run_portal_shell_entry(
        body,
        portal_instance_id="fnd",
        portal_domain="example.test",
        public_dir=public_dir,
        private_dir=private_dir,
        data_dir=data_dir,
        webapps_root=webapps_root,
    )
    return response.get("surface_payload", {})


class ExtensionSubtabSelectorTests(unittest.TestCase):
    def test_default_surface_lists_6_tabs_with_email_active(self) -> None:
        # Phase 17b adds ext_connect as the 5th tab; Wave 2 adds ext_resources
        # as the 6th (the retired resources.root surface re-homed as an extension).
        payload = _surface_payload()
        selector = payload.get("extension_subtab_selector")
        self.assertIsNotNone(selector, "extension_subtab_selector missing")
        tab_ids = [tab.get("tool_id") for tab in selector.get("tabs") or []]
        self.assertEqual(
            tab_ids,
            [
                "ext_aws_email",
                "ext_analytics",
                "ext_newsletter",
                "ext_paypal",
                "ext_connect",
                "ext_resources",
            ],
        )
        self.assertEqual(selector.get("selected_tool_id"), "ext_aws_email")
        active = [t for t in selector["tabs"] if t.get("active")]
        self.assertEqual([t["tool_id"] for t in active], ["ext_aws_email"])

    def test_only_active_extension_card_in_payload(self) -> None:
        payload = _surface_payload()
        extensions = payload.get("extensions") or []
        tool_ids = [ext.get("tool_id") for ext in extensions]
        self.assertEqual(tool_ids, ["ext_aws_email"])

    def test_explicit_tab_selection_filters_payload(self) -> None:
        payload = _surface_payload(selected_extension_tool_id="ext_newsletter")
        extensions = payload.get("extensions") or []
        self.assertEqual(
            [ext.get("tool_id") for ext in extensions], ["ext_newsletter"]
        )
        selector = payload.get("extension_subtab_selector") or {}
        self.assertEqual(selector.get("selected_tool_id"), "ext_newsletter")
        for tab in selector.get("tabs") or []:
            self.assertEqual(
                tab.get("active"), tab.get("tool_id") == "ext_newsletter"
            )

    def test_tab_select_action_preserves_active_grantee(self) -> None:
        # User on grantee beta, click any tab → select_action keeps beta.
        payload = _surface_payload(
            selected_grantee_msn="beta", selected_extension_tool_id="ext_newsletter"
        )
        selector = payload.get("extension_subtab_selector") or {}
        for tab in selector.get("tabs") or []:
            action_payload = tab["select_action"]["payload"]
            self.assertEqual(
                action_payload["surface_query"]["selected_grantee_msn"], "beta"
            )
            self.assertEqual(
                action_payload["requested_surface_id"],
                UTILITIES_EXTENSIONS_SURFACE_ID,
            )

    def test_grantee_select_action_preserves_active_extension_tab(self) -> None:
        # User on ext_paypal tab, click a grantee → select_action keeps paypal.
        payload = _surface_payload(
            selected_grantee_msn="alpha", selected_extension_tool_id="ext_paypal"
        )
        grantee_selector = payload.get("grantee_selector") or {}
        for grantee in grantee_selector.get("grantees") or []:
            action_payload = grantee["select_action"]["payload"]
            self.assertEqual(
                action_payload["surface_query"]["selected_extension_tool_id"],
                "ext_paypal",
            )

    def test_grantee_profile_extension_never_in_tab_list(self) -> None:
        payload = _surface_payload()
        tab_ids = {tab.get("tool_id") for tab in (payload.get("extension_subtab_selector") or {}).get("tabs") or []}
        self.assertNotIn("ext_grantee_profile", tab_ids)

    def test_invalid_tool_id_falls_back_to_email_default(self) -> None:
        payload = _surface_payload(selected_extension_tool_id="ext_does_not_exist")
        selector = payload.get("extension_subtab_selector") or {}
        self.assertEqual(selector.get("selected_tool_id"), "ext_aws_email")
        self.assertEqual(
            [ext.get("tool_id") for ext in payload.get("extensions") or []],
            ["ext_aws_email"],
        )


if __name__ == "__main__":
    unittest.main()
