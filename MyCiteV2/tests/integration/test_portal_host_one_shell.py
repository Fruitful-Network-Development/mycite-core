from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None

if FLASK_AVAILABLE:
    from MyCiteV2.instances._shared.portal_host.app import V2PortalHostConfig, build_shell_asset_manifest, create_app
    from MyCiteV2.packages.adapters.filesystem.network_root_read_model import build_system_log_document


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_network_chronology_authority(data_dir: Path) -> None:
    (data_dir / "system").mkdir(parents=True, exist_ok=True)
    _write_json(
        data_dir / "system" / "anthology.json",
        {
            "1-1-1": [
                [
                    "1-1-1",
                    "0-0-1",
                    "00000010000110000000110011010101111000011011001100011101111001111101000111110100011111010001011011010111000111100111100",
                ],
                ["HOPS-chronological"],
            ]
        },
    )
    _write_json(
        data_dir / "system" / "sources" / "sc.fnd.quadrennium_cycle.json",
        {
            "datum_addressing_abstraction_space": {
                "1-1-1": [["1-1-1", "rf.0-0-1", "00000100011100000101100100011011111101110110110101110001111001111001111101000"], ["HOPS-quadrennium_cycle"]],
                "2-0-1": [["2-0-1", "~", "1-1-1"], ["HOPS-space-quadrennium"]],
                "3-1-1": [["3-1-1", "2-0-1", "0"], ["HOPS-babelette-quadrennium_cycle"]],
            }
        },
    )


def _write_aws_csm_state(private_dir: Path) -> None:
    tool_root = private_dir / "utilities" / "tools" / "aws-csm"
    tool_root.mkdir(parents=True, exist_ok=True)
    _write_json(
        tool_root / "spec.json",
        {
            "schema": "mycite.portal.tool_mediation.v1",
            "tool_id": "aws_csm",
            "label": "AWS-CSM",
        },
    )
    _write_json(
        tool_root / "tool.3-2-3-17-77-1-6-4-1-4.aws-csm.json",
        {
            "schema": "mycite.portal.tool_collection.v1",
            "tool_id": "aws_csm",
            "member_files": [
                "spec.json",
                "aws-csm-domain.cvccboard.json",
                "aws-csm.fnd.dylan.json",
                "newsletter/newsletter.fruitfulnetworkdevelopment.com.profile.json",
            ],
        },
    )
    _write_json(
        tool_root / "aws-csm-domain.cvccboard.json",
        {
            "schema": "mycite.service_tool.aws_csm.domain.v1",
            "identity": {
                "tenant_id": "cvccboard",
                "domain": "cvccboard.org",
                "region": "us-east-1",
                "hosted_zone_id": "Z05968042395KDRPX4PLG",
            },
            "dns": {
                "hosted_zone_present": True,
                "nameserver_match": True,
                "registrar_nameservers": [
                    "ns-1225.awsdns-25.org",
                    "ns-148.awsdns-18.com",
                    "ns-1765.awsdns-28.co.uk",
                    "ns-947.awsdns-54.net",
                ],
                "hosted_zone_nameservers": [
                    "ns-1225.awsdns-25.org",
                    "ns-148.awsdns-18.com",
                    "ns-1765.awsdns-28.co.uk",
                    "ns-947.awsdns-54.net",
                ],
                "mx_expected_value": "10 inbound-smtp.us-east-1.amazonaws.com",
                "mx_record_present": True,
                "mx_record_values": ["10 inbound-smtp.us-east-1.amazonaws.com"],
                "dkim_records_present": False,
                "dkim_record_values": [],
            },
            "ses": {
                "identity_exists": False,
                "identity_status": "not_started",
                "verified_for_sending_status": False,
                "dkim_status": "not_started",
                "dkim_tokens": [],
            },
            "receipt": {
                "status": "not_ready",
                "rule_name": "portal-capture-cvccboard-org",
                "expected_recipient": "cvccboard.org",
                "expected_lambda_name": "newsletter-inbound-capture",
                "bucket": "ses-inbound-fnd-mail",
                "prefix": "inbound/cvccboard.org/",
            },
            "observation": {
                "last_checked_at": "2026-04-18T00:00:00+00:00",
                "account": "065948377733",
                "role_arn": "arn:aws:iam::065948377733:role/EC2-AWSCMS-Admin",
            },
            "readiness": {
                "schema": "mycite.service_tool.aws_csm.domain_readiness.v1",
                "state": "identity_missing",
                "summary": "Create the SES domain identity to obtain DKIM tokens.",
                "blockers": ["SES domain identity has not been created yet."],
                "last_checked_at": "2026-04-18T00:00:00+00:00",
                "domain": "cvccboard.org",
            },
        },
    )
    _write_json(
        tool_root / "aws-csm.fnd.dylan.json",
        {
            "schema": "mycite.service_tool.aws_csm.profile.v1",
            "identity": {
                "profile_id": "aws-csm.fnd.dylan",
                "tenant_id": "fnd",
                "domain": "fruitfulnetworkdevelopment.com",
                "region": "us-east-1",
                "send_as_email": "dylan@fruitfulnetworkdevelopment.com",
                "single_user_email": "dylan@fruitfulnetworkdevelopment.com",
                "role": "operator",
                "mailbox_local_part": "dylan",
            },
            "workflow": {"lifecycle_state": "ready", "handoff_status": "accepted"},
            "verification": {"status": "verified", "portal_state": "verified"},
            "provider": {"gmail_send_as_status": "verified", "aws_ses_identity_status": "verified"},
            "smtp": {
                "host": "email-smtp.us-east-1.amazonaws.com",
                "port": "587",
                "username": "DYLANSMTP",
                "credentials_secret_name": "aws-cms/smtp/fnd.dylan",
                "credentials_secret_state": "configured",
                "forward_to_email": "dylan@fruitfulnetworkdevelopment.com",
            },
            "inbound": {"receive_state": "configured", "receive_verified": "yes"},
        },
    )
    newsletter_root = tool_root / "newsletter"
    _write_json(
        newsletter_root / "newsletter.fruitfulnetworkdevelopment.com.profile.json",
        {
            "domain": "fruitfulnetworkdevelopment.com",
            "list_address": "news@fruitfulnetworkdevelopment.com",
            "sender_address": "news@fruitfulnetworkdevelopment.com",
            "selected_author_profile_id": "aws-csm.fnd.dylan",
            "selected_author_address": "dylan@fruitfulnetworkdevelopment.com",
            "delivery_mode": "manual",
            "last_dispatch_id": "dispatch-001",
        },
    )
    _write_json(
        newsletter_root / "newsletter.fruitfulnetworkdevelopment.com.contacts.json",
        {
            "contacts": [
                {"email": "reader@example.com", "subscribed": True},
                {"email": "former@example.com", "subscribed": False},
            ],
            "dispatches": [{"dispatch_id": "dispatch-001"}],
        },
    )


