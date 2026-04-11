from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.state_machine.trusted_tenant_portal import (
    BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
    TRUSTED_TENANT_PORTAL_REQUEST_SCHEMA,
    TrustedTenantPortalRequest,
    build_trusted_tenant_portal_dispatch_bodies,
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

    def test_catalog_and_dispatch_bodies_are_serializable(self) -> None:
        catalog = [entry.to_dict() for entry in build_trusted_tenant_portal_surface_catalog()]
        bodies = build_trusted_tenant_portal_dispatch_bodies(portal_tenant_id="tff")

        self.assertEqual(json.loads(json.dumps(catalog, sort_keys=True)), catalog)
        self.assertEqual(json.loads(json.dumps(bodies, sort_keys=True)), bodies)
        self.assertEqual(
            catalog,
            [
                {
                    "slice_id": BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
                    "label": "Portal Home and Tenant Status",
                    "exposure_status": "implemented_trusted_tenant_read_only",
                    "read_write_posture": "read-only",
                    "status_summary": "default_landing",
                    "surface_kind": "tenant_home_status",
                    "launchable": True,
                    "default_surface": True,
                }
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


if __name__ == "__main__":
    unittest.main()
