"""Integration test for the Phase 8 paypal-webhook sidecar backcompat path.

Per grantee_profile_contract.md, the runtime's _load_grantee_profiles
hydrates a profile's paypal sub-config from the legacy
paypal-webhook.{msn_id}.json sidecar when the grantee JSON itself lacks
the inline `paypal` block. The on-disk grantee JSON is not modified by
the read path; sidecar deprecation completes when an operator edits the
profile through the Phase 9 form.

This test exercises the runtime helper rather than a Flask round-trip
because the read path is the hard part — the sidecar policy lives there.
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

from MyCiteV2.instances._shared.runtime.operational_store import load_grantee_profiles
from MyCiteV2.packages.core.grantee import GRANTEE_PROFILE_SCHEMA


def _seed_grantee(dir_path: Path, msn_id: str, *, with_paypal: bool = False) -> None:
    payload = {
        "schema": GRANTEE_PROFILE_SCHEMA,
        "msn_id": msn_id,
        "label": f"Grantee {msn_id}",
        "short_name": msn_id,
        "domains": ["example.org"],
        "users": ["alice@example.org"],
    }
    if with_paypal:
        payload["paypal"] = {
            "webhook_url": "https://example.org/inline",
            "client_id": "",
            "client_secret": "",
            "environment": "sandbox",
        }
    dest = dir_path / f"grantee.fnd-msn.{msn_id}.json"
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _seed_sidecar(dir_path: Path, msn_id: str, webhook_url: str) -> None:
    sidecar = dir_path / f"paypal-webhook.{msn_id}.json"
    sidecar.write_text(json.dumps({"webhook_url": webhook_url}), encoding="utf-8")


class SidecarBackcompatTests(unittest.TestCase):
    def _build_tree(self) -> tuple[Path, Path]:
        root = Path(tempfile.mkdtemp(prefix="phase8_sidecar_"))
        fnd_csm = root / "utilities" / "tools" / "fnd-csm"
        fnd_csm.mkdir(parents=True, exist_ok=True)
        return root, fnd_csm

    def test_sidecar_hydrates_paypal_when_grantee_json_lacks_it(self) -> None:
        private_dir, fnd_csm = self._build_tree()
        _seed_grantee(fnd_csm, msn_id="g1", with_paypal=False)
        _seed_sidecar(fnd_csm, "g1", "https://example.org/sidecar")

        profiles = load_grantee_profiles(private_dir)
        self.assertEqual(len(profiles), 1)
        paypal = profiles[0].get("paypal") or {}
        self.assertEqual(paypal.get("webhook_url"), "https://example.org/sidecar")

    def test_grantee_inline_paypal_wins_over_sidecar(self) -> None:
        private_dir, fnd_csm = self._build_tree()
        _seed_grantee(fnd_csm, msn_id="g2", with_paypal=True)
        _seed_sidecar(fnd_csm, "g2", "https://example.org/sidecar")

        profiles = load_grantee_profiles(private_dir)
        self.assertEqual(len(profiles), 1)
        paypal = profiles[0].get("paypal") or {}
        # Inline grantee.paypal.webhook_url stays; sidecar is ignored when
        # the inline sub-config is present (Phase 8 precedence).
        self.assertEqual(paypal.get("webhook_url"), "https://example.org/inline")

    def test_no_sidecar_no_inline_yields_no_paypal_key(self) -> None:
        private_dir, fnd_csm = self._build_tree()
        _seed_grantee(fnd_csm, msn_id="g3", with_paypal=False)

        profiles = load_grantee_profiles(private_dir)
        self.assertEqual(len(profiles), 1)
        self.assertNotIn("paypal", profiles[0])

    def test_invalid_sidecar_is_ignored(self) -> None:
        private_dir, fnd_csm = self._build_tree()
        _seed_grantee(fnd_csm, msn_id="g4", with_paypal=False)
        # Malformed sidecar (not JSON) must not crash the loader.
        (fnd_csm / "paypal-webhook.g4.json").write_text("{ not json", encoding="utf-8")

        profiles = load_grantee_profiles(private_dir)
        self.assertEqual(len(profiles), 1)
        self.assertNotIn("paypal", profiles[0])

    def test_loader_returns_dicts_with_expected_keys(self) -> None:
        # The loader's contract is that downstream code (which still uses
        # dict access — grantee.get("domains") etc.) keeps working.
        private_dir, fnd_csm = self._build_tree()
        _seed_grantee(fnd_csm, msn_id="g5", with_paypal=False)

        profiles = load_grantee_profiles(private_dir)
        self.assertEqual(len(profiles), 1)
        p = profiles[0]
        self.assertIsInstance(p, dict)
        self.assertEqual(p["msn_id"], "g5")
        self.assertEqual(p["domains"], ["example.org"])
        self.assertEqual(p["users"], ["alice@example.org"])

    def test_production_grantees_load_unchanged(self) -> None:
        # Smoke: the three production grantees load cleanly via the runtime
        # path. None of them currently has paypal/aws_ses/newsletter so they
        # round-trip through the schema without surfacing those keys.
        production = Path("/srv/webapps/mycite/fnd/private")
        if not (production / "utilities" / "tools" / "fnd-csm").exists():
            self.skipTest("production grantee directory not present")
        profiles = load_grantee_profiles(production)
        self.assertGreaterEqual(len(profiles), 1)
        for p in profiles:
            self.assertIn("msn_id", p)
            self.assertIn("label", p)


if __name__ == "__main__":
    unittest.main()
