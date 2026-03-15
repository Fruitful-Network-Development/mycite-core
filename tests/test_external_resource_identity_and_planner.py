from __future__ import annotations

import unittest

from portals._shared.portal.data_engine.external_resources.isolate_identity import compute_isolate_identity
from portals._shared.portal.data_engine.external_resources.write_planner import plan_local_materialization


class ExternalResourceIdentityPlannerTests(unittest.TestCase):
    def test_isolate_identity_stable_for_same_inputs(self):
        a = compute_isolate_identity(
            source_msn_id="9-9-9-9",
            resource_id="farm_metrics",
            export_family="mycite.public.resource.v1",
            payload_sha256="abc",
            closure_signature="def",
            wire_variant="mycite.public.resource.v1",
        )
        b = compute_isolate_identity(
            source_msn_id="9-9-9-9",
            resource_id="farm_metrics",
            export_family="mycite.public.resource.v1",
            payload_sha256="abc",
            closure_signature="def",
            wire_variant="mycite.public.resource.v1",
        )
        self.assertEqual(a, b)

    def test_write_planner_reports_sparse_materialization(self):
        plan = plan_local_materialization(
            local_msn_id="3-2-3-17-77-1-6-4-1-4",
            anthology_payload={"rows": [{"identifier": "5-0-2", "label": "Local Existing"}]},
            target_ref="5-9-9",
            required_refs=["9-9-9-9.5-0-1", "3-2-3-17-77-1-6-4-1-4.5-0-2"],
            bundle_refs=["9-9-9-9.5-0-1"],
            allow_auto_create=False,
        )
        payload = plan.to_dict()
        self.assertTrue(payload["ok"])
        self.assertIn("9-9-9-9.5-0-1", payload["satisfiable_from_bundle_refs"])
        self.assertTrue(any(item.get("action") == "create_target" for item in payload["ordered_writes"]))


if __name__ == "__main__":
    unittest.main()
