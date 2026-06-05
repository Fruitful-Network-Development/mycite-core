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

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_shell_runtime import (
    _build_utilities_surface_context,
)

# The ctx keys that existed before the mode mechanism. Grantee mode must
# preserve exactly these, plus the single additive "mode" key.
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
            set(ctx) - {"mode"},
            set(_LEGACY_CTX_KEYS),
            "grantee-mode ctx must equal the legacy key set plus only 'mode'",
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
    def test_selector_leads_with_overall_entry(self) -> None:
        selector = _build(default_to_global=True)["grantee_selector"]
        first = selector["grantees"][0]
        self.assertTrue(first.get("is_overall"))
        self.assertEqual(first["msn_id"], "")
        self.assertEqual(
            first["select_action"]["payload"]["surface_query"]["utilities_mode"],
            "global",
        )

    def test_overall_entry_active_in_global_mode(self) -> None:
        selector = _build(default_to_global=True)["grantee_selector"]
        self.assertTrue(selector["grantees"][0].get("active"))
        self.assertEqual(selector["mode"], "global")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