def _write_fnd_dcm_state(private_dir: Path, webapps_root: Path) -> None:
    tool_root = private_dir / "utilities" / "tools" / "fnd-dcm"
    tool_root.mkdir(parents=True, exist_ok=True)
    _write_json(
        tool_root / "spec.json",
        {
            "schema": "mycite.portal.tool_spec.v1",
            "tool_id": "fnd-dcm",
            "mediation": {"mode": "manifest_read_only"},
        },
    )
    _write_json(
        tool_root / "tool.3-2-3-17-77-1-6-4-1-4.fnd-dcm.json",
        {
            "schema": "mycite.portal.tool_collection.v1",
            "member_files": ["spec.json", "fnd-dcm.cvcc.json", "fnd-dcm.tff.json"],
        },
    )
    _write_json(
        tool_root / "fnd-dcm.cvcc.json",
        {
            "schema": "mycite.service_tool.fnd_dcm.profile.v1",
            "domain": "cuyahogavalleycountrysideconservancy.org",
            "label": "CVCC",
            "manifest_relative_path": "assets/docs/manifest.json",
            "render_script_relative_path": "scripts/render_manifest.py",
        },
    )
    _write_json(
        tool_root / "fnd-dcm.tff.json",
        {
            "schema": "mycite.service_tool.fnd_dcm.profile.v1",
            "domain": "trappfamilyfarm.com",
            "label": "Trapp Family Farm",
            "manifest_relative_path": "assets/docs/manifest.json",
            "render_script_relative_path": "scripts/render_manifest.py",
        },
    )
    cvcc_root = webapps_root / "clients" / "cuyahogavalleycountrysideconservancy.org" / "frontend"
    tff_root = webapps_root / "clients" / "trappfamilyfarm.com" / "frontend"
    _write_json(
        cvcc_root / "assets" / "docs" / "manifest.json",
        {
            "schema": "webdz.site_content.v2",
            "site": {"name": "CVCC", "homepage_href": "index.html", "shell": {}},
            "navigation": [{"id": "home", "label": "Home", "href": "index.html"}],
            "footer": {"columns": [{"template": "rich_text"}], "copyright": "©"},
            "collections": {
                "board_profiles": {"type": "json_file", "source": "assets/docs/board_profiles.json"},
                "blog_posts": {
                    "type": "markdown_directory",
                    "directory": "assets/docs/blogs",
                    "pattern": "*.md",
                },
            },
            "pages": {
                "people": {"file": "people.html", "template": "board_directory", "content": {"collection": "board_profiles"}},
                "newsletter": {"file": "newsletter.html", "template": "article_archive", "content": {"collection": "blog_posts"}},
            },
        },
    )
    _write_json(
        cvcc_root / "assets" / "docs" / "board_profiles.json",
        [{"name": "Jane Example", "bio": ["Jane supports local farming."]}],
    )
    (cvcc_root / "assets" / "docs" / "blogs").mkdir(parents=True, exist_ok=True)
    (cvcc_root / "assets" / "docs" / "blogs" / "spring.md").write_text("# Spring\n", encoding="utf-8")
    (cvcc_root / "scripts").mkdir(parents=True, exist_ok=True)
    (cvcc_root / "scripts" / "render_manifest.py").write_text("print('ok')\n", encoding="utf-8")
    _write_json(
        tff_root / "assets" / "docs" / "manifest.json",
        {
            "schema": "webdz.site_content.v3",
            "site": {"name": "Trapp Family Farm", "homepage_href": "home.html", "shell": {}},
            "icons": {"favicon": "/favicon.svg"},
            "navigation": [{"id": "home", "label": "Home", "href": "home.html"}],
            "footer": {"columns": [{"template": "contact_lines"}], "copyright": "©"},
            "collections": {
                "newsletters": {
                    "type": "markdown_documents",
                    "items": [{"source": "assets/docs/newsletters/fall-2024.md"}],
                }
            },
            "pages": {
                "home": {"file": "home.html", "template": "home_featured"},
                "newsletter": {"file": "newsletter.html", "template": "article_archive", "content": {"collection": "newsletters"}},
            },
        },
    )
    (tff_root / "assets" / "docs" / "newsletters").mkdir(parents=True, exist_ok=True)
    (tff_root / "assets" / "docs" / "newsletters" / "fall-2024.md").write_text("# Fall\n", encoding="utf-8")
    (tff_root / "scripts").mkdir(parents=True, exist_ok=True)
    (tff_root / "scripts" / "render_manifest.py").write_text("print('ok')\n", encoding="utf-8")


