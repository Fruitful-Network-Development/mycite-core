"""Postcondition for the GLOBAL ("Overall") vs per-grantee Utilities mode.

The mode mechanism must be ADDITIVE: when a grantee is selected (grantee
mode), the extension render ``ctx`` must be byte-identical to the pre-mode
context PLUS the single additive ``mode`` key — so live email/payment/
newsletter tooling, which reads ``ctx["grantee"]``/``["domain"]``/
``["private_dir"]``, cannot regress. Global mode is a strictly additive
branch: it empties grantee/domain and adds the ``grantees`` roster for
aggregation.

These tests pin:
  * the legacy ctx key set is preserved in grantee mode (+ ``mode`` only);
  * global mode empties grantee/domain and adds ``grantees``;
  * the surface default (Extensions → global, others → grantee);
  * an explicit grantee selection always wins over the default;
  * the grantee_selector always leads with the synthetic "All — Overall"
    entry that engages global mode.
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

from MyCiteV2.instances._shared.runtime.portal_shell_runtime import (
    _build_utilities_surface_context,
)


def _seed_private_with_grantee() -> Path:
    """A temp private_dir holding one grantee JSON the loader can glob."""
    private_dir = Path(tempfile.mkdtemp(prefix="mode_selector_"))
    grantee_dir = private_dir / "utilities" / "tools" / "fnd-csm"
    grantee_dir.mkdir(parents=True)
    (grantee_dir / "grantee.fnd-msn.acme.json").write_text(
        json.dumps(
            {"msn_id": "acme", "label": "Acme", "short_name": "acme", "domains": ["acme.org"]}
        ),
        encoding="utf-8",
    )
    return private_dir

# The ctx keys that existed before the mode mechanism. Grantee mode must
# preserve exactly these, plus the single additive "mode" key, plus the
# per-extension inner-subtab/Browse drill-down state (additive, verbatim from
# surface_query; extensions that ignore these keys render exactly as before).
_LEGACY_CTX_KEYS = frozenset(
    {
        "grantee",
        "domain",
        "private_dir",
        "webapps_root",
        "authority_db_file",
        "portal_instance_id",
    }
)
_INNER_SUBTAB_CTX_KEYS = frozenset(
    {"surface_query", "extension_subtab", "browse_type", "browse_view", "browse_instance"}
)


def _build(*, query=None, default_to_global=False):
    return _build_utilities_surface_context(
        surface_query=query,
        private_dir=None,  # no roster on disk → empty grantee list
        webapps_root="/tmp/webapps",
        authority_db_file=None,
        portal_instance_id="test-instance",
        default_to_global=default_to_global,
    )


class GranteeModeCtxEquality(unittest.TestCase):
    def test_grantee_mode_keys_are_legacy_plus_mode_only(self) -> None:
        ctx = _build(query={"selected_grantee_msn": "acme"})["ctx"]
        self.assertEqual(ctx["mode"], "grantee")
        self.assertEqual(
            set(ctx) - {"mode"} - _INNER_SUBTAB_CTX_KEYS,
            set(_LEGACY_CTX_KEYS),
            "grantee-mode ctx must equal the legacy key set plus 'mode' + inner-subtab state",
        )
        self.assertEqual(
            set(ctx) & _INNER_SUBTAB_CTX_KEYS,
            set(_INNER_SUBTAB_CTX_KEYS),
            "ctx must always carry the additive inner-subtab/Browse state keys",
        )
        self.assertNotIn(
            "grantees", ctx, "grantee mode must NOT carry the aggregation roster"
        )

    def test_grantee_profile_surface_defaults_to_grantee(self) -> None:
        # default_to_global=False (the Grantee-Profile + legacy surfaces).
        ctx = _build(default_to_global=False)["ctx"]
        self.assertEqual(ctx["mode"], "grantee")


class GlobalModeCtx(unittest.TestCase):
    def test_extensions_surface_defaults_to_global(self) -> None:
        bundle = _build(default_to_global=True)
        ctx = bundle["ctx"]
        self.assertEqual(ctx["mode"], "global")
        self.assertEqual(bundle["mode"], "global")
        self.assertEqual(ctx["grantee"], {})
        self.assertEqual(ctx["domain"], "")
        self.assertIn("grantees", ctx)

    def test_explicit_grantee_overrides_global_default(self) -> None:
        ctx = _build(
            query={"selected_grantee_msn": "acme"}, default_to_global=True
        )["ctx"]
        self.assertEqual(ctx["mode"], "grantee")

    def test_explicit_global_mode_query_engages_global(self) -> None:
        ctx = _build(query={"utilities_mode": "global"})["ctx"]
        self.assertEqual(ctx["mode"], "global")


class SelectorShape(unittest.TestCase):
    def _seeded_selector(self, **kw):
        private_dir = _seed_private_with_grantee()
        return _build_utilities_surface_context(
            surface_query=kw.get("query"),
            private_dir=private_dir,
            webapps_root="/tmp/webapps",
            authority_db_file=None,
            portal_instance_id="test-instance",
            default_to_global=kw.get("default_to_global", True),
        )["grantee_selector"]

    def test_selector_leads_with_overall_entry(self) -> None:
        selector = self._seeded_selector()
        first = selector["grantees"][0]
        self.assertTrue(first.get("is_overall"))
        self.assertEqual(first["msn_id"], "")
        self.assertEqual(
            first["select_action"]["payload"]["surface_query"]["utilities_mode"],
            "global",
        )

    def test_overall_entry_active_in_global_mode(self) -> None:
        selector = self._seeded_selector()
        self.assertTrue(selector["grantees"][0].get("active"))
        self.assertEqual(selector["mode"], "global")

    def test_no_overall_entry_when_no_grantees(self) -> None:
        # With no grantees configured the selector list is empty (Overall is
        # meaningless) so the empty-state help text shows instead.
        selector = _build(default_to_global=True)["grantee_selector"]
        self.assertEqual(selector["grantees"], [])


class GlobalRosterViews(unittest.TestCase):
    """In global mode each grantee-scoped extension returns an overall roster
    (additive branch), while per-grantee mode keeps its original payload."""

    def _render(self, tool_id, ctx):
        from MyCiteV2.instances._shared.runtime.utilities_extensions import (
            render_extension,
        )

        return render_extension(tool_id, ctx)

    def test_operational_extensions_render_overall_roster_in_global(self) -> None:
        grantees = [
            {"msn_id": "a", "label": "Alpha", "short_name": "Alpha", "domains": ["a.org"]},
            {"msn_id": "b", "label": "Beta", "domains": ["b.org", "b2.org"]},
        ]
        ctx = {"mode": "global", "grantees": grantees, "private_dir": None}
        for tool_id in (
            "ext_aws_email",
            "ext_analytics",
            "ext_newsletter",
            "ext_paypal",
            "ext_connect",
            "ext_grantee_profile",
        ):
            payload = self._render(tool_id, ctx)
            self.assertTrue(
                payload.get("overall_roster"),
                f"{tool_id} should render an overall roster in global mode",
            )
            self.assertEqual(payload.get("count"), 2)
            labels = {g["label"] for g in payload["grantees"]}
            self.assertEqual(labels, {"Alpha", "Beta"})

    def test_grantee_mode_preserves_original_payload(self) -> None:
        # A grantee-scoped extension in grantee mode does NOT return a roster.
        ctx = {
            "mode": "grantee",
            "grantee": {"msn_id": "a", "label": "Alpha", "domains": ["a.org"]},
            "domain": "a.org",
            "private_dir": None,
        }
        payload = self._render("ext_grantee_profile", ctx)
        self.assertFalse(payload.get("overall_roster"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
