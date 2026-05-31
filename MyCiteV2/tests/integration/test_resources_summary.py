"""RESOURCES tab backend: /__fnd/resources/summary is grantee-scoped and reads
only the caller's own site manifests."""

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
    from MyCiteV2.packages.core.grantee import GRANTEE_PROFILE_SCHEMA

CVCC = "3-2-3-17-77-3-6-1-1-2"
FND = "3-2-3-17-77-1-6-4-1-4"


def _seed_grantee(fnd_csm: Path, msn, short, domains):
    fnd_csm.mkdir(parents=True, exist_ok=True)
    (fnd_csm / f"grantee.fnd.{msn}.json").write_text(json.dumps({
        "schema": GRANTEE_PROFILE_SCHEMA, "msn_id": msn, "label": short,
        "short_name": short, "domains": domains, "users": [],
    }), encoding="utf-8")


def _seed_manifest(clients_root: Path, domain, kind, entries):
    d = clients_root / domain / "frontend" / "assets"
    d.mkdir(parents=True, exist_ok=True)
    lines = [f"manifest_kind: {kind}_use", f"site_domain: {domain}", "entries:"]
    for e in entries:
        lines.append(f"- asset_id: {e}")
        lines.append(f"  asset_path: /assets/{kind}s/{e}.x")
        lines.append("  consumers: []")
    (d / f"0000-00-00.record-manifest.x-website.{kind}_use.yaml").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class ResourcesSummaryTests(unittest.TestCase):
    def _client(self):
        tmp = Path(tempfile.mkdtemp(prefix="resources_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        fnd_csm = tmp / "private" / "utilities" / "tools" / "fnd-csm"
        _seed_grantee(fnd_csm, CVCC, "CVCC", ["cvcc.example.test"])
        _seed_grantee(fnd_csm, FND, "FND", ["fnd.example.test"])
        clients = tmp / "webapps" / "clients"
        _seed_manifest(clients, "cvcc.example.test", "image", ["cvcc_logo", "cvcc_hero"])
        _seed_manifest(clients, "fnd.example.test", "image", ["fnd_secret"])
        config = V2PortalHostConfig(
            portal_instance_id="fnd", public_dir=tmp / "public", private_dir=tmp / "private",
            data_dir=tmp / "data", portal_domain="example.test", webapps_root=tmp / "webapps",
        )
        return create_app(config).test_client()

    def test_returns_only_own_assets(self) -> None:
        resp = self._client().get(
            "/__fnd/resources/summary", headers={"X-Auth-Request-Grantee": CVCC}
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        body = resp.get_json()
        ids = {a["asset_id"] for a in body["resources"]["images"]}
        self.assertEqual(ids, {"cvcc_logo", "cvcc_hero"})
        self.assertNotIn("fnd_secret", ids)  # never another site's assets
        self.assertEqual(body["counts"]["images"], 2)

    def test_cross_grantee_request_rejected(self) -> None:
        resp = self._client().get(
            "/__fnd/resources/summary?grantee=" + FND,
            headers={"X-Auth-Request-Grantee": CVCC},
        )
        self.assertEqual(resp.status_code, 403, resp.get_data(as_text=True))
        self.assertEqual(resp.get_json()["error"], "scope_mismatch")


if __name__ == "__main__":
    unittest.main()
