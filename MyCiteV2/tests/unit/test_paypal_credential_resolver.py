"""Unit tests for the PayPal credential resolver + base-URL bug fix.

Covers:
  - ``_paypal_base_url`` recognizes both ``"live"`` and ``"production"``
    as the live endpoint (PaypalConfig only allows sandbox|live, so the
    pre-fix function silently routed ``live`` to sandbox).
  - ``_resolve_paypal_credentials_for_domain`` precedence:
      grantee.paypal (full creds) → env-var fallback → None.
  - Partial grantee creds (id only or secret only) fall through to env,
    do not 503 with empty values.
  - ``grantee.paypal.environment`` overrides the domain-profile environment.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.portal_host.app import (  # noqa: E402
    _paypal_base_url,
    _resolve_paypal_credentials_for_domain,
)


def _seed_grantee(private_dir: Path, *, domain: str, paypal: dict | None) -> None:
    fnd_csm = private_dir / "utilities" / "tools" / "fnd-csm"
    fnd_csm.mkdir(parents=True, exist_ok=True)
    payload: dict = {
        "schema": "mycite.v2.grantee.profile.v1",
        "msn_id": "test-grantee",
        "label": "Test Grantee",
        "short_name": "TG",
        "domains": [domain],
        "users": [],
    }
    if paypal is not None:
        payload["paypal"] = paypal
    (fnd_csm / "grantee.fnd.test-grantee.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


class TestPaypalBaseUrl(unittest.TestCase):
    def test_sandbox_returns_sandbox_url(self) -> None:
        self.assertEqual(_paypal_base_url("sandbox"), "https://api-m.sandbox.paypal.com")

    def test_empty_returns_sandbox_url(self) -> None:
        self.assertEqual(_paypal_base_url(""), "https://api-m.sandbox.paypal.com")

    def test_unknown_value_returns_sandbox_url(self) -> None:
        self.assertEqual(_paypal_base_url("staging"), "https://api-m.sandbox.paypal.com")

    def test_live_returns_production_url(self) -> None:
        # Latent bug fix: PaypalConfig.environment ∈ {sandbox, live} only,
        # but the pre-fix function only mapped "production" to live URL.
        self.assertEqual(_paypal_base_url("live"), "https://api-m.paypal.com")

    def test_production_still_returns_production_url(self) -> None:
        # Backwards compatibility: legacy callers may still pass "production".
        self.assertEqual(_paypal_base_url("production"), "https://api-m.paypal.com")

    def test_case_insensitive(self) -> None:
        self.assertEqual(_paypal_base_url("LIVE"), "https://api-m.paypal.com")
        self.assertEqual(_paypal_base_url("Production"), "https://api-m.paypal.com")


class TestResolvePaypalCredentialsForDomain(unittest.TestCase):
    DOMAIN = "test-grantee.example.test"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="paypal_resolver_")
        self.private_dir = Path(self._tmp.name)
        # Clear env so each test starts from a known state.
        for key in ("PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET"):
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        self._tmp.cleanup()
        for key in ("PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET"):
            os.environ.pop(key, None)

    def _tenant(self) -> dict:
        return {"credentials_ref": "1"}

    def test_grantee_creds_win_over_env(self) -> None:
        _seed_grantee(
            self.private_dir,
            domain=self.DOMAIN,
            paypal={
                "client_id": "grantee_id",
                "client_secret": "grantee_secret",
                "environment": "live",
            },
        )
        os.environ["PAYPAL_CLIENT_ID"] = "env_id"
        os.environ["PAYPAL_CLIENT_SECRET"] = "env_secret"

        result = _resolve_paypal_credentials_for_domain(
            self.private_dir, self.DOMAIN, self._tenant()
        )
        self.assertEqual(result, ("grantee_id", "grantee_secret", "live"))

    def test_falls_through_to_env_when_no_grantee(self) -> None:
        # No grantee JSON seeded.
        os.environ["PAYPAL_CLIENT_ID"] = "env_id"
        os.environ["PAYPAL_CLIENT_SECRET"] = "env_secret"
        result = _resolve_paypal_credentials_for_domain(
            self.private_dir, self.DOMAIN, self._tenant()
        )
        self.assertEqual(result, ("env_id", "env_secret", ""))

    def test_partial_grantee_creds_id_only_falls_through(self) -> None:
        _seed_grantee(
            self.private_dir,
            domain=self.DOMAIN,
            paypal={"client_id": "grantee_id", "client_secret": "", "environment": "sandbox"},
        )
        os.environ["PAYPAL_CLIENT_ID"] = "env_id"
        os.environ["PAYPAL_CLIENT_SECRET"] = "env_secret"
        result = _resolve_paypal_credentials_for_domain(
            self.private_dir, self.DOMAIN, self._tenant()
        )
        # Falls through to env — does not 503 with empty grantee secret.
        self.assertEqual(result, ("env_id", "env_secret", ""))

    def test_partial_grantee_creds_secret_only_falls_through(self) -> None:
        _seed_grantee(
            self.private_dir,
            domain=self.DOMAIN,
            paypal={"client_id": "", "client_secret": "grantee_secret", "environment": "sandbox"},
        )
        os.environ["PAYPAL_CLIENT_ID"] = "env_id"
        os.environ["PAYPAL_CLIENT_SECRET"] = "env_secret"
        result = _resolve_paypal_credentials_for_domain(
            self.private_dir, self.DOMAIN, self._tenant()
        )
        self.assertEqual(result, ("env_id", "env_secret", ""))

    def test_empty_grantee_paypal_and_no_env_returns_none(self) -> None:
        _seed_grantee(
            self.private_dir,
            domain=self.DOMAIN,
            paypal={"client_id": "", "client_secret": "", "environment": "sandbox"},
        )
        result = _resolve_paypal_credentials_for_domain(
            self.private_dir, self.DOMAIN, self._tenant()
        )
        self.assertIsNone(result)

    def test_unknown_domain_falls_through_to_env(self) -> None:
        _seed_grantee(
            self.private_dir,
            domain="someone-else.example",
            paypal={
                "client_id": "grantee_id",
                "client_secret": "grantee_secret",
                "environment": "live",
            },
        )
        os.environ["PAYPAL_CLIENT_ID"] = "env_id"
        os.environ["PAYPAL_CLIENT_SECRET"] = "env_secret"
        result = _resolve_paypal_credentials_for_domain(
            self.private_dir, "different.example.test", self._tenant()
        )
        # Unknown domain → no grantee match → env fallback.
        self.assertEqual(result, ("env_id", "env_secret", ""))

    def test_grantee_environment_override_defaults_sandbox(self) -> None:
        _seed_grantee(
            self.private_dir,
            domain=self.DOMAIN,
            paypal={"client_id": "grantee_id", "client_secret": "grantee_secret"},
        )
        result = _resolve_paypal_credentials_for_domain(
            self.private_dir, self.DOMAIN, self._tenant()
        )
        # Missing environment → defaults to sandbox.
        self.assertEqual(result, ("grantee_id", "grantee_secret", "sandbox"))


if __name__ == "__main__":
    unittest.main()
