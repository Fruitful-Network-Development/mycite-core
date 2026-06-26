"""Grantee leaflet cutover — shared identity leaflet + admin-only secret merge.

Guards the MYCITE_GRANTEE_LEAFLETS cutover: when enabled, grantee identity is
read from clients/_shared/site-core/grantee and PayPal/AWS secrets are merged
from clients/_shared/dashboard-admin/grantee; when off, the loader is untouched.
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from MyCiteV2.instances._shared.runtime import operational_store as ostore
from MyCiteV2.instances._shared.runtime.utilities_extensions import tolling

IDENTITY = {
    "schema": "mycite.v2.grantee.profile.v1",
    "msn_id": "9-9-9-test",
    "label": "Acme Test",
    "short_name": "ACME",
    "domains": ["acme.example"],
    "users": ["ops@acme.example"],
    "newsletter": {
        "selected_sender_address": "news@acme.example",
        "sender_display_name": "Acme",
        "reply_to": "ops@acme.example",
    },
}
SECRETS = {
    "schema": "mycite.v2.grantee.secrets.v1",
    "msn_id": "9-9-9-test",
    "short_name": "ACME",
    "paypal": {"client_id": "cid", "client_secret": "shh", "environment": "live", "mode": "rest"},
    "aws_ses": {
        "region": "us-east-1",
        "identity": "ops@acme.example",
        "smtp_username": "u",
        "smtp_password": "p",
    },
}


class GranteeLeafletCutoverTest(unittest.TestCase):
    def setUp(self) -> None:
        self._env = {k: os.environ.get(k) for k in ("MYCITE_WEBAPPS_ROOT", "MYCITE_GRANTEE_LEAFLETS")}
        self._tmp = TemporaryDirectory()
        root = Path(self._tmp.name)
        id_dir = root / "clients" / "_shared" / "site-core" / "grantee"
        sec_dir = root / "clients" / "_shared" / "dashboard-admin" / "grantee"
        id_dir.mkdir(parents=True)
        sec_dir.mkdir(parents=True)
        (id_dir / "0000-00-00.artifact-grantee-profile.acme.grantee_profile.yaml").write_text(
            yaml.safe_dump(IDENTITY, sort_keys=False), encoding="utf-8"
        )
        (sec_dir / "grantee.acme.secrets.yaml").write_text(
            yaml.safe_dump(SECRETS, sort_keys=False), encoding="utf-8"
        )
        os.environ["MYCITE_WEBAPPS_ROOT"] = str(root)
        ostore._GRANTEE_PROFILES_CACHE.clear()
        tolling.clear_caches()

    def tearDown(self) -> None:
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        ostore._GRANTEE_PROFILES_CACHE.clear()
        tolling.clear_caches()
        self._tmp.cleanup()

    def test_flag_off_ignores_leaflets(self) -> None:
        os.environ.pop("MYCITE_GRANTEE_LEAFLETS", None)
        self.assertIsNone(ostore.load_grantee_leaflets_if_enabled())
        # With the flag off and no legacy private_dir, the loader returns nothing.
        self.assertEqual(ostore.load_grantee_profiles(None), [])

    def test_flag_on_merges_identity_and_secrets(self) -> None:
        os.environ["MYCITE_GRANTEE_LEAFLETS"] = "1"
        ostore._GRANTEE_PROFILES_CACHE.clear()
        profiles = ostore.load_grantee_profiles(None)
        self.assertEqual(len(profiles), 1)
        profile = profiles[0]
        self.assertEqual(profile["msn_id"], "9-9-9-test")
        self.assertEqual(profile["short_name"], "ACME")
        self.assertEqual(profile["domains"], ["acme.example"])
        # Secret sub-configs are merged in from the admin-only sidecar.
        self.assertEqual(profile["paypal"]["client_secret"], "shh")
        self.assertEqual(profile["aws_ses"]["smtp_password"], "p")

    def test_secrets_never_in_identity_leaflet(self) -> None:
        # The on-disk identity leaflet must not carry any secret sub-config.
        root = Path(os.environ["MYCITE_WEBAPPS_ROOT"])
        leaflet = root / "clients" / "_shared" / "site-core" / "grantee" / "0000-00-00.artifact-grantee-profile.acme.grantee_profile.yaml"
        on_disk = yaml.safe_load(leaflet.read_text(encoding="utf-8"))
        self.assertNotIn("paypal", on_disk)
        self.assertNotIn("aws_ses", on_disk)

    def test_tolling_delegates_when_enabled(self) -> None:
        os.environ["MYCITE_GRANTEE_LEAFLETS"] = "1"
        tolling.clear_caches()
        ostore._GRANTEE_PROFILES_CACHE.clear()
        directory = tolling.load_grantee_directory()
        self.assertEqual([g["msn_id"] for g in directory], ["9-9-9-test"])
        resolved = tolling.grantee_for_domain("acme.example")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["short_name"], "ACME")


    def test_persist_splits_identity_and_secrets(self) -> None:
        os.environ["MYCITE_GRANTEE_LEAFLETS"] = "1"
        ostore._GRANTEE_PROFILES_CACHE.clear()
        from MyCiteV2.packages.core.grantee.schema import AwsSesConfig, GranteeProfile, PaypalConfig

        prof = GranteeProfile(
            msn_id="7-7-7-new",
            label="New Co",
            short_name="NEW",
            domains=("new.example",),
            users=("ops@new.example",),
            paypal=PaypalConfig(client_id="cid", client_secret="zzz", environment="live", mode="rest"),
            aws_ses=AwsSesConfig(region="us-east-1", identity="ops@new.example", smtp_username="su", smtp_password="sp"),
        )
        root = Path(os.environ["MYCITE_WEBAPPS_ROOT"])
        ostore.persist_grantee_profile(prof, legacy_path=root / "unused" / "grantee.x.7-7-7-new.yaml")

        id_file = root / "clients" / "_shared" / "site-core" / "grantee" / "0000-00-00.artifact-grantee-profile.new.grantee_profile.yaml"
        sec_file = root / "clients" / "_shared" / "dashboard-admin" / "grantee" / "grantee.new.secrets.yaml"
        self.assertTrue(id_file.exists())
        self.assertTrue(sec_file.exists())
        on_id = yaml.safe_load(id_file.read_text(encoding="utf-8"))
        on_sec = yaml.safe_load(sec_file.read_text(encoding="utf-8"))
        # Identity leaflet carries NO secrets; the sidecar carries them.
        self.assertNotIn("paypal", on_id)
        self.assertNotIn("aws_ses", on_id)
        self.assertEqual(on_sec["paypal"]["client_secret"], "zzz")
        self.assertEqual(on_sec["aws_ses"]["smtp_password"], "sp")
        # Secret sidecar stays 0600.
        self.assertEqual(oct(os.stat(sec_file).st_mode & 0o777), "0o600")
        # Round-trips through the resolved read with secrets merged back.
        ostore._GRANTEE_PROFILES_CACHE.clear()
        loaded = ostore.load_grantee_profile_resolved("7-7-7-new", legacy_path=root / "unused" / "x.yaml")
        self.assertEqual(loaded.paypal.client_secret, "zzz")
        self.assertEqual(loaded.aws_ses.smtp_password, "sp")
        self.assertEqual(loaded.domains, ("new.example",))

    def test_persist_legacy_when_flag_off(self) -> None:
        os.environ.pop("MYCITE_GRANTEE_LEAFLETS", None)
        from MyCiteV2.packages.core.grantee import load_grantee_profile
        from MyCiteV2.packages.core.grantee.schema import GranteeProfile

        prof = GranteeProfile(msn_id="5-5-5", label="Legacy", short_name="LEG", domains=("leg.example",), users=())
        legacy = Path(self._tmp.name) / "legacy" / "grantee.op.5-5-5.json"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        ostore.persist_grantee_profile(prof, legacy_path=legacy)
        written = legacy.with_suffix(".yaml")
        self.assertTrue(written.exists())
        self.assertEqual(load_grantee_profile(written).short_name, "LEG")


if __name__ == "__main__":
    unittest.main()
