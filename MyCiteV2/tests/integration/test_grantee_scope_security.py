"""Security regression for the Phase-D cross-grantee management gate.

Cross-grantee read/write (and the /__fnd/grantees/list roster) is operator-only,
AND the operator may be asserted ONLY via the TRUSTED nginx-set
X-Auth-Request-Grantee header — never a client-spoofable X-Auth-Request-Groups /
X-Portal-Roles. A code-review (2026-06-26) found that trusting the group header
let any basic-auth dashboard client spoof `operator` and hijack another grantee's
PayPal config; this test guards that it can't recur.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None
if FLASK_AVAILABLE:
    from MyCiteV2.instances._shared.portal_host.app import V2PortalHostConfig, create_app

OPERATOR_MSN = "3-2-3-17-77-1-6-4-1-4"  # FND
CLIENT_MSN = "3-2-3-17-77-3-6-1-1-2"    # CVCC


def _seed(fnd_csm: Path, msn: str, short: str, domains) -> None:
    fnd_csm.mkdir(parents=True, exist_ok=True)
    (fnd_csm / f"grantee.fnd.{msn}.json").write_text(
        json.dumps({"msn_id": msn, "short_name": short, "label": short, "domains": list(domains)}),
        encoding="utf-8",
    )


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class GranteeScopeSecurityTests(unittest.TestCase):
    def _client(self):
        tmp = Path(tempfile.mkdtemp(prefix="grantee_scope_sec_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        fnd_csm = tmp / "private" / "utilities" / "tools" / "fnd-csm"
        _seed(fnd_csm, OPERATOR_MSN, "FND", ["fruitfulnetworkdevelopment.com"])
        _seed(fnd_csm, CLIENT_MSN, "CVCC", ["cvccboard.org"])
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain="example.test",
            webapps_root=tmp / "webapps",
        )
        return create_app(config).test_client()

    # --- /__fnd/grantees/list (operator-only roster) ---
    def test_operator_lists_all(self) -> None:
        r = self._client().get("/__fnd/grantees/list", headers={"X-Auth-Request-Grantee": OPERATOR_MSN})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual({g["short_name"] for g in r.get_json()["grantees"]}, {"FND", "CVCC"})

    def test_client_cannot_list(self) -> None:
        r = self._client().get("/__fnd/grantees/list", headers={"X-Auth-Request-Grantee": CLIENT_MSN})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.get_json()["error"], "operator_only")

    def test_spoofed_group_header_cannot_list(self) -> None:
        for hdr in ({"X-Auth-Request-Groups": "admin"}, {"X-Portal-Roles": "operator"}):
            r = self._client().get("/__fnd/grantees/list", headers=hdr)
            self.assertEqual(r.status_code, 403, hdr)

    def test_client_plus_spoofed_group_cannot_escalate_list(self) -> None:
        r = self._client().get(
            "/__fnd/grantees/list",
            headers={"X-Auth-Request-Grantee": CLIENT_MSN, "X-Auth-Request-Groups": "operator"},
        )
        self.assertEqual(r.status_code, 403)

    # --- cross-grantee scope on a scoped route (PayPal admin config) ---
    def test_client_cannot_cross_grantee(self) -> None:
        r = self._client().get(
            f"/__fnd/paypal/admin/config?grantee={OPERATOR_MSN}",
            headers={"X-Auth-Request-Grantee": CLIENT_MSN},
        )
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.get_json()["error"], "scope_mismatch")

    def test_client_plus_spoofed_group_cannot_cross_grantee(self) -> None:
        r = self._client().get(
            f"/__fnd/paypal/admin/config?grantee={OPERATOR_MSN}",
            headers={"X-Auth-Request-Grantee": CLIENT_MSN, "X-Auth-Request-Groups": "operator"},
        )
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.get_json()["error"], "scope_mismatch")

    def test_operator_may_cross_grantee(self) -> None:
        r = self._client().get(
            f"/__fnd/paypal/admin/config?grantee={CLIENT_MSN}",
            headers={"X-Auth-Request-Grantee": OPERATOR_MSN},
        )
        self.assertNotEqual(r.status_code, 403, r.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
