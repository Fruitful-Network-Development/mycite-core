from __future__ import annotations

import sys
import unittest
from pathlib import Path

portals_root = Path(__file__).resolve().parents[1] / "instances"
token = str(portals_root)
if token not in sys.path:
    sys.path.insert(0, token)

from _shared.portal.data_engine.inherited_txa_adapter import (  # noqa: E402
    adapt_published_txa_resource_value,
    select_inherited_binding_for_field,
)


class InheritedTxaAdapterTests(unittest.TestCase):
    def test_deterministic_binding_prefers_product_and_invoice_buckets(self):
        payload = {
            "resource_id": "txa.local",
            "resource_kind": "txa",
            "source_msn_id": "9-9-9",
            "published_value": {
                "field_ref_bindings": {
                    "all_refs": ["9-9-9.8-4-2", "9-9-9.8-5-3"],
                    "product_profile_refs": ["9-9-9.8-5-3"],
                    "invoice_log_refs": ["9-9-9.8-4-2"],
                }
            },
        }
        adapted_one = adapt_published_txa_resource_value(payload=payload, context_source="unit")
        adapted_two = adapt_published_txa_resource_value(payload=payload, context_source="unit")
        self.assertEqual(adapted_one.get("field_ref_bindings"), adapted_two.get("field_ref_bindings"))

        product = select_inherited_binding_for_field(
            field_id="inherited_product_profile_ref",
            field_ref_bindings=adapted_one.get("field_ref_bindings"),
        )
        invoice = select_inherited_binding_for_field(
            field_id="inherited_supply_log_ref",
            field_ref_bindings=adapted_one.get("field_ref_bindings"),
        )
        self.assertEqual(product.get("selected_ref"), "9-9-9.8-5-3")
        self.assertEqual(product.get("selection_source"), "product_profile_refs")
        self.assertEqual(invoice.get("selected_ref"), "9-9-9.8-4-2")
        self.assertEqual(invoice.get("selection_source"), "invoice_log_refs")

    def test_fallback_to_all_refs_emits_explicit_warning(self):
        bindings = {"all_refs": ["7-7-7.8-5-5"], "product_profile_refs": [], "invoice_log_refs": []}
        selected = select_inherited_binding_for_field(
            field_id="inherited_supply_log_ref",
            field_ref_bindings=bindings,
        )
        self.assertEqual(selected.get("selected_ref"), "7-7-7.8-5-5")
        self.assertEqual(selected.get("selection_source"), "all_refs_fallback")
        self.assertTrue(selected.get("warnings"))

    def test_external_bundle_shape_normalizes_to_bindings(self):
        bundle_payload = {
            "schema": "mycite.external.isolate_bundle.v1",
            "source_msn_id": "6-6-6",
            "resource_id": "foreign_txa",
            "isolates": [
                {"canonical_ref": "6-6-6.8-5-8"},
                {"canonical_ref": "6-6-6.8-4-9"},
            ],
        }
        adapted = adapt_published_txa_resource_value(payload=bundle_payload, context_source="unit.external")
        bindings = adapted.get("field_ref_bindings") if isinstance(adapted.get("field_ref_bindings"), dict) else {}
        self.assertIn("6-6-6.8-5-8", list(bindings.get("product_profile_refs") or []))
        self.assertIn("6-6-6.8-4-9", list(bindings.get("invoice_log_refs") or []))


if __name__ == "__main__":
    unittest.main()
