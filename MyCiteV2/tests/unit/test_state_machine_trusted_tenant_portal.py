from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.state_machine.trusted_tenant_portal import (
    BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
    BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
    BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
    BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID,
    TRUSTED_TENANT_AUDIT_ACTIVITY_REQUEST_SCHEMA,
    TRUSTED_TENANT_CANONICAL_LANDING_PAGE_ROUTE,
    TRUSTED_TENANT_OPERATIONAL_STATUS_REQUEST_SCHEMA,
    TRUSTED_TENANT_PORTAL_REQUEST_SCHEMA,
    TRUSTED_TENANT_PROFILE_BASICS_WRITE_REQUEST_SCHEMA,
    TrustedTenantPortalRequest,
    build_trusted_tenant_portal_dispatch_bodies,
    build_trusted_tenant_portal_route_catalog,
    build_trusted_tenant_portal_surface_catalog,
    resolve_trusted_tenant_portal_request,
)


class TrustedTenantPortalStateMachineTests(unittest.TestCase):
    def test_request_defaults_to_band1_home_slice(self) -> None:
        request = TrustedTenantPortalRequest()

        self.assertEqual(
            request.to_dict(),
            {
                "schema": TRUSTED_TENANT_PORTAL_REQUEST_SCHEMA,
                "requested_slice_id": BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
                "tenant_scope": {"scope_id": "fnd", "audience": "trusted-tenant"},
            },
        )

    def test_home_slice_is_available_for_trusted_tenant_and_unknown_slice_is_denied(self) -> None:
        allowed = resolve_trusted_tenant_portal_request(
            {
                "schema": TRUSTED_TENANT_PORTAL_REQUEST_SCHEMA,
                "requested_slice_id": BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
                "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
            }
        )
        unknown = resolve_trusted_tenant_portal_request(
            {
                "schema": TRUSTED_TENANT_PORTAL_REQUEST_SCHEMA,
                "requested_slice_id": "band1.unknown",
                "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
            }
        )

        self.assertTrue(allowed.allowed)
        self.assertEqual(allowed.active_surface_id, BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID)
        self.assertFalse(unknown.allowed)
        self.assertEqual(unknown.selection_status, "unknown")
        self.assertEqual(unknown.reason_code, "slice_unknown")

    def test_non_trusted_audience_is_denied_by_selection(self) -> None:
        selection = resolve_trusted_tenant_portal_request(
            {
                "schema": TRUSTED_TENANT_PORTAL_REQUEST_SCHEMA,
                "requested_slice_id": BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
                "tenant_scope": {"scope_id": "tff", "audience": "internal"},
            }
        )

        self.assertFalse(selection.allowed)
        self.assertEqual(selection.selection_status, "audience_denied")
        self.assertEqual(selection.reason_code, "audience_not_allowed")

    def test_catalog_routes_and_dispatch_bodies_are_serializable(self) -> None:
        catalog = [entry.to_dict() for entry in build_trusted_tenant_portal_surface_catalog()]
        routes = list(build_trusted_tenant_portal_route_catalog())
        bodies = build_trusted_tenant_portal_dispatch_bodies(portal_tenant_id="tff")

        self.assertEqual(json.loads(json.dumps(catalog, sort_keys=True)), catalog)
        self.assertEqual(json.loads(json.dumps(routes, sort_keys=True)), routes)
        self.assertEqual(json.loads(json.dumps(bodies, sort_keys=True)), bodies)
        self.assertEqual(
            [entry["slice_id"] for entry in catalog],
            [
                BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
                BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
                BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
                BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID,
            ],
        )
        self.assertEqual(catalog[0]["page_route"], TRUSTED_TENANT_CANONICAL_LANDING_PAGE_ROUTE)
        self.assertEqual(catalog[0]["control_panel_kind"], "tenant_home_control_panel")
        self.assertEqual(catalog[1]["control_panel_kind"], "tenant_operational_status_control_panel")
        self.assertEqual(catalog[2]["control_panel_kind"], "tenant_audit_activity_control_panel")
        self.assertEqual(catalog[3]["control_panel_kind"], "tenant_profile_basics_control_panel")
        self.assertEqual(catalog[0]["surface_posture"], "pending_audit")
        self.assertEqual(routes[0]["page_route"], TRUSTED_TENANT_CANONICAL_LANDING_PAGE_ROUTE)
        self.assertEqual(
            [route["request_schema"] for route in routes],
            [
                TRUSTED_TENANT_PORTAL_REQUEST_SCHEMA,
                TRUSTED_TENANT_OPERATIONAL_STATUS_REQUEST_SCHEMA,
                TRUSTED_TENANT_AUDIT_ACTIVITY_REQUEST_SCHEMA,
                TRUSTED_TENANT_PROFILE_BASICS_WRITE_REQUEST_SCHEMA,
            ],
        )
        self.assertEqual(
            bodies[BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID],
            {
                "schema": TRUSTED_TENANT_PORTAL_REQUEST_SCHEMA,
                "requested_slice_id": BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
                "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
            },
        )
        self.assertEqual(
            bodies[BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID],
            {
                "schema": TRUSTED_TENANT_OPERATIONAL_STATUS_REQUEST_SCHEMA,
                "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
            },
        )
        self.assertEqual(
            bodies[BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID],
            {
                "schema": TRUSTED_TENANT_AUDIT_ACTIVITY_REQUEST_SCHEMA,
                "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
            },
        )
        self.assertEqual(
            bodies[BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID],
            {
                "schema": TRUSTED_TENANT_PROFILE_BASICS_WRITE_REQUEST_SCHEMA,
                "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
            },
        )


if __name__ == "__main__":
    unittest.main()
