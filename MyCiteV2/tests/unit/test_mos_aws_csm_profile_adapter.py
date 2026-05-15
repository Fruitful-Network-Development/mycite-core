"""Tests for MosDatumAwsCsmProfileAdapter (Email tab MOS backing)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.sql.aws_csm_profile_registry import (
    DOMAIN_SCHEMA,
    PROFILE_SCHEMA,
    MosDatumAwsCsmProfileAdapter,
)


def _operator_profile(profile_id: str, tenant: str, domain: str) -> dict:
    return {
        "schema": "mycite.service_tool.aws_csm.profile.v1",
        "identity": {
            "profile_id": profile_id,
            "tenant_id": tenant,
            "domain": domain,
            "mailbox_local_part": profile_id.split(".")[-1],
            "send_as_email": f"{profile_id.split('.')[-1]}@{domain}",
            "role": "operator",
        },
        "workflow": {"lifecycle_state": "draft"},
        "inbound": {"receive_state": "receive_unconfigured"},
    }


def _domain_record(tenant: str, domain: str) -> dict:
    return {
        "schema": "mycite.service_tool.aws_csm.domain.v1",
        "identity": {"tenant_id": tenant, "domain": domain, "region": "us-east-1"},
        "dns": {"hosted_zone_present": True},
    }


class MosProfileAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "mos.sqlite3"
        self.adapter = MosDatumAwsCsmProfileAdapter(
            authority_db_file=self.db,
            tenant_id="tenant",
            msn_id="test-msn",
        )

    def test_list_profiles_empty_until_seeded(self) -> None:
        self.assertEqual(self.adapter.list_profiles(), [])
        self.assertEqual(self.adapter.list_domains(), [])

    def test_create_then_list_profile(self) -> None:
        payload = _operator_profile("aws-csm.cvccboard.elizabeth", "cvccboard", "cvccboard.org")
        self.adapter.create_profile(profile_id="aws-csm.cvccboard.elizabeth", payload=payload)
        profiles = self.adapter.list_profiles()
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0]["identity"]["profile_id"], "aws-csm.cvccboard.elizabeth")

    def test_save_then_load_domain_record(self) -> None:
        payload = _domain_record("cvcc", "cuyahogavalleycountrysideconservancy.org")
        self.adapter.save_domain(tenant_id="cvcc", payload=payload)
        loaded = self.adapter.load_domain(domain="cuyahogavalleycountrysideconservancy.org")
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded["identity"]["domain"], "cuyahogavalleycountrysideconservancy.org")
        # list_domains should also return it
        self.assertEqual(len(self.adapter.list_domains()), 1)

    def test_load_profile_returns_none_when_missing(self) -> None:
        self.assertIsNone(
            self.adapter.load_profile(
                tenant_scope_id="tenant", profile_id="aws-csm.nonexistent.user"
            )
        )

    def test_load_profile_enforces_tenant_scope(self) -> None:
        self.adapter.create_profile(
            profile_id="aws-csm.cvccboard.eliz",
            payload=_operator_profile("aws-csm.cvccboard.eliz", "cvccboard", "cvccboard.org"),
        )
        # Tenant-scope mismatch returns None
        self.assertIsNone(
            self.adapter.load_profile(
                tenant_scope_id="other-tenant", profile_id="aws-csm.cvccboard.eliz"
            )
        )
        # Tenant-scope match returns the record
        match = self.adapter.load_profile(
            tenant_scope_id="cvccboard", profile_id="aws-csm.cvccboard.eliz"
        )
        self.assertIsNotNone(match)

    def test_resolve_domain_seed_returns_provider_summary(self) -> None:
        payload = _domain_record("cvccboard", "cvccboard.org")
        payload["ses"] = {"identity_status": "verified"}
        payload["observation"] = {"last_checked_at": "2026-05-01T00:00:00Z"}
        self.adapter.save_domain(tenant_id="cvccboard", payload=payload)
        seed = self.adapter.resolve_domain_seed(domain="cvccboard.org")
        self.assertIsNotNone(seed)
        assert seed is not None
        self.assertEqual(seed["tenant_id"], "cvccboard")
        self.assertEqual(seed["provider"]["aws_ses_identity_status"], "verified")


if __name__ == "__main__":
    unittest.main()
