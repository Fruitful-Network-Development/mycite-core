"""Regression: /__fnd/tolling/overview is operator-only.

It returns EVERY grantee's AWS costs + the full grantee roster, and is reachable
through the per-grantee /dashboard/api/ proxy (which injects the caller's
X-Auth-Request-Grantee header). A scoped (client) caller must be rejected; the
operator (header-absent surface, or the FND operator msn) is not.

The 403 path short-circuits before any AWS Cost Explorer call, so this test is
deterministic without mocking the peripheral.
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

OPERATOR_MSN = "3-2-3-17-77-1-6-4-1-4"  # FND, == OPERATOR_MSN_ID
CLIENT_MSN = "3-2-3-17-77-3-6-1-1-2"    # CVCC


def _seed_grantee(fnd_csm_dir: Path, msn_id: str, short_name: str, domains) -> None:
    fnd_csm_dir.mkdir(parents=True, exist_ok=True)
    (fnd_csm_dir / f"grantee.fnd.{msn_id}.json").write_text(
        json.dumps({
            "msn_id": msn_id,
            "short_name": short_name,
            "label": short_name,
            "domains": list(domains),
        }),
        encoding="utf-8",
    )


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class TollingOverviewScopeTests(unittest.TestCase):
    def _client(self):
        tmp = Path(tempfile.mkdtemp(prefix="tolling_overview_scope_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        fnd_csm = tmp / "private" / "utilities" / "tools" / "fnd-csm"
        _seed_grantee(fnd_csm, OPERATOR_MSN, "FND", ["fruitfulnetworkdevelopment.com"])
        _seed_grantee(fnd_csm, CLIENT_MSN, "CVCC", ["cvccboard.org"])
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain="example.test",
            webapps_root=tmp / "webapps",
        )
        return create_app(config).test_client()

    def test_client_grantee_header_is_rejected(self) -> None:
        resp = self._client().get(
            "/__fnd/tolling/overview",
            headers={"X-Auth-Request-Grantee": CLIENT_MSN},
        )
        self.assertEqual(resp.status_code, 403, resp.get_data(as_text=True))
        self.assertEqual(resp.get_json()["error"], "operator_only")

    def test_operator_header_is_not_gate_blocked(self) -> None:
        # The FND operator msn passes the gate (it may then 5xx on the AWS Cost
        # Explorer call in a credential-less test env — that's fine; we only
        # assert the operator is NOT rejected by the operator_only gate).
        resp = self._client().get(
            "/__fnd/tolling/overview",
            headers={"X-Auth-Request-Grantee": OPERATOR_MSN},
        )
        self.assertNotEqual(resp.status_code, 403, resp.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
