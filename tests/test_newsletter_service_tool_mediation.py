from __future__ import annotations

import importlib
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def _load_service_tools_module():
    portals_root = Path(__file__).resolve().parents[1] / "portals"
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return importlib.import_module("_shared.portal.application.service_tools")


class NewsletterServiceToolMediationTests(unittest.TestCase):
    def test_aws_newsletter_context_prefers_canonical_profile_over_progeny_drift(self):
        module = _load_service_tools_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir) / "private"
            frontend_root = Path(temp_dir) / "clients" / "trappfamilyfarm.com" / "frontend"
            frontend_root.mkdir(parents=True, exist_ok=True)
            contact_path = frontend_root.parent / "contacts" / "trappfamilyfarm.com-contact_log.json"
            contact_path.parent.mkdir(parents=True, exist_ok=True)
            contact_path.write_text(
                json.dumps(
                    {
                        "schema": "mycite.webapp.contact_log.v1",
                        "domain": "trappfamilyfarm.com",
                        "contacts": [{"email": "reader@example.com", "subscribed": True}],
                        "dispatches": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            newsletter_root = private_dir / "utilities" / "tools" / "newsletter-admin"
            newsletter_root.mkdir(parents=True, exist_ok=True)
            (newsletter_root / "spec.json").write_text(
                json.dumps({"schema": "mycite.portal.tool_spec.v1", "tool_id": "newsletter-admin", "inherited_inputs": [], "outputs": []})
                + "\n",
                encoding="utf-8",
            )
            (newsletter_root / "tool.3-2-3.newsletter-admin.json").write_text(
                json.dumps({"member_files": ["newsletter-admin.trappfamilyfarm.com.json"]}) + "\n",
                encoding="utf-8",
            )
            (newsletter_root / "newsletter-admin.trappfamilyfarm.com.json").write_text(
                json.dumps(
                    {
                        "schema": "mycite.service_tool.newsletter.profile.v1",
                        "domain": "trappfamilyfarm.com",
                        "sender_address": "news@trappfamilyfarm.com",
                        "selected_author_profile_id": "aws-csm.tff.technicalContact",
                        "selected_author_address": "technicalContact@trappfamilyfarm.com",
                        "selected_sender_profile_id": "aws-csm.tff.technicalContact",
                        "selected_sender_address": "technicalContact@trappfamilyfarm.com",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            fnd_ebi_root = private_dir / "utilities" / "tools" / "fnd-ebi"
            fnd_ebi_root.mkdir(parents=True, exist_ok=True)
            (fnd_ebi_root / "fnd-ebi.trappfamilyfarm.com.json").write_text(
                json.dumps({"schema": "mycite.service_tool.fnd_ebi.profile.v1", "domain": "trappfamilyfarm.com", "site_root": str(frontend_root)})
                + "\n",
                encoding="utf-8",
            )
            aws_root = private_dir / "utilities" / "tools" / "aws-csm"
            aws_root.mkdir(parents=True, exist_ok=True)
            (aws_root / "spec.json").write_text(
                json.dumps({"schema": "mycite.portal.tool_spec.v1", "tool_id": "aws-csm", "inherited_inputs": [], "outputs": []})
                + "\n",
                encoding="utf-8",
            )
            (aws_root / "tool.3-2-3.aws-csm.json").write_text(
                json.dumps({"schema": "mycite.portal.tool_collection.v1", "member_files": ["spec.json", "aws-csm.tff.technicalContact.json"]}) + "\n",
                encoding="utf-8",
            )
            (aws_root / "aws-csm.tff.technicalContact.json").write_text(
                json.dumps(
                    {
                        "schema": "mycite.service_tool.aws_csm.profile.v1",
                        "identity": {
                            "profile_id": "aws-csm.tff.technicalContact",
                            "domain": "trappfamilyfarm.com",
                            "mailbox_local_part": "technicalContact",
                            "role": "technical_contact",
                            "send_as_email": "technicalContact@trappfamilyfarm.com",
                        },
                        "verification": {"status": "verified"},
                        "provider": {"gmail_send_as_status": "verified"},
                        "workflow": {"is_send_as_confirmed": True},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            progeny_root = private_dir / "network" / "progeny"
            progeny_root.mkdir(parents=True, exist_ok=True)
            (progeny_root / "member-trapp.json").write_text(
                json.dumps(
                    {
                        "profile_refs": {
                            "paypal_site_domain": "trappfamilyfarm.com",
                            "newsletter_ingest_address": "hermes@trappfamilyfarm.com",
                            "newsletter_sender_address": "news@trappfamilyfarm.com",
                            "newsletter_allowed_from_csv": "mark@trappfamilyfarm.com",
                            "newsletter_dispatch_mode": "aws_internal",
                        },
                        "email_policy": {
                            "newsletter": {
                                "allowed_from": ["mark@trappfamilyfarm.com"],
                                "ingest_address": "hermes@trappfamilyfarm.com",
                                "sender_address": "news@trappfamilyfarm.com",
                                "dispatch_mode": "aws_internal",
                            }
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            payload = module.build_service_tool_config_context(
                "aws_platform_admin",
                private_dir=private_dir,
                tool_tabs=[{"tool_id": "aws_platform_admin", **module.build_service_tool_meta("aws_platform_admin")}],
                portal_instance_id="fnd",
                msn_id="3-2-3",
            )
            self.assertTrue(payload.get("ok"))
            self.assertEqual(payload.get("tool_namespace"), "aws-csm")
            sections = payload.get("profile_domain_sections") or []
            self.assertEqual(len(sections), 1)
            newsletter_cards = sections[0].get("newsletter_cards") if isinstance(sections[0], dict) else []
            self.assertEqual(len(newsletter_cards), 1)
            body = (newsletter_cards[0].get("body") or {}) if isinstance(newsletter_cards[0], dict) else {}
            self.assertEqual(body.get("domain"), "trappfamilyfarm.com")
            self.assertEqual(body.get("subscribed_count"), 1)
            self.assertEqual(((body.get("selected_sender") or {}).get("send_as_email")), "technicalContact@trappfamilyfarm.com")
            self.assertEqual(body.get("sender_address"), "news@trappfamilyfarm.com")
            warnings = body.get("warnings") if isinstance(body.get("warnings"), list) else []
            self.assertTrue(any("compatibility drift" in str(item) for item in warnings))
