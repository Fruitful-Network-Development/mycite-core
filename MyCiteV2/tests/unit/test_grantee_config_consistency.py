"""Grantee config-consistency linter (stack operating contract: SSOT + drift-lint)."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from MyCiteV2.scripts.grantee_config_consistency import check_grantee


def _seed_newsletter_admin(private_dir: Path, domain: str) -> None:
    d = private_dir / "utilities" / "tools" / "newsletter-admin"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"newsletter-admin.{domain}.json").write_text("{}", encoding="utf-8")


class GranteeConfigConsistencyTests(unittest.TestCase):
    def test_complete_grantee_has_no_gaps(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp)
            _seed_newsletter_admin(p, "example.org")
            g = {
                "domains": ["example.org"],
                "aws_ses": {"identity": "x@example.org"},
                "connect": {"forward_to_email": "y@example.org"},
            }
            r = check_grantee(p, g)
            self.assertTrue(r["ok"])
            self.assertEqual(r["gaps"], [])

    def test_missing_newsletter_and_forward_are_operator_decisions(self) -> None:
        with TemporaryDirectory() as tmp:
            g = {"domains": ["bpw.com"], "aws_ses": {"identity": "x@bpw.com"}}
            r = check_grantee(Path(tmp), g)
            fields = {f for _, f, _ in r["gaps"]}
            self.assertIn("connect.forward_to_email", fields)
            self.assertIn("newsletter-admin profile", fields)
            self.assertTrue(all(cls == "OPERATOR_DECISION" for cls, _, _ in r["gaps"]))

    def test_missing_aws_ses_identity_is_required(self) -> None:
        with TemporaryDirectory() as tmp:
            _seed_newsletter_admin(Path(tmp), "x.com")
            g = {"domains": ["x.com"], "connect": {"forward_to_email": "a@x.com"}}
            r = check_grantee(Path(tmp), g)
            self.assertIn("REQUIRED", {cls for cls, _, _ in r["gaps"]})

    def test_first_domain_is_primary_rest_are_aliases(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp)
            _seed_newsletter_admin(p, "primary.org")
            g = {
                "domains": ["primary.org", "alias.org"],
                "aws_ses": {"identity": "x@primary.org"},
                "connect": {"forward_to_email": "y@primary.org"},
            }
            r = check_grantee(p, g)
            self.assertEqual(r["primary"], "primary.org")
            self.assertEqual(r["aliases"], ["alias.org"])
            self.assertTrue(r["ok"])  # aliases don't need their own configs


if __name__ == "__main__":
    unittest.main()