class _FakeAwsCsmActionCloud:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, object]] = []
        self.domain_statuses: dict[str, dict[str, object]] = {}
        self.route_sync_calls: list[list[dict[str, object]]] = []

    def _domain_status_patch(self, domain_record: dict[str, object]) -> dict[str, object]:
        identity = dict(domain_record.get("identity") or {})
        receipt = dict(domain_record.get("receipt") or {})
        domain = str(identity.get("domain") or "").strip().lower()
        region = str(identity.get("region") or "us-east-1").strip() or "us-east-1"
        base = {
            "dns": {
                "hosted_zone_present": True,
                "nameserver_match": True,
                "registrar_nameservers": [
                    "ns-1225.awsdns-25.org",
                    "ns-148.awsdns-18.com",
                    "ns-1765.awsdns-28.co.uk",
                    "ns-947.awsdns-54.net",
                ],
                "hosted_zone_nameservers": [
                    "ns-1225.awsdns-25.org",
                    "ns-148.awsdns-18.com",
                    "ns-1765.awsdns-28.co.uk",
                    "ns-947.awsdns-54.net",
                ],
                "mx_expected_value": "10 inbound-smtp." + region + ".amazonaws.com",
                "mx_record_present": True,
                "mx_record_values": ["10 inbound-smtp." + region + ".amazonaws.com"],
                "dkim_records_present": False,
                "dkim_record_values": [],
            },
            "ses": {
                "identity_exists": False,
                "identity_status": "not_started",
                "verified_for_sending_status": False,
                "dkim_status": "not_started",
                "dkim_tokens": [],
            },
            "receipt": {
                "status": "not_ready",
                "rule_name": receipt.get("rule_name") or "portal-capture-" + domain.replace(".", "-"),
                "expected_recipient": receipt.get("expected_recipient") or domain,
                "expected_lambda_name": receipt.get("expected_lambda_name") or "newsletter-inbound-capture",
                "bucket": receipt.get("bucket") or "ses-inbound-fnd-mail",
                "prefix": receipt.get("prefix") or ("inbound/" + domain + "/"),
                "matching_rules": [],
            },
            "observation": {
                "last_checked_at": "2026-04-18T00:00:00+00:00",
                "account": "065948377733",
                "role_arn": "arn:aws:sts::065948377733:assumed-role/EC2-AWSCMS-Admin/i-0123456789abcdef0",
            },
        }
        overrides = self.domain_statuses.get(domain, {})
        for section in ("dns", "ses", "receipt", "observation"):
            if isinstance(overrides.get(section), dict):
                section_payload = dict(base.get(section) or {})
                section_payload.update(dict(overrides.get(section) or {}))
                base[section] = section_payload
        return base

    def describe_domain_status(self, domain_record: dict[str, object]) -> dict[str, object]:
        return self._domain_status_patch(domain_record)

    def ensure_domain_identity(self, domain_record: dict[str, object]) -> None:
        identity = dict(domain_record.get("identity") or {})
        domain = str(identity.get("domain") or "").strip().lower()
        self.domain_statuses[domain] = {
            **self.domain_statuses.get(domain, {}),
            "ses": {
                "identity_exists": True,
                "identity_status": "pending",
                "verified_for_sending_status": False,
                "dkim_status": "pending",
                "dkim_tokens": ["token-1", "token-2", "token-3"],
            },
        }

    def sync_domain_dns(self, domain_record: dict[str, object]) -> None:
        identity = dict(domain_record.get("identity") or {})
        domain = str(identity.get("domain") or "").strip().lower()
        self.domain_statuses[domain] = {
            **self.domain_statuses.get(domain, {}),
            "dns": {
                "hosted_zone_present": True,
                "nameserver_match": True,
                "mx_record_present": True,
                "mx_record_values": ["10 inbound-smtp.us-east-1.amazonaws.com"],
                "dkim_records_present": True,
                "dkim_record_values": [
                    "token-1.dkim.amazonses.com",
                    "token-2.dkim.amazonses.com",
                    "token-3.dkim.amazonses.com",
                ],
            },
            "ses": {
                "identity_exists": True,
                "identity_status": "verified",
                "verified_for_sending_status": True,
                "dkim_status": "verified",
                "dkim_tokens": ["token-1", "token-2", "token-3"],
            },
        }

    def ensure_domain_receipt_rule(self, domain_record: dict[str, object]) -> None:
        identity = dict(domain_record.get("identity") or {})
        domain = str(identity.get("domain") or "").strip().lower()
        self.domain_statuses[domain] = {
            **self.domain_statuses.get(domain, {}),
            "receipt": {
                "status": "ok",
                "rule_name": "portal-capture-" + domain.replace(".", "-"),
                "expected_recipient": domain,
                "expected_lambda_name": "newsletter-inbound-capture",
                "bucket": "ses-inbound-fnd-mail",
                "prefix": "inbound/" + domain + "/",
                "matching_rules": [{"rule_name": "portal-capture-" + domain.replace(".", "-")}],
            },
        }

    def supplemental_profile_patch(self, action: str, profile: dict[str, object]) -> dict[str, object]:
        identity = dict(profile.get("identity") or {})
        send_as_email = str(identity.get("send_as_email") or "").strip().lower()
        if action == "stage_smtp_credentials":
            return {
                "smtp": {
                    "host": "email-smtp.us-east-1.amazonaws.com",
                    "port": "587",
                    "username": "SMTPUSER",
                    "credentials_secret_state": "configured",
                    "credentials_secret_name": "aws-cms/smtp/fnd.alex",
                    "handoff_ready": True,
                    "forward_to_email": "ops@example.com",
                },
                "workflow": {"handoff_status": "ready_for_gmail_handoff", "is_ready_for_user_handoff": True},
                "provider": {"aws_ses_identity_status": "verified"},
            }
        if action == "refresh_provider_status":
            return {"provider": {"aws_ses_identity_status": "verified"}}
        if action == "capture_verification":
            return {
                "verification": {
                    "portal_state": "capture_ready",
                    "status": "pending",
                    "link": "https://mail.google.com/verify/example",
                    "latest_message_reference": "s3://ses-bucket/inbound/message-1",
                },
                "inbound": {
                    "receive_state": "receive_pending",
                    "portal_native_display_ready": True,
                    "latest_message_subject": "Gmail Confirmation - Send Mail as " + send_as_email,
                    "latest_message_has_verification_link": True,
                    "latest_message_s3_uri": "s3://ses-bucket/inbound/message-1",
                },
            }
        return {}

    def gmail_confirmation_evidence_satisfied(self, profile: dict[str, object]) -> bool:
        verification = dict(profile.get("verification") or {})
        inbound = dict(profile.get("inbound") or {})
        return bool(verification.get("link")) or bool(inbound.get("latest_message_has_verification_link"))

    def confirmation_evidence_satisfied(self, profile: dict[str, object]) -> bool:
        return self.gmail_confirmation_evidence_satisfied(profile)

    def describe_profile_readiness(self, profile: dict[str, object]) -> dict[str, object]:
        identity = dict(profile.get("identity") or {})
        smtp = dict(profile.get("smtp") or {})
        return {
            "schema": "mycite.v2.portal.system.tools.aws_csm.cloud_readiness.v1",
            "checked_at": "2026-04-17T00:00:00+00:00",
            "profile_id": identity.get("profile_id"),
            "smtp": {
                "status": "ready" if smtp.get("credentials_secret_state") == "configured" else "action_required",
                "credentials_secret_state": smtp.get("credentials_secret_state") or "missing",
                "secret_name": smtp.get("credentials_secret_name") or "",
                "username": smtp.get("username") or "",
                "smtp_host": smtp.get("host") or "",
                "smtp_port": smtp.get("port") or "",
                "handoff_ready": smtp.get("credentials_secret_state") == "configured",
                "message": "",
            },
            "provider": {"status": "ready", "aws_ses_identity_status": "verified", "last_checked_at": "2026-04-17T00:00:00+00:00", "message": ""},
            "inbound": {
                "status": "captured",
                "expected_recipient": identity.get("send_as_email") or "",
                "expected_lambda_name": "newsletter-inbound-capture",
                "receipt_rule": {"status": "ok"},
                "inbound_lambda": {"status": "active"},
                "latest_capture": {"s3_uri": "s3://ses-bucket/inbound/message-1", "portal_native_evidence_present": True},
                "portal_native_evidence_present": True,
                "message": "",
            },
            "confirmation": {
                "status": "ready",
                "already_verified": False,
                "can_confirm_verified": True,
                "portal_native_evidence_present": True,
                "message": "",
            },
        }

    def send_handoff_email(self, profile: dict[str, object]) -> dict[str, object]:
        identity = dict(profile.get("identity") or {})
        smtp = dict(profile.get("smtp") or {})
        payload = {
            "message_id": "ses-message-001",
            "sent_to": smtp.get("forward_to_email") or identity.get("operator_inbox_target") or "",
            "send_as_email": identity.get("send_as_email") or "",
            "username": smtp.get("username") or "SMTPUSER",
            "smtp_host": smtp.get("host") or "email-smtp.us-east-1.amazonaws.com",
            "smtp_port": smtp.get("port") or "587",
            "state": "configured",
        }
        self.sent_messages.append(payload)
        return payload

    def read_handoff_secret(self, profile: dict[str, object]) -> dict[str, object]:
        identity = dict(profile.get("identity") or {})
        smtp = dict(profile.get("smtp") or {})
        return {
            "send_as_email": identity.get("send_as_email") or "",
            "secret_name": smtp.get("credentials_secret_name") or "aws-cms/smtp/fnd.alex",
            "state": "configured",
            "username": smtp.get("username") or "SMTPUSER",
            "password": "SMTPPASS",
            "smtp_host": smtp.get("host") or "email-smtp.us-east-1.amazonaws.com",
            "smtp_port": smtp.get("port") or "587",
        }

    def sync_verification_route_map(self, *, profiles: list[dict[str, object]]) -> dict[str, object]:
        self.route_sync_calls.append(list(profiles))
        tracked = sorted(
            str((dict(item.get("identity") or {})).get("send_as_email") or "").lower()
            for item in profiles
            if isinstance(item, dict)
            and str((dict(item.get("identity") or {})).get("send_as_email") or "").strip()
        )
        return {
            "status": "success",
            "message": "Verification-forward route map synced to Lambda environment.",
            "route_count": len(tracked),
            "tracked_recipients": tracked,
            "lambda_name": "newsletter-inbound-capture",
            "changed": True,
        }


