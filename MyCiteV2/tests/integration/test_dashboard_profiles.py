"""Dashboard RESOURCES tab — read-only Profiles subtab backend.

Covers the two grantee-scoped, READ-ONLY endpoints that power the dashboard
Profiles subtab (the operator's edit path lives elsewhere, under
``/__fnd/resources/profile/save``):

  * ``GET /__fnd/resources/profiles?grantee=<msn>`` — the public profile
    roster the caller may see (cards: slug/display_name/image_url/...), scoped
    to the caller's entity when a token matches, else the full public roster.
  * ``GET /__fnd/resources/profile?grantee=<msn>&slug=<slug>`` — one public,
    in-roster profile's full detail (every field, including empty ones).

The endpoints are grantee-scoped exactly like ``/__fnd/resources/summary``:
a cross-grantee request is rejected (403), a non-public profile never
surfaces, and there is NO write route.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

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
    (fnd_csm / f"grantee.fnd.{msn}.json").write_text(
        json.dumps(
            {
                "schema": GRANTEE_PROFILE_SCHEMA,
                "msn_id": msn,
                "label": short,
                "short_name": short,
                "domains": domains,
                "users": [],
            }
        ),
        encoding="utf-8",
    )


def _seed_profile(profiles_dir: Path, slug, data):
    profiles_dir.mkdir(parents=True, exist_ok=True)
    name = f"0000-00-00.artifact-profile-legal_entity.{slug}.profile.yaml"
    (profiles_dir / name).write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class DashboardProfilesTests(unittest.TestCase):
    def _client(self):
        tmp = Path(tempfile.mkdtemp(prefix="dash_profiles_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        fnd_csm = tmp / "private" / "utilities" / "tools" / "fnd-csm"
        _seed_grantee(fnd_csm, CVCC, "CVCC", ["cvcc.example.test"])
        _seed_grantee(fnd_csm, FND, "FND", ["fnd.example.test"])
        profiles = tmp / "webapps" / "clients" / "_shared" / "site-core" / "profiles"
        _seed_profile(
            profiles,
            "bloom_hill_farm",
            {
                "public": True,
                "display_name": "Bloom Hill Farm",
                "entity_type": "farm",
                "website": "https://bloomhillfarm.example",
                "email": None,
            },
        )
        _seed_profile(
            profiles,
            "anna_dean_farm",
            {"public": True, "display_name": "Anna-Dean Farm", "phone": None},
        )
        # A non-public profile must never surface to a grantee.
        _seed_profile(
            profiles,
            "secret_entity",
            {"public": False, "display_name": "Secret Entity"},
        )
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain="example.test",
            webapps_root=tmp / "webapps",
        )
        return create_app(config).test_client()

    def test_roster_is_public_only(self) -> None:
        resp = self._client().get(
            "/__fnd/resources/profiles", headers={"X-Auth-Request-Grantee": CVCC}
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        body = resp.get_json()
        self.assertTrue(body["ok"])
        slugs = {p["slug"] for p in body["profiles"]}
        self.assertIn("bloom_hill_farm", slugs)
        self.assertIn("anna_dean_farm", slugs)
        self.assertNotIn("secret_entity", slugs)  # non-public never surfaces
        # Cards carry the contact-app fields the UI renders.
        card = next(p for p in body["profiles"] if p["slug"] == "bloom_hill_farm")
        for key in ("display_name", "image_url", "subtitle"):
            self.assertIn(key, card)

    def test_detail_returns_all_fields_including_empty(self) -> None:
        resp = self._client().get(
            "/__fnd/resources/profile?slug=bloom_hill_farm",
            headers={"X-Auth-Request-Grantee": CVCC},
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        body = resp.get_json()
        self.assertTrue(body["ok"])
        fields = {f["key"]: f["value"] for f in body["profile"]["fields"]}
        self.assertEqual(fields["display_name"], "Bloom Hill Farm")
        self.assertIn("email", fields)  # empty field still present
        self.assertEqual(fields["email"], "")  # rendered as empty, not dropped

    def test_detail_for_non_public_is_404(self) -> None:
        resp = self._client().get(
            "/__fnd/resources/profile?slug=secret_entity",
            headers={"X-Auth-Request-Grantee": CVCC},
        )
        self.assertEqual(resp.status_code, 404, resp.get_data(as_text=True))
        self.assertEqual(resp.get_json()["error"], "profile_not_found")

    def test_detail_requires_slug(self) -> None:
        resp = self._client().get(
            "/__fnd/resources/profile", headers={"X-Auth-Request-Grantee": CVCC}
        )
        self.assertEqual(resp.status_code, 400, resp.get_data(as_text=True))
        self.assertEqual(resp.get_json()["error"], "slug_required")

    def test_cross_grantee_request_rejected(self) -> None:
        resp = self._client().get(
            "/__fnd/resources/profiles?grantee=" + FND,
            headers={"X-Auth-Request-Grantee": CVCC},
        )
        self.assertEqual(resp.status_code, 403, resp.get_data(as_text=True))
        self.assertEqual(resp.get_json()["error"], "scope_mismatch")

    def test_no_write_route(self) -> None:
        # The dashboard Profiles subtab is read-only: POST is not allowed.
        resp = self._client().post(
            "/__fnd/resources/profiles", headers={"X-Auth-Request-Grantee": CVCC}
        )
        self.assertEqual(resp.status_code, 405, resp.get_data(as_text=True))

    def test_operator_only_resource_mutations_blocked_for_grantees(self) -> None:
        # The per-grantee /dashboard/api/ proxy forwards every /__fnd/* path, so
        # operator-only resource-mutation routes must reject a non-operator
        # grantee caller (X-Auth-Request-Grantee != operator) — otherwise a
        # dashboard-cred client could edit the shared type manifest or another
        # grantee's assets/profiles.
        client = self._client()
        for path in (
            "/__fnd/resources/profile/save",
            "/__fnd/resources/manifest/set-icon-ref",
            "/__fnd/resources/asset/delete",
            # grantee/save takes msn_id from the BODY and rewrites that grantee's
            # config (PayPal client_secret, SES, …) — must be operator-only or a
            # dashboard-cred client could tamper with any grantee cross-tenant.
            "/__fnd/grantee/save",
        ):
            resp = client.post(
                path, headers={"X-Auth-Request-Grantee": CVCC}, json={}
            )
            self.assertEqual(resp.status_code, 403, f"{path}: {resp.get_data(as_text=True)}")
            self.assertEqual(resp.get_json().get("error"), "operator_only", path)


if __name__ == "__main__":
    unittest.main()
