from __future__ import annotations

import importlib
import json
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory


def _load_service_tools_module():
    portals_root = Path(__file__).resolve().parents[1] / "portals"
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return importlib.import_module("_shared.portal.application.service_tools")


class ServiceToolMediationTests(unittest.TestCase):
    def test_service_tool_meta_exposes_shared_config_context_contract(self):
        module = _load_service_tools_module()
        meta = module.build_service_tool_meta("fnd_ebi")
        self.assertTrue(meta.get("config_context_support"))
        self.assertEqual(
            ((meta.get("inspector_card_contribution") or {}).get("config_context_route")),
            "/portal/api/data/system/config_context/fnd_ebi",
        )
        self.assertEqual(((meta.get("workbench_contribution") or {})), {})
        self.assertEqual(((meta.get("interface_panel_contribution") or {}).get("default_mode")), "overview")
        self.assertEqual(meta.get("shell_composition_mode"), "tool")
        self.assertEqual(meta.get("foreground_surface"), "interface_panel")
        self.assertEqual(meta.get("surface_mode"), "mediation_only")
        self.assertFalse(meta.get("owns_shell_state"))
        self.assertEqual(((meta.get("service_contract") or {}).get("mediation_host_path")), "/portal/system")
        self.assertEqual((((meta.get("service_contract") or {}).get("host_composition") or {}).get("mode")), "tool")
        self.assertEqual(((meta.get("service_contract") or {}).get("config_datum") or {}).get("content_kind"), "json")
        self.assertIn(
            "tool.*.fnd-ebi.json",
            (((meta.get("service_contract") or {}).get("config_datum") or {}).get("patterns") or []),
        )
        self.assertEqual(
            ((meta.get("service_contract") or {}).get("collection_view_contract") or {}).get("default_mode"),
            "overview",
        )
        self.assertEqual(
            ((meta.get("service_contract") or {}).get("internal_source_contract") or {}).get("mode"),
            "read_only",
        )

    def test_service_tool_registration_has_no_shell_home(self):
        module = _load_service_tools_module()
        tool = module.build_service_tool_registration("operations", "Operations")
        self.assertEqual(tool.get("tool_id"), "operations")
        self.assertEqual(tool.get("route_prefix"), "")
        self.assertEqual(tool.get("home_path"), "")
        self.assertEqual(tool.get("surface_mode"), "mediation_only")
        self.assertFalse(tool.get("owns_shell_state"))

    def test_service_tool_config_context_reads_tool_owned_collections(self):
        module = _load_service_tools_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir) / "private"
            root = private_dir / "utilities" / "tools" / "fnd-ebi"
            root.mkdir(parents=True, exist_ok=True)
            client_root = Path(temp_dir) / "clients" / "fruitfulnetworkdevelopment.com"
            frontend_root = client_root / "frontend"
            analytics_root = client_root / "analytics"
            (analytics_root / "nginx").mkdir(parents=True, exist_ok=True)
            (analytics_root / "events").mkdir(parents=True, exist_ok=True)
            frontend_root.mkdir(parents=True, exist_ok=True)
            (analytics_root / "nginx" / "access.log").write_text(
                '127.0.0.1 - - [24/Mar/2026:00:00:01 +0000] "GET / HTTP/1.1" 200 123\n',
                encoding="utf-8",
            )
            (analytics_root / "nginx" / "error.log").write_text(
                "[error] 1#1: *1 upstream timed out\n",
                encoding="utf-8",
            )
            (root / "web-analytics.json").write_text(
                json.dumps({"1-0-1": [["1-0-1", "[]", "[\"[]\"]"], ["fnd-ebi.fnd.json"]]}) + "\n",
                encoding="utf-8",
            )
            (root / "fnd-ebi.fnd.json").write_text(
                json.dumps(
                    {
                        "domain": "fruitfulnetworkdevelopment.com",
                        "site_root": str(frontend_root),
                        "analytics": {"enabled": True},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            previous_roots = os.environ.get("MYCITE_INTERNAL_FILE_ROOTS")
            os.environ["MYCITE_INTERNAL_FILE_ROOTS"] = str(client_root.parent)
            try:
                payload = module.build_service_tool_config_context(
                    "fnd_ebi",
                    private_dir=private_dir,
                    tool_tabs=[{"tool_id": "fnd_ebi", **module.build_service_tool_meta("fnd_ebi")}],
                    portal_instance_id="fnd",
                    msn_id="3-2-3",
                )
            finally:
                if previous_roots is None:
                    os.environ.pop("MYCITE_INTERNAL_FILE_ROOTS", None)
                else:
                    os.environ["MYCITE_INTERNAL_FILE_ROOTS"] = previous_roots
            self.assertTrue(payload.get("ok"))
            self.assertEqual(payload.get("tool_namespace"), "fnd-ebi")
            self.assertGreaterEqual(len(payload.get("collection_files") or []), 5)
            self.assertEqual(((payload.get("config_datum") or {}).get("file_name")), "fnd-ebi.fnd.json")
            self.assertEqual(((payload.get("collection_datum") or {}).get("file_name")), "web-analytics.json")
            self.assertEqual(((payload.get("service_contract") or {}).get("schema")), "mycite.service_tool.contract.v1")
            self.assertEqual(((payload.get("activation") or {}).get("default_verb")), "mediate")
            self.assertEqual(((payload.get("activation") or {}).get("host_path")), "/portal/system")
            self.assertEqual(payload.get("shell_composition_mode"), "tool")
            self.assertEqual(payload.get("foreground_surface"), "interface_panel")
            self.assertEqual(((payload.get("interface_lens") or {}).get("default_mode")), "overview")
            self.assertEqual(((payload.get("interface_lens") or {}).get("shell_composition_mode")), "tool")
            self.assertNotIn("workspace_profile", payload)
            self.assertEqual(
                ((payload.get("activation") or {}).get("request_payload") or {}).get("shell_verb"),
                "mediate",
            )
            self.assertTrue(any(str(item.get("title") or "") == "fruitfulnetworkdevelopment.com" for item in payload.get("profile_cards") or []))
            snapshots = payload.get("analytics_snapshots") or []
            self.assertEqual(len(snapshots), 1)
            self.assertEqual((snapshots[0].get("access_log") or {}).get("present"), True)
            self.assertEqual((snapshots[0].get("error_log") or {}).get("present"), True)
            self.assertIn("frontend", snapshots[0])
            self.assertEqual((snapshots[0].get("frontend") or {}).get("robots_present"), False)
            self.assertEqual((snapshots[0].get("events_file") or {}).get("raw_line_count"), 0)
            self.assertIn("traffic", snapshots[0])
            self.assertIn("events_summary", snapshots[0])

    def test_fnd_ebi_legacy_events_path_is_consumed_with_warning(self):
        module = _load_service_tools_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir) / "private"
            root = private_dir / "utilities" / "tools" / "fnd-ebi"
            root.mkdir(parents=True, exist_ok=True)
            client_root = Path(temp_dir) / "clients" / "legacy-domain.test"
            frontend_root = client_root / "frontend"
            analytics_root = client_root / "analytics"
            (analytics_root / "nginx").mkdir(parents=True, exist_ok=True)
            (analytics_root / "evnts").mkdir(parents=True, exist_ok=True)
            frontend_root.mkdir(parents=True, exist_ok=True)
            (analytics_root / "nginx" / "access.log").write_text(
                '127.0.0.1 - - [24/Mar/2026:00:00:01 +0000] "GET / HTTP/1.1" 200 123 "-" "Mozilla/5.0"\n',
                encoding="utf-8",
            )
            (analytics_root / "nginx" / "error.log").write_text("", encoding="utf-8")
            month_token = datetime.now(timezone.utc).strftime("%Y-%m")
            (analytics_root / "evnts" / f"{month_token}.ndjson").write_text(
                '{"event_type":"page_view","timestamp":"2026-03-24T00:00:01Z","session_id":"s1"}\n',
                encoding="utf-8",
            )
            (root / "web-analytics.json").write_text(
                json.dumps({"1-0-1": [["1-0-1", "[]", "[\"[]\"]"], ["fnd-ebi.legacy.json"]]}) + "\n",
                encoding="utf-8",
            )
            (root / "fnd-ebi.legacy.json").write_text(
                json.dumps({"domain": "legacy-domain.test", "site_root": str(frontend_root)}) + "\n",
                encoding="utf-8",
            )
            previous_roots = os.environ.get("MYCITE_INTERNAL_FILE_ROOTS")
            os.environ["MYCITE_INTERNAL_FILE_ROOTS"] = str(client_root.parent)
            try:
                payload = module.build_service_tool_config_context(
                    "fnd_ebi",
                    private_dir=private_dir,
                    tool_tabs=[{"tool_id": "fnd_ebi", **module.build_service_tool_meta("fnd_ebi")}],
                    portal_instance_id="fnd",
                    msn_id="3-2-3",
                )
            finally:
                if previous_roots is None:
                    os.environ.pop("MYCITE_INTERNAL_FILE_ROOTS", None)
                else:
                    os.environ["MYCITE_INTERNAL_FILE_ROOTS"] = previous_roots
            snapshots = payload.get("analytics_snapshots") or []
            self.assertEqual(len(snapshots), 1)
            self.assertEqual((snapshots[0].get("events_file") or {}).get("present"), True)
            self.assertIn("using legacy events path", " ".join(list(snapshots[0].get("warnings") or [])))

    def test_service_tool_context_prefers_configured_anchor(self):
        module = _load_service_tools_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir) / "private"
            root = private_dir / "utilities" / "tools" / "fnd-ebi"
            root.mkdir(parents=True, exist_ok=True)
            (private_dir / "config.json").write_text(
                json.dumps(
                    {
                        "msn_id": "3-2-3",
                        "tools_configuration": [
                            {
                                "name": "fnd-ebi",
                                "anchor": "tool.3-2-3.fnd-ebi.json",
                                "status": "enabled",
                                "mount_target": "peripherals.tools",
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "tool.3-2-3.fnd-ebi.json").write_text(
                json.dumps({"1-0-1": [["1-0-1", "~", "[\"0-0-11\"]"], ["fnd-ebi.fnd.json"]]}) + "\n",
                encoding="utf-8",
            )
            (root / "fnd-ebi.fnd.json").write_text(
                json.dumps({"schema": "mycite.service_tool.fnd_ebi.profile.v1", "domain": "example.org", "site_root": "/tmp/site"})
                + "\n",
                encoding="utf-8",
            )
            payload = module.build_service_tool_config_context(
                "fnd_ebi",
                private_dir=private_dir,
                tool_tabs=[{"tool_id": "fnd_ebi", **module.build_service_tool_meta("fnd_ebi")}],
                portal_instance_id="fnd",
                msn_id="3-2-3",
            )
            self.assertEqual(((payload.get("config_datum") or {}).get("file_name")), "tool.3-2-3.fnd-ebi.json")

    def test_aws_profile_contract_is_normalized_for_smtp_staging(self):
        module = _load_service_tools_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir) / "private"
            root = private_dir / "utilities" / "tools" / "aws-csm"
            root.mkdir(parents=True, exist_ok=True)
            (root / "aws-csm.fnd.json").write_text(
                json.dumps(
                    {
                        "domain": "fruitfulnetworkdevelopment.com",
                        "region": "us-east-1",
                        "alias_email": "dylan@fruitfulnetworkdevelopment.com",
                        "forward_to_email": "dylancarsonmontgomery@gmail.com",
                        "forwarding_status": "active",
                        "gmail_send_as_status": "not_started",
                        "verification_code": "",
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
            cards = payload.get("profile_cards") if isinstance(payload.get("profile_cards"), list) else []
            self.assertTrue(cards)
            card_body = cards[0].get("body") if isinstance(cards[0], dict) else {}
            self.assertIn("identity", card_body)
            self.assertIn("smtp", card_body)
            self.assertIn("verification", card_body)
            self.assertIn("provider", card_body)
            self.assertIn("workflow", card_body)
            identity = card_body.get("identity") if isinstance(card_body.get("identity"), dict) else {}
            smtp = card_body.get("smtp") if isinstance(card_body.get("smtp"), dict) else {}
            verification = card_body.get("verification") if isinstance(card_body.get("verification"), dict) else {}
            provider = card_body.get("provider") if isinstance(card_body.get("provider"), dict) else {}
            workflow = card_body.get("workflow") if isinstance(card_body.get("workflow"), dict) else {}
            inbound = card_body.get("inbound") if isinstance(card_body.get("inbound"), dict) else {}
            self.assertEqual(identity.get("tenant_id"), "fnd")
            self.assertEqual(identity.get("profile_id"), "aws-csm.fnd.dylan")
            self.assertEqual(identity.get("mailbox_local_part"), "dylan")
            self.assertEqual(identity.get("profile_kind"), "mailbox")
            self.assertEqual(identity.get("single_user_email"), "dylancarsonmontgomery@gmail.com")
            self.assertEqual(identity.get("operator_inbox_target"), "dylancarsonmontgomery@gmail.com")
            self.assertEqual(smtp.get("host"), "email-smtp.us-east-1.amazonaws.com")
            self.assertEqual(smtp.get("port"), "587")
            self.assertEqual(smtp.get("credentials_source"), "operator_managed")
            self.assertEqual(smtp.get("credentials_secret_name"), "aws-cms/smtp/fnd.dylan")
            self.assertEqual(smtp.get("credentials_secret_state"), "missing")
            self.assertEqual(verification.get("portal_state"), "staged")
            self.assertEqual(provider.get("aws_ses_identity_status"), "not_started")
            self.assertEqual(workflow.get("schema"), "mycite.service_tool.aws_csm.onboarding.v1")
            self.assertEqual(workflow.get("flow"), "mailbox_send_as")
            self.assertEqual(workflow.get("lifecycle_state"), "uninitiated")
            self.assertEqual(inbound.get("receive_state"), "receive_configured")
            self.assertEqual(inbound.get("legacy_dependency_state"), "portal_native_pending")
            self.assertFalse(bool(inbound.get("portal_native_display_ready")))
            self.assertEqual(list(workflow.get("missing_required_now") or []), [])
            self.assertEqual(list(workflow.get("configuration_blockers_now") or []), [])
            self.assertEqual(list(workflow.get("gmail_handoff_blockers_now") or []), [])
            self.assertEqual(list(workflow.get("inbound_blockers_now") or []), [])
            self.assertEqual(workflow.get("handoff_status"), "uninitiated")
            self.assertEqual(workflow.get("completion_boundary"), "uninitiated")
            self.assertFalse(bool(workflow.get("is_ready_for_user_handoff")))

    def test_aws_profile_boundary_can_be_ready_for_gmail_handoff_without_send_as_confirmation(self):
        module = _load_service_tools_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir) / "private"
            root = private_dir / "utilities" / "tools" / "aws-csm"
            root.mkdir(parents=True, exist_ok=True)
            (root / "aws-csm.fnd.dylan.json").write_text(
                json.dumps(
                    {
                        "schema": "mycite.service_tool.aws_csm.profile.v1",
                        "identity": {
                            "profile_id": "aws-csm.fnd.dylan",
                            "tenant_id": "fnd",
                            "domain": "fruitfulnetworkdevelopment.com",
                            "region": "us-east-1",
                            "mailbox_local_part": "dylan",
                            "operator_inbox_target": "dylancarsonmontgomery@gmail.com",
                            "single_user_email": "dylancarsonmontgomery@gmail.com",
                            "send_as_email": "dylan@fruitfulnetworkdevelopment.com",
                        },
                        "smtp": {
                            "send_as_email": "dylan@fruitfulnetworkdevelopment.com",
                            "host": "email-smtp.us-east-1.amazonaws.com",
                            "port": "587",
                            "username": "AKIAEXAMPLE",
                            "credentials_source": "operator_managed",
                            "credentials_secret_name": "aws-cms/smtp/fnd",
                            "credentials_secret_state": "configured",
                            "forward_to_email": "dylancarsonmontgomery@gmail.com",
                        },
                        "verification": {
                            "status": "not_started",
                        },
                        "provider": {
                            "aws_ses_identity_status": "verified",
                            "gmail_send_as_status": "not_started",
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
            cards = payload.get("profile_cards") if isinstance(payload.get("profile_cards"), list) else []
            self.assertTrue(cards)
            card_body = cards[0].get("body") if isinstance(cards[0], dict) else {}
            smtp = card_body.get("smtp") if isinstance(card_body.get("smtp"), dict) else {}
            verification = card_body.get("verification") if isinstance(card_body.get("verification"), dict) else {}
            workflow = card_body.get("workflow") if isinstance(card_body.get("workflow"), dict) else {}
            inbound = card_body.get("inbound") if isinstance(card_body.get("inbound"), dict) else {}
            self.assertEqual(smtp.get("credentials_secret_name"), "aws-cms/smtp/fnd")
            self.assertEqual(smtp.get("credentials_secret_state"), "configured")
            self.assertEqual(smtp.get("username"), "AKIAEXAMPLE")
            self.assertTrue(bool(smtp.get("handoff_ready")))
            self.assertEqual(verification.get("status"), "not_started")
            provider = card_body.get("provider") if isinstance(card_body.get("provider"), dict) else {}
            self.assertEqual(provider.get("gmail_send_as_status"), "not_started")
            self.assertEqual(workflow.get("flow"), "mailbox_send_as")
            self.assertEqual(workflow.get("lifecycle_state"), "send_as_pending")
            self.assertEqual(verification.get("portal_state"), "awaiting_gmail_handoff")
            self.assertEqual(inbound.get("receive_state"), "receive_pending")
            self.assertEqual(list(workflow.get("configuration_blockers_now") or []), [])
            self.assertEqual(
                list(workflow.get("gmail_handoff_blockers_now") or []),
                ["verification.status", "provider.gmail_send_as_status"],
            )
            self.assertEqual(
                list(workflow.get("inbound_blockers_now") or []),
                ["inbound.portal_native_display_ready", "inbound.receive_verified"],
            )
            self.assertEqual(workflow.get("handoff_status"), "ready_for_gmail_handoff")
            self.assertEqual(workflow.get("completion_boundary"), "gmail_inbox_dependent")
            self.assertTrue(bool(workflow.get("is_ready_for_user_handoff")))
            self.assertFalse(bool(workflow.get("is_send_as_confirmed")))

    def test_aws_profile_requires_both_mailbox_and_provider_verified_states_for_send_as_confirmation(self):
        module = _load_service_tools_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir) / "private"
            root = private_dir / "utilities" / "tools" / "aws-csm"
            root.mkdir(parents=True, exist_ok=True)
            (root / "aws-csm.fnd.dylan.json").write_text(
                json.dumps(
                    {
                        "schema": "mycite.service_tool.aws_csm.profile.v1",
                        "identity": {
                            "profile_id": "aws-csm.fnd.dylan",
                            "tenant_id": "fnd",
                            "domain": "fruitfulnetworkdevelopment.com",
                            "region": "us-east-1",
                            "mailbox_local_part": "dylan",
                            "operator_inbox_target": "dylancarsonmontgomery@gmail.com",
                            "single_user_email": "dylancarsonmontgomery@gmail.com",
                            "send_as_email": "dylan@fruitfulnetworkdevelopment.com",
                        },
                        "smtp": {
                            "send_as_email": "dylan@fruitfulnetworkdevelopment.com",
                            "host": "email-smtp.us-east-1.amazonaws.com",
                            "port": "587",
                            "username": "AKIAEXAMPLE",
                            "credentials_source": "operator_managed",
                            "credentials_secret_name": "aws-cms/smtp/fnd",
                            "credentials_secret_state": "configured",
                            "forward_to_email": "dylancarsonmontgomery@gmail.com",
                        },
                        "verification": {
                            "status": "pending",
                            "portal_state": "verification_email_received",
                            "link": "https://mail-settings.google.com/mail/vf-example",
                            "latest_message_reference": "s3://ses-inbound-fnd-mail/inbound/example",
                        },
                        "provider": {
                            "aws_ses_identity_status": "verified",
                            "gmail_send_as_status": "verified",
                        },
                        "inbound": {
                            "receive_routing_target": "dylancarsonmontgomery@gmail.com",
                            "latest_message_has_verification_link": True,
                        },
                        "workflow": {
                            "initiated": True,
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
            cards = payload.get("profile_cards") if isinstance(payload.get("profile_cards"), list) else []
            self.assertTrue(cards)
            card_body = cards[0].get("body") if isinstance(cards[0], dict) else {}
            verification = card_body.get("verification") if isinstance(card_body.get("verification"), dict) else {}
            provider = card_body.get("provider") if isinstance(card_body.get("provider"), dict) else {}
            workflow = card_body.get("workflow") if isinstance(card_body.get("workflow"), dict) else {}
            self.assertEqual(verification.get("status"), "pending")
            self.assertEqual(provider.get("gmail_send_as_status"), "verified")
            self.assertFalse(bool(workflow.get("is_send_as_confirmed")))
            self.assertEqual(workflow.get("handoff_status"), "ready_for_gmail_handoff")
            self.assertIn("verification.status", list(workflow.get("gmail_handoff_blockers_now") or []))

    def test_service_tool_context_emits_profile_interface_cards(self):
        module = _load_service_tools_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir) / "private"
            root = private_dir / "utilities" / "tools" / "aws-csm"
            root.mkdir(parents=True, exist_ok=True)
            (root / "aws-csm.fnd.dylan.json").write_text(
                json.dumps(
                    {
                        "schema": "mycite.service_tool.aws_csm.profile.v1",
                        "identity": {
                            "profile_id": "aws-csm.fnd.dylan",
                            "tenant_id": "fnd",
                            "domain": "fruitfulnetworkdevelopment.com",
                            "region": "us-east-1",
                            "mailbox_local_part": "dylan",
                            "single_user_email": "dylan@fruitfulnetworkdevelopment.com",
                        },
                        "smtp": {
                            "send_as_email": "dylan@fruitfulnetworkdevelopment.com",
                            "host": "smtp.gmail.com",
                            "port": "587",
                            "username": "dylan@fruitfulnetworkdevelopment.com",
                            "forward_to_email": "dylancarsonmontgomery@gmail.com",
                            "handoff_ready": True,
                        },
                        "verification": {"status": "pending"},
                        "provider": {"gmail_send_as_status": "pending"},
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
            inspector_cards = payload.get("inspector_cards") if isinstance(payload.get("inspector_cards"), list) else []
            profile_cards = [card for card in inspector_cards if str(card.get("kind") or "") == "profile"]
            self.assertTrue(profile_cards)
            first = profile_cards[0].get("body") if isinstance(profile_cards[0], dict) else {}
            self.assertIn("identity", first)
            self.assertIn("smtp", first)
            self.assertIn("verification", first)
            self.assertIn("provider", first)

    def test_aws_profile_verified_state_requires_confirmation_evidence(self):
        module = _load_service_tools_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir) / "private"
            root = private_dir / "utilities" / "tools" / "aws-csm"
            root.mkdir(parents=True, exist_ok=True)
            (root / "aws-csm.tff.technicalContact.json").write_text(
                json.dumps(
                    {
                        "schema": "mycite.service_tool.aws_csm.profile.v1",
                        "identity": {
                            "profile_id": "aws-csm.tff.technicalContact",
                            "tenant_id": "tff",
                            "domain": "trappfamilyfarm.com",
                            "region": "us-east-1",
                            "mailbox_local_part": "technicalContact",
                            "operator_inbox_target": "trapp.family.farm@gmail.com",
                            "send_as_email": "technicalContact@trappfamilyfarm.com",
                        },
                        "smtp": {
                            "send_as_email": "technicalContact@trappfamilyfarm.com",
                            "host": "email-smtp.us-east-1.amazonaws.com",
                            "port": "587",
                            "username": "AKIAEXAMPLE",
                            "credentials_source": "operator_managed",
                            "credentials_secret_name": "aws-cms/smtp/tff.technicalContact",
                            "credentials_secret_state": "configured",
                            "forward_to_email": "trapp.family.farm@gmail.com",
                        },
                        "verification": {
                            "status": "verified",
                            "portal_state": "verified",
                            "verified_at": "2026-04-05T17:37:16.583968+00:00",
                        },
                        "provider": {
                            "aws_ses_identity_status": "verified",
                            "gmail_send_as_status": "verified",
                        },
                        "inbound": {
                            "receive_routing_target": "trapp.family.farm@gmail.com",
                            "receive_verified": True,
                        },
                        "workflow": {
                            "initiated": True,
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
            cards = payload.get("profile_cards") if isinstance(payload.get("profile_cards"), list) else []
            self.assertTrue(cards)
            card_body = cards[0].get("body") if isinstance(cards[0], dict) else {}
            verification = card_body.get("verification") if isinstance(card_body.get("verification"), dict) else {}
            provider = card_body.get("provider") if isinstance(card_body.get("provider"), dict) else {}
            workflow = card_body.get("workflow") if isinstance(card_body.get("workflow"), dict) else {}
            self.assertEqual(verification.get("status"), "not_started")
            self.assertEqual(provider.get("gmail_send_as_status"), "not_started")
            self.assertFalse(bool(workflow.get("is_send_as_confirmed")))
            self.assertEqual(workflow.get("handoff_status"), "ready_for_gmail_handoff")

    def test_aws_profile_stale_receive_verified_state_downgrades_without_receive_evidence(self):
        module = _load_service_tools_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir) / "private"
            root = private_dir / "utilities" / "tools" / "aws-csm"
            root.mkdir(parents=True, exist_ok=True)
            (root / "aws-csm.tff.technicalContact.json").write_text(
                json.dumps(
                    {
                        "schema": "mycite.service_tool.aws_csm.profile.v1",
                        "identity": {
                            "profile_id": "aws-csm.tff.technicalContact",
                            "tenant_id": "tff",
                            "domain": "trappfamilyfarm.com",
                            "region": "us-east-1",
                            "mailbox_local_part": "technicalContact",
                            "operator_inbox_target": "trapp.family.farm@gmail.com",
                            "send_as_email": "technicalContact@trappfamilyfarm.com",
                        },
                        "smtp": {
                            "send_as_email": "technicalContact@trappfamilyfarm.com",
                            "host": "email-smtp.us-east-1.amazonaws.com",
                            "port": "587",
                            "username": "AKIAEXAMPLE",
                            "credentials_source": "operator_managed",
                            "credentials_secret_name": "aws-cms/smtp/tff.technicalContact",
                            "credentials_secret_state": "configured",
                            "forward_to_email": "trapp.family.farm@gmail.com",
                        },
                        "workflow": {
                            "initiated": True,
                        },
                        "inbound": {
                            "receive_routing_target": "trapp.family.farm@gmail.com",
                            "receive_state": "receive_verified",
                            "receive_verified": False,
                            "portal_native_display_ready": False,
                            "latest_message_has_verification_link": False,
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
            cards = payload.get("profile_cards") if isinstance(payload.get("profile_cards"), list) else []
            self.assertTrue(cards)
            card_body = cards[0].get("body") if isinstance(cards[0], dict) else {}
            inbound = card_body.get("inbound") if isinstance(card_body.get("inbound"), dict) else {}
            self.assertEqual(inbound.get("receive_state"), "receive_pending")

    def test_aws_profile_boundary_can_be_fully_completed_after_confirmation(self):
        module = _load_service_tools_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir) / "private"
            root = private_dir / "utilities" / "tools" / "aws-csm"
            root.mkdir(parents=True, exist_ok=True)
            (root / "aws-csm.fnd.dylan.json").write_text(
                json.dumps(
                    {
                        "schema": "mycite.service_tool.aws_csm.profile.v1",
                        "identity": {
                            "profile_id": "aws-csm.fnd.dylan",
                            "tenant_id": "fnd",
                            "domain": "fruitfulnetworkdevelopment.com",
                            "region": "us-east-1",
                            "mailbox_local_part": "dylan",
                            "operator_inbox_target": "dylancarsonmontgomery@gmail.com",
                            "single_user_email": "dylancarsonmontgomery@gmail.com",
                            "send_as_email": "dylan@fruitfulnetworkdevelopment.com",
                        },
                        "smtp": {
                            "send_as_email": "dylan@fruitfulnetworkdevelopment.com",
                            "host": "email-smtp.us-east-1.amazonaws.com",
                            "port": "587",
                            "username": "AKIAEXAMPLE",
                            "credentials_source": "operator_managed",
                            "credentials_secret_name": "aws-cms/smtp/fnd",
                            "credentials_secret_state": "configured",
                            "forward_to_email": "dylancarsonmontgomery@gmail.com",
                        },
                        "verification": {
                            "status": "verified",
                            "portal_state": "verified",
                            "verified_at": "2026-04-02T15:40:00+00:00",
                            "link": "https://mail-settings.google.com/mail/vf-example",
                            "latest_message_reference": "s3://ses-inbound-fnd-mail/inbound/example",
                        },
                        "provider": {
                            "aws_ses_identity_status": "verified",
                            "gmail_send_as_status": "verified",
                        },
                        "inbound": {
                            "receive_routing_target": "dylancarsonmontgomery@gmail.com",
                            "receive_state": "inbound_verified",
                            "receive_verified": True,
                            "portal_native_display_ready": True,
                            "capture_source_reference": "s3://ses-inbound-fnd-mail/inbound/example",
                            "latest_message_has_verification_link": True,
                            "legacy_forwarder_dependency": True,
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
            cards = payload.get("profile_cards") if isinstance(payload.get("profile_cards"), list) else []
            self.assertTrue(cards)
            card_body = cards[0].get("body") if isinstance(cards[0], dict) else {}
            verification = card_body.get("verification") if isinstance(card_body.get("verification"), dict) else {}
            workflow = card_body.get("workflow") if isinstance(card_body.get("workflow"), dict) else {}
            inbound = card_body.get("inbound") if isinstance(card_body.get("inbound"), dict) else {}
            self.assertEqual(verification.get("portal_state"), "verified")
            self.assertEqual(list(workflow.get("gmail_handoff_blockers_now") or []), [])
            self.assertEqual(workflow.get("lifecycle_state"), "operational")
            self.assertEqual(workflow.get("handoff_status"), "send_as_confirmed")
            self.assertEqual(workflow.get("completion_boundary"), "completed")
            self.assertTrue(bool(workflow.get("is_send_as_confirmed")))
            self.assertTrue(bool(workflow.get("is_mailbox_operational")))
            self.assertEqual(inbound.get("receive_state"), "receive_operational")

    def test_aws_mailbox_profiles_are_listed_as_separate_units(self):
        module = _load_service_tools_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir) / "private"
            root = private_dir / "utilities" / "tools" / "aws-csm"
            root.mkdir(parents=True, exist_ok=True)
            progeny_root = private_dir / "network" / "progeny"
            progeny_root.mkdir(parents=True, exist_ok=True)
            (root / "aws-csm.tff.technicalContact.json").write_text(
                json.dumps(
                    {
                        "identity": {
                            "profile_id": "aws-csm.tff.technicalContact",
                            "tenant_id": "tff",
                            "domain": "trappfamilyfarm.com",
                            "region": "us-east-1",
                            "mailbox_local_part": "technicalContact",
                            "role": "technical_contact",
                            "operator_inbox_target": "trapp.family.farm@gmail.com",
                            "send_as_email": "technicalContact@trappfamilyfarm.com",
                        },
                        "smtp": {
                            "credentials_secret_name": "aws-cms/smtp/tff.technicalContact",
                            "credentials_secret_state": "configured",
                            "username": "AKIAREADY",
                            "send_as_email": "technicalContact@trappfamilyfarm.com",
                        },
                        "verification": {
                            "status": "not_started",
                        },
                        "provider": {
                            "aws_ses_identity_status": "verified",
                            "gmail_send_as_status": "not_started",
                        },
                        "workflow": {
                            "initiated": True,
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "aws-csm.tff.mark.json").write_text(
                json.dumps(
                    {
                        "identity": {
                            "profile_id": "aws-csm.tff.mark",
                            "tenant_id": "tff",
                            "domain": "trappfamilyfarm.com",
                            "region": "us-east-1",
                            "mailbox_local_part": "mark",
                            "role": "operator",
                            "operator_inbox_target": "trapp.family.farm@gmail.com",
                            "send_as_email": "mark@trappfamilyfarm.com",
                        },
                        "smtp": {
                            "credentials_secret_name": "aws-cms/smtp/tff.mark",
                            "credentials_secret_state": "missing",
                            "username": "",
                            "send_as_email": "mark@trappfamilyfarm.com",
                        },
                        "provider": {
                            "aws_ses_identity_status": "verified",
                            "gmail_send_as_status": "not_started",
                        },
                        "workflow": {
                            "initiated": False,
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (progeny_root / "member-trapp.json").write_text(
                json.dumps(
                    {
                        "profile_refs": {
                            "paypal_site_domain": "trappfamilyfarm.com",
                            "newsletter_ingest_address": "hermes@trappfamilyfarm.com",
                            "newsletter_sender_address": "news@trappfamilyfarm.com",
                            "newsletter_allowed_from_csv": "mark@trappfamilyfarm.com",
                            "newsletter_dispatch_mode": "aws_internal",
                        }
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
            cards = payload.get("profile_cards") if isinstance(payload.get("profile_cards"), list) else []
            self.assertEqual(len(cards), 2)
            sections = payload.get("profile_domain_sections") if isinstance(payload.get("profile_domain_sections"), list) else []
            self.assertEqual(len(sections), 1)
            self.assertEqual(sections[0].get("domain"), "trappfamilyfarm.com")
            self.assertEqual(len(sections[0].get("cards") or []), 2)
            newsletter_cards = sections[0].get("newsletter_cards") if isinstance(sections[0].get("newsletter_cards"), list) else []
            self.assertEqual(len(newsletter_cards), 1)
            self.assertEqual(newsletter_cards[0].get("sender_address"), "news@trappfamilyfarm.com")
            self.assertEqual(newsletter_cards[0].get("ingest_address"), "hermes@trappfamilyfarm.com")
            titles = [str(card.get("title") or "") for card in cards if isinstance(card, dict)]
            self.assertIn("technicalContact@trappfamilyfarm.com", titles)
            self.assertIn("mark@trappfamilyfarm.com", titles)
            by_id = {str(card.get("card_id") or ""): card for card in cards if isinstance(card, dict)}
            technical = ((by_id.get("aws-csm.tff.technicalContact") or {}).get("body") or {})
            mark = ((by_id.get("aws-csm.tff.mark") or {}).get("body") or {})
            self.assertEqual((((technical.get("smtp") or {}).get("username"))), "AKIAREADY")
            self.assertEqual((((technical.get("smtp") or {}).get("credentials_secret_state"))), "configured")
            self.assertEqual((((technical.get("verification") or {}).get("status"))), "not_started")
            self.assertEqual((((technical.get("provider") or {}).get("gmail_send_as_status"))), "not_started")
            self.assertEqual((((technical.get("workflow") or {}).get("lifecycle_state"))), "send_as_pending")
            self.assertEqual((((technical.get("workflow") or {}).get("handoff_status"))), "ready_for_gmail_handoff")
            self.assertEqual((((mark.get("workflow") or {}).get("lifecycle_state"))), "uninitiated")
            self.assertEqual((((mark.get("workflow") or {}).get("handoff_status"))), "uninitiated")
            self.assertEqual((((mark.get("smtp") or {}).get("username"))), "")
            self.assertEqual(((((technical.get("inbound") or {}).get("receive_state")))), "receive_pending")
            self.assertEqual(((((mark.get("inbound") or {}).get("receive_state")))), "receive_configured")

    def test_aws_platform_admin_service_meta_narrows_to_operator_send_as_scope(self):
        module = _load_service_tools_module()
        meta = module.build_service_tool_meta("aws_platform_admin")
        interface_panel = meta.get("interface_panel_contribution") if isinstance(meta.get("interface_panel_contribution"), dict) else {}
        self.assertEqual(interface_panel.get("label"), "AWS mailbox and newsletter operations")
        self.assertEqual(interface_panel.get("default_mode"), "overview")
        self.assertEqual(interface_panel.get("lens_id"), "service.aws_csm")
        self.assertIn("newsletter", interface_panel.get("modes") or [])
        self.assertEqual(meta.get("shell_composition_mode"), "tool")
        self.assertEqual(meta.get("foreground_surface"), "interface_panel")
        collection_datum = ((meta.get("service_contract") or {}).get("collection_datum")) or {}
        config_datum = ((meta.get("service_contract") or {}).get("config_datum")) or {}
        self.assertEqual(collection_datum.get("patterns"), ["tool.*.aws-csm.json"])
        self.assertTrue(any(str(item).startswith("aws-csm.") and str(item).endswith(".*.json") for item in (config_datum.get("patterns") or [])))
        self.assertIn("aws-csm.*.json", config_datum.get("patterns") or [])
        self.assertNotIn("aws-csm.collection.json", collection_datum.get("patterns") or [])
        self.assertIn("*audit*.json", ((meta.get("service_contract") or {}).get("member_datum") or {}).get("patterns") or [])
        self.assertEqual(module.build_service_tool_meta("aws_tenant_actions"), {})


if __name__ == "__main__":
    unittest.main()
