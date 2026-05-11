"""Tests for the FND-CSM tool runtime — grantee-aware service management."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_fnd_csm_runtime import (
    _apply_fnd_csm_action,
    _build_analytics_tab,
    _build_analytics_component_group,
    _build_email_component_group,
    _build_newsletter_component_group,
    _build_newsletter_tab,
    _build_paypal_component_group,
    _build_paypal_tab,
    _fnd_csm_render_key,
    _load_grantee_profiles,
    _normalize_fnd_csm_tool_state,
    build_portal_fnd_csm_surface_bundle,
)
from MyCiteV2.instances._shared.runtime.portal_fnd_csm_runtime import (
    GRANTEE_PROFILE_SCHEMA,
)
from MyCiteV2.packages.state_machine.portal_shell import (
    FND_CSM_TOOL_SURFACE_ID,
    PortalScope,
    initial_portal_shell_state,
)


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _grantee(msn_id: str, label: str, domains: list[str], users: list[str]) -> dict:
    return {
        "schema": GRANTEE_PROFILE_SCHEMA,
        "msn_id": msn_id,
        "label": label,
        "short_name": label[:3].upper(),
        "domains": domains,
        "users": users,
    }


class FndCsmRuntimeGranteeProfileTests(unittest.TestCase):
    def test_grantee_profiles_loaded_sorted_by_label(self) -> None:
        with TemporaryDirectory() as tmp:
            fnd_csm_dir = Path(tmp) / "utilities" / "tools" / "fnd-csm"
            _write(fnd_csm_dir / "grantee.fnd.tff.json", _grantee("tff", "Trapp Family Farm", ["trappfamilyfarm.com"], ["info@trappfamilyfarm.com"]))
            _write(fnd_csm_dir / "grantee.fnd.cvcc.json", _grantee("cvcc", "CVCC", ["cvcc.org"], ["admin@cvcc.org"]))

            profiles = _load_grantee_profiles(tmp)
            self.assertEqual(len(profiles), 2)
            self.assertEqual(profiles[0]["label"], "CVCC")
            self.assertEqual(profiles[1]["label"], "Trapp Family Farm")

    def test_grantee_profiles_empty_when_private_dir_is_none(self) -> None:
        self.assertEqual(_load_grantee_profiles(None), [])

    def test_grantee_profiles_skips_invalid_schema(self) -> None:
        with TemporaryDirectory() as tmp:
            fnd_csm_dir = Path(tmp) / "utilities" / "tools" / "fnd-csm"
            _write(fnd_csm_dir / "grantee.fnd.tff.json", {"schema": "wrong.schema", "msn_id": "tff"})
            _write(fnd_csm_dir / "grantee.fnd.valid.json", _grantee("valid", "Valid Co", ["valid.com"], []))
            profiles = _load_grantee_profiles(tmp)
            self.assertEqual(len(profiles), 1)
            self.assertEqual(profiles[0]["msn_id"], "valid")


class FndCsmRuntimeAnalyticsTabTests(unittest.TestCase):
    def test_analytics_tab_aggregates_events_by_type(self) -> None:
        with TemporaryDirectory() as tmp:
            events_dir = Path(tmp) / "clients" / "example.com" / "analytics" / "events"
            events_dir.mkdir(parents=True)
            events_ndjson = events_dir / "2026-04.ndjson"
            events_ndjson.write_text(
                '{"event_type": "page_view", "path": "/home"}\n'
                '{"event_type": "page_view", "path": "/about"}\n'
                '{"event_type": "form_submit", "path": "/contact"}\n',
                encoding="utf-8",
            )
            tab = _build_analytics_tab("example.com", tmp)
            self.assertEqual(tab["summary"]["page_view"], 2)
            self.assertEqual(tab["summary"]["form_submit"], 1)
            self.assertEqual(tab["domain"], "example.com")
            self.assertTrue(tab["events_dir_present"])

    def test_analytics_tab_empty_when_no_events_dir(self) -> None:
        with TemporaryDirectory() as tmp:
            tab = _build_analytics_tab("example.com", tmp)
            self.assertEqual(tab["summary"]["page_view"], 0)
            self.assertFalse(tab["events_dir_present"])

    def test_analytics_tab_empty_when_no_domain_or_root(self) -> None:
        tab = _build_analytics_tab("", None)
        self.assertEqual(tab["summary"], {})
        self.assertEqual(tab["recent_events"], [])


class FndCsmRuntimeNewsletterTabTests(unittest.TestCase):
    def test_newsletter_tab_returns_users_as_sender_options(self) -> None:
        users = ["info@example.com", "news@example.com"]
        grantee = _grantee("g1", "Example", ["example.com"], users)
        tab = _build_newsletter_tab(grantee, "example.com", None)
        self.assertEqual(tab["sender_options"], users)
        self.assertEqual(tab["contact_rows"], [])
        self.assertEqual(tab["current_sender"], "")

    def test_newsletter_tab_reads_contact_log_when_private_dir_set(self) -> None:
        with TemporaryDirectory() as tmp:
            private_dir = Path(tmp)
            # Path: {private_dir}/utilities/tools/aws-csm/newsletter/newsletter.{domain}.contacts.json
            contact_log_path = private_dir / "utilities" / "tools" / "aws-csm" / "newsletter" / "newsletter.example.com.contacts.json"
            _write(contact_log_path, {
                "schema": "mycite.service_tool.aws_csm.newsletter_contact_log.v1",
                "domain": "example.com",
                "contacts": [
                    {"email": "a@example.com", "subscribed": True, "source": "website_signup", "last_newsletter_sent_at": "", "send_count": 0},
                    {"email": "b@example.com", "subscribed": False, "source": "website_signup", "last_newsletter_sent_at": "", "send_count": 1},
                ],
                "dispatches": [],
            })
            grantee = _grantee("g1", "Example", ["example.com"], ["info@example.com"])
            tab = _build_newsletter_tab(grantee, "example.com", private_dir)
            self.assertEqual(len(tab["contact_rows"]), 2)
            self.assertEqual(tab["subscribed_count"], 1)
            self.assertEqual(tab["unsubscribed_count"], 1)


class FndCsmRuntimePaypalTabTests(unittest.TestCase):
    def test_paypal_tab_reads_orders_for_domain(self) -> None:
        with TemporaryDirectory() as tmp:
            private_dir = Path(tmp)
            orders_path = private_dir / "utilities" / "tools" / "paypal-csm" / "orders.ndjson"
            orders_path.parent.mkdir(parents=True)
            orders_path.write_text(
                '{"event":"create_order","order_id":"A","amount":"10.00","domain":"example.com","status":"CREATED"}\n'
                '{"event":"create_order","order_id":"B","amount":"25.00","domain":"other.com","status":"CREATED"}\n',
                encoding="utf-8",
            )
            grantee = _grantee("g1", "Example", ["example.com"], [])
            tab = _build_paypal_tab(grantee, "example.com", private_dir)
            self.assertEqual(len(tab["orders"]), 1)
            self.assertEqual(tab["orders"][0]["order_id"], "A")

    def test_paypal_tab_empty_when_no_orders_file(self) -> None:
        with TemporaryDirectory() as tmp:
            grantee = _grantee("g1", "Example", ["example.com"], [])
            tab = _build_paypal_tab(grantee, "example.com", tmp)
            self.assertEqual(tab["orders"], [])
            self.assertEqual(tab["webhook_url"], "")


class FndCsmRuntimeActionTests(unittest.TestCase):
    def test_select_grantee_action_updates_tool_state(self) -> None:
        tool_state = {"selected_grantee_msn": "old", "selected_domain": "x.com", "active_tab": "email"}
        next_state, result = _apply_fnd_csm_action(
            action_kind="select_grantee",
            action_payload={"msn_id": "new_msn"},
            tool_state=tool_state,
            private_dir=None,
        )
        self.assertEqual(next_state["selected_grantee_msn"], "new_msn")
        self.assertEqual(next_state["selected_domain"], "")
        self.assertEqual(result["status"], "accepted")

    def test_select_domain_action_updates_tool_state(self) -> None:
        tool_state = {"selected_grantee_msn": "g1", "selected_domain": "", "active_tab": "email"}
        next_state, result = _apply_fnd_csm_action(
            action_kind="select_domain",
            action_payload={"domain": "Example.COM"},
            tool_state=tool_state,
            private_dir=None,
        )
        self.assertEqual(next_state["selected_domain"], "example.com")
        self.assertEqual(result["status"], "accepted")

    def test_assign_newsletter_sender_rejected_when_missing_required_fields(self) -> None:
        tool_state = _normalize_fnd_csm_tool_state({})
        _, result = _apply_fnd_csm_action(
            action_kind="assign_newsletter_sender",
            action_payload={"domain": ""},
            tool_state=tool_state,
            private_dir=None,
        )
        self.assertEqual(result["status"], "rejected")

    def test_update_contact_subscription_rejected_when_missing_fields(self) -> None:
        tool_state = _normalize_fnd_csm_tool_state({})
        _, result = _apply_fnd_csm_action(
            action_kind="update_contact_subscription",
            action_payload={},
            tool_state=tool_state,
            private_dir=None,
        )
        self.assertEqual(result["status"], "rejected")


class FndCsmRuntimeBundleTests(unittest.TestCase):
    def test_bundle_emits_four_tabs_when_grantees_loaded(self) -> None:
        with TemporaryDirectory() as tmp:
            private_dir = Path(tmp)
            fnd_csm_dir = private_dir / "utilities" / "tools" / "fnd-csm"
            _write(fnd_csm_dir / "grantee.fnd.tff.json", _grantee("tff", "TFF", ["trappfamilyfarm.com"], ["info@trappfamilyfarm.com"]))

            portal_scope = PortalScope(scope_id="fnd", capabilities=("fnd_peripheral_routing",))
            shell_state = initial_portal_shell_state(
                surface_id=FND_CSM_TOOL_SURFACE_ID,
                portal_scope=portal_scope.to_dict(),
            )
            bundle = build_portal_fnd_csm_surface_bundle(
                portal_scope=portal_scope,
                shell_state=shell_state,
                private_dir=private_dir,
                webapps_root=None,
                request_payload={},
                tool_exposure_policy=None,
                tool_rows=[],
            )
            # interface_panel is the region dict itself — tabs are at the top level
            interface_panel = bundle["interface_panel"]
            tab_ids = [t["id"] for t in interface_panel.get("tabs", [])]
            self.assertIn("email", tab_ids)
            self.assertIn("analytics", tab_ids)
            self.assertIn("newsletter", tab_ids)
            self.assertIn("paypal", tab_ids)

    def test_bundle_shows_no_grantees_when_private_dir_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            portal_scope = PortalScope(scope_id="fnd", capabilities=("fnd_peripheral_routing",))
            shell_state = initial_portal_shell_state(
                surface_id=FND_CSM_TOOL_SURFACE_ID,
                portal_scope=portal_scope.to_dict(),
            )
            bundle = build_portal_fnd_csm_surface_bundle(
                portal_scope=portal_scope,
                shell_state=shell_state,
                private_dir=tmp,
                webapps_root=None,
                request_payload={},
                tool_exposure_policy=None,
                tool_rows=[],
            )
            # No grantees → grantees list is empty in surface_payload
            self.assertEqual(bundle["surface_payload"]["grantees"], [])

    def test_bundle_has_region_family_contracts(self) -> None:
        with TemporaryDirectory() as tmp:
            portal_scope = PortalScope(scope_id="fnd", capabilities=("fnd_peripheral_routing",))
            shell_state = initial_portal_shell_state(
                surface_id=FND_CSM_TOOL_SURFACE_ID,
                portal_scope=portal_scope.to_dict(),
            )
            bundle = build_portal_fnd_csm_surface_bundle(
                portal_scope=portal_scope,
                shell_state=shell_state,
                private_dir=tmp,
                webapps_root=None,
                request_payload={},
                tool_exposure_policy=None,
                tool_rows=[],
            )
            self.assertIn("family_contract", bundle["control_panel"])
            self.assertIn("family_contract", bundle["workbench"])
            self.assertIn("family_contract", bundle["interface_panel"])
            self.assertEqual(bundle["control_panel"]["family_contract"]["family"], "directive_panel")
            self.assertEqual(bundle["workbench"]["family_contract"]["family"], "reflective_workspace")
            self.assertEqual(bundle["interface_panel"]["family_contract"]["family"], "presentation_surface")


class FndCsmComponentFrameTests(unittest.TestCase):
    """Tests for canonical component frame builder functions."""

    def test_email_frames_include_mailboxes_characteristic_set(self) -> None:
        email_tab = {
            "profiles": [{"send_as": "info@ex.com", "role": "admin", "lifecycle": "active", "inbound": "enabled"}],
            "domain_record": {},
        }
        group = _build_email_component_group(email_tab, "g1", "ex.com", "")
        self.assertEqual(group["component_type"], "component_group")
        self.assertEqual(group["frame_id"], "fnd_csm.tab.email")
        child_ids = [c["frame_id"] for c in group["payload"]["children"]]
        self.assertIn("fnd_csm.email.mailboxes", child_ids)

    def test_analytics_frames_include_summary_and_events(self) -> None:
        analytics_tab = {
            "summary": {"page_view": 5, "form_submit": 2, "ops_probe": 0, "other": 1},
            "recent_events": [{"event_type": "page_view", "path": "/", "timestamp": "2026-05-01T00:00:00Z"}],
        }
        group = _build_analytics_component_group(analytics_tab, "g1", "ex.com", "")
        child_ids = [c["frame_id"] for c in group["payload"]["children"]]
        self.assertIn("fnd_csm.analytics.summary", child_ids)
        self.assertIn("fnd_csm.analytics.events", child_ids)

    def test_newsletter_frames_include_sender_and_contacts(self) -> None:
        nl_tab = {
            "current_sender": "info@ex.com",
            "sender_options": ["info@ex.com"],
            "contact_rows": [],
            "subscribed_count": 0,
            "unsubscribed_count": 0,
        }
        group = _build_newsletter_component_group(nl_tab, "g1", "ex.com", "")
        child_ids = [c["frame_id"] for c in group["payload"]["children"]]
        self.assertIn("fnd_csm.newsletter.sender", child_ids)
        self.assertIn("fnd_csm.newsletter.contacts", child_ids)

    def test_paypal_frames_include_webhook_and_orders(self) -> None:
        paypal_tab = {"webhook_url": "", "orders": []}
        group = _build_paypal_component_group(paypal_tab, "g1", "ex.com", "")
        child_ids = [c["frame_id"] for c in group["payload"]["children"]]
        self.assertIn("fnd_csm.paypal.webhook", child_ids)
        self.assertIn("fnd_csm.paypal.orders", child_ids)

    def test_engage_frame_action_sets_engaged_frame_id_in_tool_state(self) -> None:
        tool_state = _normalize_fnd_csm_tool_state({})
        next_state, result = _apply_fnd_csm_action(
            action_kind="engage_component_frame",
            action_payload={"frame_id": "fnd_csm.tab.email"},
            tool_state=tool_state,
            private_dir=None,
        )
        self.assertEqual(next_state["engaged_frame_id"], "fnd_csm.tab.email")
        self.assertEqual(result["status"], "accepted")

    def test_engaged_frame_id_produces_different_render_key_for_targeted_frame(self) -> None:
        base_rk = _fnd_csm_render_key("g1", "ex.com", "fnd_csm.tab.email", "")
        engaged_rk = _fnd_csm_render_key("g1", "ex.com", "fnd_csm.tab.email", "fnd_csm.tab.email")
        other_rk = _fnd_csm_render_key("g1", "ex.com", "fnd_csm.tab.analytics", "fnd_csm.tab.email")
        self.assertNotEqual(base_rk, engaged_rk)
        self.assertEqual(other_rk, _fnd_csm_render_key("g1", "ex.com", "fnd_csm.tab.analytics", ""))

    def test_bundle_interface_panel_has_four_component_group_frames(self) -> None:
        with TemporaryDirectory() as tmp:
            private_dir = Path(tmp)
            fnd_csm_dir = private_dir / "utilities" / "tools" / "fnd-csm"
            _write(fnd_csm_dir / "grantee.fnd.tff.json", _grantee("tff", "TFF", ["tff.com"], ["info@tff.com"]))
            portal_scope = PortalScope(scope_id="fnd", capabilities=("fnd_peripheral_routing",))
            shell_state = initial_portal_shell_state(
                surface_id=FND_CSM_TOOL_SURFACE_ID,
                portal_scope=portal_scope.to_dict(),
            )
            bundle = build_portal_fnd_csm_surface_bundle(
                portal_scope=portal_scope,
                shell_state=shell_state,
                private_dir=private_dir,
                webapps_root=None,
                request_payload={},
                tool_exposure_policy=None,
            )
            frames = bundle["interface_panel"].get("component_frames", [])
            self.assertEqual(len(frames), 4)
            frame_ids = {f["frame_id"] for f in frames}
            self.assertEqual(frame_ids, {
                "fnd_csm.tab.email",
                "fnd_csm.tab.analytics",
                "fnd_csm.tab.newsletter",
                "fnd_csm.tab.paypal",
            })

    def test_bundle_interface_panel_tabs_all_have_initializers(self) -> None:
        with TemporaryDirectory() as tmp:
            portal_scope = PortalScope(scope_id="fnd", capabilities=("fnd_peripheral_routing",))
            shell_state = initial_portal_shell_state(
                surface_id=FND_CSM_TOOL_SURFACE_ID,
                portal_scope=portal_scope.to_dict(),
            )
            bundle = build_portal_fnd_csm_surface_bundle(
                portal_scope=portal_scope,
                shell_state=shell_state,
                private_dir=tmp,
                webapps_root=None,
                request_payload={},
                tool_exposure_policy=None,
            )
            tabs = bundle["interface_panel"].get("tabs", [])
            self.assertEqual(len(tabs), 4)
            for tab in tabs:
                self.assertIn("initializer", tab, f"Tab {tab.get('id')} missing initializer")
                self.assertEqual(tab["initializer"]["verb"], "mediate")
                self.assertEqual(tab["initializer"]["target_authority"], "fnd_csm")


if __name__ == "__main__":
    unittest.main()