@unittest.skipUnless(FLASK_AVAILABLE, "flask is not installed")
class PortalHostOneShellIntegrationTests(unittest.TestCase):
    def test_host_serves_canonical_routes_and_shell_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            public_dir = root / "public"
            private_dir = root / "private"
            data_dir = root / "data"
            webapps_root = root / "webapps"
            for path in (public_dir, private_dir, data_dir, webapps_root):
                path.mkdir(parents=True, exist_ok=True)
            (data_dir / "system").mkdir(parents=True, exist_ok=True)
            _write_network_chronology_authority(data_dir)
            _write_json(
                data_dir / "system" / "anthology.json",
                {
                    "1-1-1": [
                        [
                            "1-1-1",
                            "0-0-1",
                            "00000010000110000000110011010101111000011011001100011101111001111101000111110100011111010001011011010111000111100111100",
                        ],
                        ["HOPS-chronological"],
                    ],
                    "1-0-1": [["1-0-1", "~", "fruitfulnetworkdevelopment.com", "", "tenant-profile-1"], ["fruitfulnetworkdevelopment.com"]],
                },
            )
            _write_json(
                data_dir / "system" / "system_log.json",
                build_system_log_document(
                    records=[
                        {
                            "source_key": "canonical-general",
                            "source_kind": "canonical_seed",
                            "source_timestamp": "2026-07-04T00:00:00Z",
                            "title": "americas_250th_anniversary_2026_07_04",
                            "label": "americas_250th_anniversary_2026_07_04",
                            "event_type_slug": "general_event",
                            "event_type_label": "general_event",
                            "status": "scheduled",
                            "counterparty": "",
                            "contract_id": "",
                            "hops_timestamp": "0-0-0-507-916-0-0-0",
                            "raw": {"kind": "calendar"},
                        }
                    ],
                    preserved_kind_labels={"general_event": "general_event"},
                ),
            )
            _write_aws_csm_state(private_dir)
            _write_fnd_dcm_state(private_dir, webapps_root)
            _write_json(
                private_dir / "config.json",
                {
                    "msn_id": "3-2-3-17-77-1-6-4-1-4",
                    "tool_exposure": {
                        "aws_csm": {"enabled": True},
                        "fnd_dcm": {"enabled": True},
                    },
                },
            )
            (public_dir / "tenant-profile-1.json").write_text(
                '{"title":"Example Profile","summary":"Public summary"}\n',
                encoding="utf-8",
            )

            config = V2PortalHostConfig(
                portal_instance_id="fnd",
                public_dir=public_dir,
                private_dir=private_dir,
                data_dir=data_dir,
                portal_domain="fruitfulnetworkdevelopment.com",
                webapps_root=webapps_root,
            )
            app = create_app(config)
            client = app.test_client()
            retired_home_route = "/portal/" + "home"
            retired_fnd_route = "/portal/" + "fnd"
            retired_tff_route = "/portal/" + "tff"

            root_response = client.get("/portal", follow_redirects=False)
            self.assertEqual(root_response.status_code, 302)
            self.assertEqual(root_response.headers["Location"], "/portal/system")
            system_response = client.get("/portal/system")
            self.assertEqual(system_response.status_code, 200)
            self.assertEqual(client.get("/portal/network").status_code, 200)
            self.assertEqual(client.get("/portal/utilities").status_code, 200)
            self.assertEqual(client.get("/portal/system/tools/aws-csm").status_code, 200)
            self.assertEqual(client.get("/portal/system/tools/cts-gis").status_code, 200)
            self.assertEqual(client.get("/portal/system/tools/fnd-dcm").status_code, 200)
            self.assertEqual(client.get("/portal/system/tools/aws", follow_redirects=False).status_code, 302)
            self.assertEqual(
                client.get("/portal/system/tools/aws", follow_redirects=False).headers["Location"],
                "/portal/system/tools/aws-csm",
            )
            self.assertEqual(client.get(retired_home_route).status_code, 404)
            self.assertEqual(client.get(retired_fnd_route).status_code, 404)
            self.assertEqual(client.get(retired_tff_route).status_code, 404)
            self.assertEqual(client.get("/portal/system/activity").status_code, 404)
            self.assertEqual(client.get("/portal/system/profile-basics").status_code, 404)
            health_response = client.get("/portal/healthz")
            self.assertEqual(health_response.status_code, 200)
            health_payload = health_response.get_json()
            if "static_files_present" in health_payload:
                self.assertTrue(all(health_payload["static_files_present"].values()))
            self.assertEqual(health_payload["shell_asset_manifest"], build_shell_asset_manifest())
            self.assertIn(
                "v2_portal_tool_surface_adapter.js",
                [entry["file"] for entry in health_payload["shell_asset_manifest"]["scripts"]["shell_modules"]],
            )

            system_html = system_response.get_data(as_text=True)
            self.assertEqual(system_html.count("data-theme-selector"), 1)
            self.assertNotIn("pagehead--withTools", system_html)
            self.assertIn("Toggle Control Panel", system_html)
            self.assertIn("Toggle Workbench", system_html)
            self.assertIn("Toggle Interface Panel", system_html)
            self.assertNotIn(">Control Panel</button>", system_html)
            self.assertNotIn(">Workbench</button>", system_html)
            self.assertIn('data-tool-panel-lock="false"', system_html)
            self.assertIn('data-shell-lockable="tool-panel"', system_html)
            self.assertIn('data-workbench-collapsed="false"', system_html)
            self.assertIn('id="v2-shell-asset-manifest"', system_html)
            for asset in (
                [health_payload["shell_asset_manifest"]["styles"]["portal_css"]]
                + [
                    health_payload["shell_asset_manifest"]["scripts"]["portal_js"],
                    health_payload["shell_asset_manifest"]["scripts"]["shell_entry"],
                ]
                + health_payload["shell_asset_manifest"]["scripts"]["shell_modules"]
            ):
                self.assertIn(asset["url"], system_html)

            shell_response = client.post(
                "/portal/api/v2/shell",
                json={
                    "schema": "mycite.v2.portal.shell.request.v1",
                    "requested_surface_id": "system.root",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                },
            )
            self.assertEqual(shell_response.status_code, 200)
            payload = shell_response.get_json()
            self.assertEqual(payload["schema"], "mycite.v2.portal.runtime.envelope.v1")
            self.assertEqual(payload["surface_id"], "system.root")
            self.assertEqual(payload["canonical_route"], "/portal/system")
            self.assertEqual(payload["canonical_query"]["file"], "anthology")
            self.assertEqual(payload["shell_composition"]["regions"]["control_panel"]["kind"], "focus_selection_panel")
            self.assertTrue(payload["shell_composition"]["inspector_collapsed"])
            self.assertTrue(payload["shell_composition"]["interface_panel_collapsed"])
            self.assertFalse(payload["shell_composition"]["workbench_collapsed"])
            self.assertEqual(
                payload["shell_composition"]["regions"]["interface_panel"],
                payload["shell_composition"]["regions"]["inspector"],
            )
            activity_items = payload["shell_composition"]["regions"]["activity_bar"]["items"]
            self.assertNotIn("system.root", [item["item_id"] for item in activity_items])
            aws_items = [item for item in activity_items if item["item_id"] == "system.tools.aws_csm"]
            self.assertEqual(len(aws_items), 1)
            self.assertEqual(aws_items[0]["label"], "AWS-CSM")
            self.assertEqual(aws_items[0]["href"], "/portal/system/tools/aws-csm")
            self.assertIn("system.tools.fnd_dcm", [item["item_id"] for item in activity_items])
            operational_payload = client.post(
                "/portal/api/v2/shell",
                json={
                    "schema": "mycite.v2.portal.shell.request.v1",
                    "requested_surface_id": "system.legacy_removed_surface",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                },
            ).get_json()
            self.assertEqual(operational_payload["surface_id"], "system.root")
            self.assertEqual(operational_payload["error"]["code"], "surface_unknown")
            network_payload = client.post(
                "/portal/api/v2/shell",
                json={
                    "schema": "mycite.v2.portal.shell.request.v1",
                    "requested_surface_id": "network.root",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                    "surface_query": {"view": "system_logs"},
                },
            ).get_json()
            self.assertEqual(network_payload["surface_id"], "network.root")
            self.assertFalse(network_payload["reducer_owned"])
            self.assertEqual(network_payload["canonical_query"], {"view": "system_logs"})
            self.assertEqual(network_payload["surface_payload"]["kind"], "network_system_log_workspace")
            self.assertEqual(network_payload["shell_composition"]["regions"]["control_panel"]["kind"], "focus_selection_panel")
            self.assertTrue(network_payload["shell_composition"]["inspector_collapsed"])
            self.assertTrue(network_payload["shell_composition"]["interface_panel_collapsed"])
            self.assertFalse(network_payload["shell_composition"]["workbench_collapsed"])

            aws_shell_payload = client.post(
                "/portal/api/v2/shell",
                json={
                    "schema": "mycite.v2.portal.shell.request.v1",
                    "requested_surface_id": "system.tools.aws_csm",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                },
            ).get_json()
            self.assertEqual(aws_shell_payload["surface_id"], "system.tools.aws_csm")
            self.assertFalse(aws_shell_payload["reducer_owned"])
            self.assertEqual(aws_shell_payload["canonical_query"], {"view": "domains"})
            self.assertEqual(aws_shell_payload["shell_composition"]["regions"]["workbench"]["kind"], "aws_csm_workbench")
            self.assertEqual(
                aws_shell_payload["shell_composition"]["regions"]["control_panel"]["context_items"],
                [
                    {"label": "Sandbox", "value": "AWS-CSM"},
                    {"label": "File", "value": "tool.3-2-3-17-77-1-6-4-1-4.aws-csm.json"},
                    {"label": "Mediation", "value": "spec.json"},
                ],
            )
            self.assertTrue(aws_shell_payload["shell_composition"]["workbench_collapsed"])
            self.assertFalse(aws_shell_payload["shell_composition"]["interface_panel_collapsed"])
            self.assertEqual(aws_shell_payload["shell_composition"]["foreground_shell_region"], "interface-panel")
            self.assertNotIn(
                "Sections",
                [
                    group["title"]
                    for group in aws_shell_payload["shell_composition"]["regions"]["control_panel"]["groups"]
                ],
            )
            self.assertFalse(aws_shell_payload["shell_composition"]["regions"]["workbench"]["visible"])
            self.assertEqual(
                aws_shell_payload["surface_payload"]["workspace"]["create_domain_defaults"]["region"],
                "us-east-1",
            )
            self.assertEqual(
                aws_shell_payload["shell_composition"]["regions"]["interface_panel"],
                aws_shell_payload["shell_composition"]["regions"]["inspector"],
            )

            tool_response = client.post(
                "/portal/api/v2/system/tools/aws-csm",
                json={"schema": "mycite.v2.portal.system.tools.aws_csm.request.v1"},
            )
            self.assertEqual(tool_response.status_code, 200)
            tool_payload = tool_response.get_json()
            self.assertEqual(tool_payload["surface_id"], "system.tools.aws_csm")
            self.assertEqual(tool_payload["canonical_query"], {"view": "domains"})
            self.assertEqual(tool_payload["surface_payload"]["kind"], "aws_csm_workspace")

            fnd_dcm_response = client.post(
                "/portal/api/v2/system/tools/fnd-dcm",
                json={"schema": "mycite.v2.portal.system.tools.fnd_dcm.request.v1"},
            )
            self.assertEqual(fnd_dcm_response.status_code, 200)
            fnd_dcm_payload = fnd_dcm_response.get_json()
            self.assertEqual(fnd_dcm_payload["surface_id"], "system.tools.fnd_dcm")
            self.assertEqual(
                fnd_dcm_payload["canonical_query"],
                {"site": "cuyahogavalleycountrysideconservancy.org", "view": "overview"},
            )
            self.assertEqual(fnd_dcm_payload["surface_payload"]["tool"]["operational"], True)
            self.assertEqual(
                fnd_dcm_payload["shell_composition"]["regions"]["control_panel"]["surface_label"],
                "FND-DCM",
            )

            cts_gis_ok = client.post(
                "/portal/api/v2/system/tools/cts-gis",
                json={"schema": "mycite.v2.portal.system.tools.cts_gis.request.v1"},
            )
            self.assertEqual(cts_gis_ok.status_code, 200)
            cts_gis_payload = cts_gis_ok.get_json()
            self.assertEqual(cts_gis_payload["surface_id"], "system.tools.cts_gis")
            shell_regions = dict((cts_gis_payload.get("shell_composition") or {}).get("regions") or {})
            inspector_region = dict(shell_regions.get("inspector") or {})
            interface_body = dict(inspector_region.get("interface_body") or {})
            garland_projection = dict(interface_body.get("garland_split_projection") or {})
            geospatial_projection = dict(garland_projection.get("geospatial_projection") or {})
            if geospatial_projection:
                self.assertIn("projection_health", geospatial_projection)
                self.assertIn("fallback_reason_codes", geospatial_projection)
                self.assertIn("focus_bounds", geospatial_projection)
                self.assertTrue(
                    geospatial_projection["projection_health"]["state"] in {"ok", "degraded", "fallback", "empty"}
                )

            cts_gis_legacy = client.post(
                "/portal/api/v2/system/tools/cts-gis",
                json={
                    "schema": "mycite.v2.portal.system.tools.cts_gis.request.v1",
                    "selected_document_id": "sandbox:" + ("map" + "s") + ":sc.legacy.json",
                },
            )
            self.assertEqual(cts_gis_legacy.status_code, 400)
            legacy_error = cts_gis_legacy.get_json()
            self.assertEqual(legacy_error["error"]["code"], "legacy_maps_alias_unsupported")

            profile_action = client.post(
                "/portal/api/v2/system/workspace/profile-basics",
                json={
                    "schema": "mycite.v2.portal.system.workspace.profile_basics.action.request.v1",
                    "profile_title": "Example Profile",
                    "profile_summary": "Workspace-owned profile summary.",
                    "contact_email": "ops@example.com",
                    "public_website_url": "https://example.com",
                },
            )
            self.assertEqual(profile_action.status_code, 200)
            profile_payload = profile_action.get_json()
            self.assertEqual(profile_payload["surface_id"], "system.root")

    def test_fnd_dcm_route_stays_available_when_webapps_root_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            public_dir = root / "public"
            private_dir = root / "private"
            data_dir = root / "data"
            webapps_root = root / "webapps"
            for path in (public_dir, private_dir, data_dir, webapps_root):
                path.mkdir(parents=True, exist_ok=True)
            _write_network_chronology_authority(data_dir)
            _write_fnd_dcm_state(private_dir, webapps_root)
            _write_json(
                private_dir / "config.json",
                {
                    "msn_id": "3-2-3-17-77-1-6-4-1-4",
                    "tool_exposure": {"fnd_dcm": {"enabled": True}},
                },
            )

            config = V2PortalHostConfig(
                portal_instance_id="fnd",
                public_dir=public_dir,
                private_dir=private_dir,
                data_dir=data_dir,
                portal_domain="fruitfulnetworkdevelopment.com",
                webapps_root=webapps_root,
            )
            object.__setattr__(config, "webapps_root", root / "missing-webapps")
            app = create_app(config)
            client = app.test_client()

            response = client.post(
                "/portal/api/v2/system/tools/fnd-dcm",
                json={
                    "schema": "mycite.v2.portal.system.tools.fnd_dcm.request.v1",
                    "surface_query": {"view": "collections", "collection": "board_profiles"},
                },
            )
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["surface_id"], "system.tools.fnd_dcm")
            self.assertFalse(payload["surface_payload"]["tool"]["operational"])
            self.assertIn("webapps_root", payload["surface_payload"]["tool"]["missing_integrations"])
            self.assertEqual(
                payload["canonical_query"],
                {"site": "cuyahogavalleycountrysideconservancy.org", "view": "collections"},
            )

    def test_aws_csm_action_route_creates_domain_and_redirects_into_domain_onboarding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            public_dir = root / "public"
            private_dir = root / "private"
            data_dir = root / "data"
            webapps_root = root / "webapps"
            audit_file = root / "portal_audit.jsonl"
            for path in (public_dir, private_dir, data_dir, webapps_root):
                path.mkdir(parents=True, exist_ok=True)
            audit_file.write_text("", encoding="utf-8")
            _write_network_chronology_authority(data_dir)
            _write_aws_csm_state(private_dir)
            _write_json(
                private_dir / "config.json",
                {"msn_id": "3-2-3-17-77-1-6-4-1-4", "tool_exposure": {"aws_csm": {"enabled": True}}},
            )

            config = V2PortalHostConfig(
                portal_instance_id="fnd",
                public_dir=public_dir,
                private_dir=private_dir,
                data_dir=data_dir,
                portal_domain="fruitfulnetworkdevelopment.com",
                webapps_root=webapps_root,
                portal_audit_storage_file=audit_file,
            )
            app = create_app(config)
            client = app.test_client()
            fake_cloud = _FakeAwsCsmActionCloud()

            with patch(
                "MyCiteV2.instances._shared.runtime.portal_aws_runtime.AwsEc2RoleOnboardingCloudAdapter",
                return_value=fake_cloud,
            ):
                create_response = client.post(
                    "/portal/api/v2/system/tools/aws-csm/actions",
                    json={
                        "schema": "mycite.v2.portal.system.tools.aws_csm.action.request.v1",
                        "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                        "surface_query": {"view": "domains"},
                        "action_kind": "create_domain",
                        "action_payload": {
                            "tenant_id": "freshboard",
                            "domain": "freshboard.org",
                            "hosted_zone_id": "Z1234567890",
                            "region": "us-east-1",
                        },
                    },
                )

            self.assertEqual(create_response.status_code, 200)
            create_payload = create_response.get_json()
            create_result = create_payload["surface_payload"]["action_result"]
            self.assertEqual(create_result["status"], "accepted")
            self.assertEqual(create_result["details"]["domain"], "freshboard.org")
            self.assertEqual(create_result["details"]["readiness_state"], "identity_missing")
            self.assertEqual(
                create_payload["canonical_query"],
                {"view": "domains", "domain": "freshboard.org", "section": "onboarding"},
            )
            created_domain_path = (
                private_dir / "utilities" / "tools" / "aws-csm" / "aws-csm-domain.freshboard.json"
            )
            self.assertTrue(created_domain_path.is_file())
            created_domain = json.loads(created_domain_path.read_text(encoding="utf-8"))
            self.assertEqual(created_domain["identity"]["domain"], "freshboard.org")
            self.assertEqual(created_domain["readiness"]["state"], "identity_missing")
            collection_payload = json.loads(
                (
                    private_dir
                    / "utilities"
                    / "tools"
                    / "aws-csm"
                    / "tool.3-2-3-17-77-1-6-4-1-4.aws-csm.json"
                ).read_text(encoding="utf-8")
            )
            self.assertIn("aws-csm-domain.freshboard.json", collection_payload["member_files"])

    def test_aws_csm_action_route_runs_add_user_flow_inside_same_surface(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            public_dir = root / "public"
            private_dir = root / "private"
            data_dir = root / "data"
            webapps_root = root / "webapps"
            audit_file = root / "portal_audit.jsonl"
            for path in (public_dir, private_dir, data_dir, webapps_root):
                path.mkdir(parents=True, exist_ok=True)
            audit_file.write_text("", encoding="utf-8")
            _write_network_chronology_authority(data_dir)
            _write_aws_csm_state(private_dir)
            _write_json(
                private_dir / "config.json",
                {"msn_id": "3-2-3-17-77-1-6-4-1-4", "tool_exposure": {"aws_csm": {"enabled": True}}},
            )

            config = V2PortalHostConfig(
                portal_instance_id="fnd",
                public_dir=public_dir,
                private_dir=private_dir,
                data_dir=data_dir,
                portal_domain="fruitfulnetworkdevelopment.com",
                webapps_root=webapps_root,
                portal_audit_storage_file=audit_file,
            )
            app = create_app(config)
            client = app.test_client()
            fake_cloud = _FakeAwsCsmActionCloud()

            def action_request(surface_query: dict[str, object], action_kind: str, action_payload: dict[str, object]) -> dict[str, object]:
                return {
                    "schema": "mycite.v2.portal.system.tools.aws_csm.action.request.v1",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                    "surface_query": surface_query,
                    "action_kind": action_kind,
                    "action_payload": action_payload,
                }

            with patch(
                "MyCiteV2.instances._shared.runtime.portal_aws_runtime.AwsEc2RoleOnboardingCloudAdapter",
                return_value=fake_cloud,
            ):
                create_response = client.post(
                    "/portal/api/v2/system/tools/aws-csm/actions",
                    json=action_request(
                        {"view": "domains", "domain": "cvccboard.org", "section": "users"},
                        "create_profile",
                        {
                            "domain": "cvccboard.org",
                            "mailbox_local_part": "alex",
                            "single_user_email": "alex@example.com",
                            "operator_inbox_target": "ops@example.com",
                        },
                    ),
                )
                self.assertEqual(create_response.status_code, 200)
                create_payload = create_response.get_json()
                create_result = create_payload["surface_payload"]["action_result"]
                self.assertEqual(create_result["status"], "accepted")
                self.assertEqual(create_result["created_profile"]["profile_id"], "aws-csm.cvccboard.alex")
                self.assertEqual(create_result["details"]["route_sync_status"], "success")
                self.assertEqual(
                    create_payload["canonical_query"],
                    {"view": "domains", "domain": "cvccboard.org", "profile": "aws-csm.cvccboard.alex", "section": "onboarding"},
                )
                self.assertEqual(
                    create_payload["shell_composition"]["regions"]["workbench"]["kind"],
                    "aws_csm_workbench",
                )

                created_profile_path = (
                    private_dir / "utilities" / "tools" / "aws-csm" / "aws-csm.cvccboard.alex.json"
                )
                self.assertTrue(created_profile_path.is_file())
                collection_payload = json.loads(
                    (
                        private_dir
                        / "utilities"
                        / "tools"
                        / "aws-csm"
                        / "tool.3-2-3-17-77-1-6-4-1-4.aws-csm.json"
                    ).read_text(encoding="utf-8")
                )
                self.assertIn("aws-csm.cvccboard.alex.json", collection_payload["member_files"])

                active_query = create_payload["canonical_query"]
                for action_kind in (
                    "stage_smtp_credentials",
                    "send_handoff_email",
                    "reveal_smtp_password",
                    "capture_verification",
                    "confirm_verified",
                    "confirm_verified_attested",
                ):
                    action_response = client.post(
                        "/portal/api/v2/system/tools/aws-csm/actions",
                        json=action_request(active_query, action_kind, {"profile_id": "aws-csm.fnd.alex"}),
                    )
                    self.assertEqual(action_response.status_code, 200)
                    action_payload = action_response.get_json()
                    self.assertEqual(action_payload["surface_payload"]["action_result"]["status"], "accepted")
                    active_query = action_payload["canonical_query"]
                    if action_kind == "stage_smtp_credentials":
                        self.assertEqual(
                            action_payload["surface_payload"]["action_result"]["details"]["route_sync_status"],
                            "success",
                        )

                    if action_kind == "send_handoff_email":
                        dispatch = action_payload["surface_payload"]["action_result"]["handoff_dispatch"]
                        self.assertEqual(dispatch["sent_to"], "ops@example.com")
                    if action_kind == "reveal_smtp_password":
                        secret = action_payload["surface_payload"]["action_result"]["ephemeral_secret"]
                        self.assertEqual(secret["password"], "SMTPPASS")

                stored_profile = json.loads(created_profile_path.read_text(encoding="utf-8"))
                self.assertEqual(stored_profile["identity"]["tenant_id"], "cvccboard")
                self.assertEqual(stored_profile["smtp"]["username"], "SMTPUSER")
                self.assertEqual(stored_profile["verification"]["status"], "verified")
                self.assertEqual(stored_profile["provider"]["send_as_provider_status"], "verified")
                self.assertIn(stored_profile["provider"]["gmail_send_as_status"], {"verified", "not_started"})
                self.assertNotIn("SMTPPASS", created_profile_path.read_text(encoding="utf-8"))
                self.assertNotIn("SMTPPASS", audit_file.read_text(encoding="utf-8"))

    def test_client_boot_prefers_server_shell_posture_on_first_v2_hydration(self) -> None:
        portal_js = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "portal.js"
        ).read_text(encoding="utf-8")
        shell_core = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_shell_core.js"
        ).read_text(encoding="utf-8")

        self.assertIn("firstV2ShellCompositionApplied", portal_js)
        self.assertIn("applyShellPostureFromDom({ useStoredWorkbenchPreference: false })", portal_js)
        self.assertIn("syncFromDom: (options) => layoutApi.syncFromDom && layoutApi.syncFromDom(options)", portal_js)
        self.assertIn("routeKeyFromUrl", shell_core)
        self.assertIn("fromShellComposition: true", shell_core)
        self.assertIn("routeKey: routeKey", shell_core)


if __name__ == "__main__":
    unittest.main()
