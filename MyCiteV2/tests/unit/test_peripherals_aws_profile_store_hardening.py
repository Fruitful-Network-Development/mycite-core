"""Profile-store hardening: schema/role drift validator (fail-safe role
coercion) + atomic write with .bak backup.

These pin the two Tier-1 storage fixes:
  * Fix 6 — an unknown ``identity.role`` is coerced to "" (operator-only) on
    read, so v1/v2/role drift can never be mistaken for a grantee-manageable
    "user" alias (the escalation-hole class).
  * Fix 11 — ``save_profile`` writes atomically (temp + os.replace) and keeps a
    single ``.bak`` of the prior version; the .bak is not picked up by the
    profile glob.
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

from MyCiteV2.packages.peripherals.aws.profile_store import (
    ProfileStore,
    validate_profile_record,
)


def _profile(role: str, schema: str = "mycite.service_tool.aws.profile.v2") -> dict:
    return {
        "schema": schema,
        "identity": {
            "profile_id": "aws-csm.t.box",
            "domain": "x.test",
            "role": role,
            "mailbox_local_part": "box",
        },
    }


class ValidateProfileRecordTests(unittest.TestCase):
    def test_clean_profile_has_no_issues(self) -> None:
        self.assertEqual(validate_profile_record(_profile("user")), [])

    def test_unknown_role_and_schema_flagged(self) -> None:
        issues = validate_profile_record(_profile("superadmin", schema="weird.v9"))
        self.assertIn("unknown_role:superadmin", issues)
        self.assertIn("unknown_schema:weird.v9", issues)

    def test_known_operator_roles_clean(self) -> None:
        for role in ("user", "operator", "technical_contact", "role", ""):
            self.assertEqual(
                validate_profile_record(_profile(role)), [], f"role={role!r}"
            )


class ProfileStoreHardeningTests(unittest.TestCase):
    def _store(self):
        d = Path(tempfile.mkdtemp(prefix="aws_csm_hardening_"))
        return ProfileStore(root=d), d

    def test_unknown_role_coerced_to_empty_on_read(self) -> None:
        store, d = self._store()
        (d / "aws-csm.t.box.json").write_text(
            json.dumps(_profile("superadmin")), encoding="utf-8"
        )
        prof = store.get_profile("aws-csm.t.box")
        self.assertIsNotNone(prof)
        # Fail-safe: a drifted role reads back as "" — never grantee-manageable.
        self.assertEqual((prof.get("identity") or {}).get("role"), "")

    def test_known_role_preserved(self) -> None:
        store, d = self._store()
        (d / "aws-csm.t.box.json").write_text(
            json.dumps(_profile("operator")), encoding="utf-8"
        )
        prof = store.get_profile("aws-csm.t.box")
        self.assertEqual((prof.get("identity") or {}).get("role"), "operator")

    def test_save_is_atomic_with_backup(self) -> None:
        store, d = self._store()
        path = d / "aws-csm.t.box.json"
        path.write_text(json.dumps(_profile("user")), encoding="utf-8")
        prof = store.get_profile("aws-csm.t.box")
        prof["identity"]["display_name"] = "v2"
        store.save_profile(
            tenant_scope_id="x.test", profile_id="aws-csm.t.box", payload=prof
        )
        # Prior version backed up, current version updated, no temp leftovers.
        self.assertTrue((d / "aws-csm.t.box.json.bak").exists())
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["identity"]["display_name"], "v2")
        self.assertNotIn("_source_path", on_disk)
        # The .bak is not surfaced as a profile.
        self.assertEqual([p["identity"]["profile_id"] for p in store.list_profiles()],
                         ["aws-csm.t.box"])
        self.assertFalse(list(d.glob(".aws_csm_*.tmp")))


if __name__ == "__main__":
    unittest.main()
