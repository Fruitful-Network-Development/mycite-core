from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def _load_normalize_module():
    repo_root = Path(__file__).resolve().parents[1]
    path = repo_root / "instances" / "_shared" / "portal" / "progeny_model" / "normalize.py"
    for candidate in (repo_root, repo_root / "instances", repo_root / "packages"):
        token = str(candidate)
        if token not in sys.path:
            sys.path.insert(0, token)
    spec = importlib.util.spec_from_file_location("mycite_shared_progeny_normalize_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MemberProfileNormalizeTests(unittest.TestCase):
    def test_legacy_email_map_derives_forwarder_no_smtp_policy(self):
        module = _load_normalize_module()
        payload = {
            "msn_id": "3-2-3-17-77-2-6-3-1-6",
            "title": "trapp_family_farm",
            "contract": {"contract_id": "contract-fnd-tff-member-001"},
            "config": {
                "status": True,
                "email_map": {
                    "inbox_inbound": {
                        "info@trappfamilyfarm.com": ["proxy@trappfamilyfarm.com"],
                        "mark@trappfamilyfarm.com": ["proxy@trappfamilyfarm.com"],
                        "proxy@trappfamilyfarm.com": ["trapp.family.farm@gmail.com"],
                    },
                    "proxy_outbound": {
                        "proxy@trappfamilyfarm.com": [
                            "info@trappfamilyfarm.com",
                            "mark@trappfamilyfarm.com",
                        ],
                        "trapp.family.farm@gmail.com": ["proxy@trappfamilyfarm.com", "hermes@trappfamilyfarm.com"],
                        "lambda": ["news@trappfamilyfarm.com"],
                    },
                },
                "paypal": {
                    "site_base_url": "https://trappfamilyfarm.com",
                },
            },
        }

        normalized = module.normalize_member_profile("1", payload)

        self.assertEqual(normalized["member_id"], "1")
        self.assertEqual(normalized["member_msn_id"], "3-2-3-17-77-2-6-3-1-6")
        self.assertEqual(normalized["display"]["title"], "trapp_family_farm")
        self.assertEqual(normalized["contract_refs"]["authorization_contract_id"], "contract-fnd-tff-member-001")
        self.assertTrue(normalized["capabilities"]["aws"])
        self.assertTrue(normalized["capabilities"]["paypal"])

        refs = normalized["profile_refs"]
        self.assertEqual(refs["email_transport_mode"], "forwarder_no_smtp")
        self.assertEqual(refs["email_forwarder_address"], "proxy@trappfamilyfarm.com")
        self.assertEqual(refs["email_operator_inbox"], "trapp.family.farm@gmail.com")
        self.assertEqual(refs["newsletter_ingest_address"], "hermes@trappfamilyfarm.com")
        self.assertEqual(refs["newsletter_sender_address"], "news@trappfamilyfarm.com")

        policy = normalized["email_policy"]
        self.assertEqual(policy["mode"], "forwarder_no_smtp")
        self.assertFalse(policy["smtp_enabled"])
        self.assertIn("info@trappfamilyfarm.com", policy["inbound_aliases"])
        self.assertIn("mark@trappfamilyfarm.com", policy["reply"]["allowed_from"])

    def test_paypal_site_domain_derives_base_url_and_keeps_custom_ref(self):
        module = _load_normalize_module()
        refs = module.normalize_member_profile_refs(
            {
                "profile_refs": {
                    "paypal_site_domain": "client.example.com",
                    "custom_route_ref": "9-9-9",
                }
            },
            "22",
        )

        self.assertEqual(refs["paypal_profile_id"], "paypal:member:22")
        self.assertEqual(refs["paypal_site_domain"], "client.example.com")
        self.assertEqual(refs["paypal_site_base_url"], "https://client.example.com")
        self.assertEqual(refs["custom_route_ref"], "9-9-9")


if __name__ == "__main__":
    unittest.main()
