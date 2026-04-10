from __future__ import annotations

import sys
import unittest
from pathlib import Path

portals_root = Path(__file__).resolve().parents[1] / "instances"
token = str(portals_root)
if token not in sys.path:
    sys.path.insert(0, token)

from _shared.portal.data_engine.write_pipeline import apply_write_preview, preview_write_intent
from _shared.portal.data_engine.property_workspace import primary_property_entry


class _WorkspaceStub:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.counter = 0

    def append_anthology_datum(self, *, layer, value_group, reference, magnitude, label, pairs=None):
        self.counter += 1
        identifier = f"{layer}-{value_group}-{self.counter}"
        self.calls.append(
            {
                "layer": layer,
                "value_group": value_group,
                "reference": reference,
                "magnitude": magnitude,
                "label": label,
                "pairs": pairs,
            }
        )
        return {"ok": True, "identifier": identifier, "contract_mss_sync": {"triggered": True, "reason": "unit"}}


class WritePipelineEngineTests(unittest.TestCase):
    def test_preview_normalizes_target_ref_and_validates_contract(self):
        preview = preview_write_intent(
            intent={
                "intent_type": "profile_field",
                "field_id": "portal_title",
                "template_id": "geometry.parcel",
                "local_msn_id": "1-2-3",
                "fields": {"local_id": "31-1-7", "title": "Parcel Seven"},
            },
            current_config={"display": {"title": "old"}},
            local_anthology_payload={"rows": []},
            external_plan_fn=lambda _: (True, {"ok": True, "ordered_writes": []}, ""),
        )
        self.assertTrue(preview.ok)
        self.assertEqual(preview.intent.get("target_ref"), "1-2-3.31-1-7")
        updates = preview.config_updates
        self.assertEqual(updates[0].get("path"), "display.title")
        self.assertEqual(updates[0].get("next"), "1-2-3.31-1-7")

    def test_preview_reuses_existing_target_when_found_locally(self):
        preview = preview_write_intent(
            intent={
                "intent_type": "geometry_datum",
                "template_id": "geometry.plot",
                "local_msn_id": "1-2-3",
                "fields": {"local_id": "31-1-22", "title": "Plot 22"},
            },
            current_config={},
            local_anthology_payload={"rows": {"31-1-22": []}},
            external_plan_fn=lambda _: (True, {"ok": True, "ordered_writes": []}, ""),
        )
        self.assertTrue(preview.ok)
        actions = [item.get("action") for item in preview.write_actions]
        self.assertIn("reuse_existing_target", actions)
        self.assertNotIn("create_target", actions)

    def test_apply_reuse_path_is_deterministic_without_mutation(self):
        workspace = _WorkspaceStub()
        preview = preview_write_intent(
            intent={
                "intent_type": "geometry_datum",
                "template_id": "geometry.parcel",
                "local_msn_id": "1-2-3",
                "fields": {"local_id": "31-1-20", "title": "Parcel 20"},
            },
            current_config={},
            local_anthology_payload={"rows": {"31-1-20": []}},
            external_plan_fn=lambda _: (True, {"ok": True, "ordered_writes": []}, ""),
        )
        result = apply_write_preview(
            preview=preview,
            workspace=workspace,
            load_config_fn=lambda: {},
            save_config_fn=lambda payload: True,
        )
        self.assertTrue(result.ok)
        self.assertEqual(len(workspace.calls), 0)
        self.assertEqual((result.mutation_summary or {}).get("created_count"), 0)
        self.assertEqual((result.mutation_summary or {}).get("reused_count"), 1)

    def test_apply_appends_multi_ref_config_update_uniquely(self):
        workspace = _WorkspaceStub()
        config_payload = {"property": {"bbox": ["1-2-3.30-1-1"]}}

        preview = preview_write_intent(
            intent={
                "intent_type": "profile_field",
                "field_id": "property_bbox",
                "template_id": "geometry.coordinate_point",
                "local_msn_id": "1-2-3",
                "fields": {"local_id": "30-1-2", "title": "Point Two"},
            },
            current_config=config_payload,
            local_anthology_payload={"rows": []},
            external_plan_fn=lambda _: (True, {"ok": True, "ordered_writes": []}, ""),
        )
        self.assertTrue(preview.ok)
        saved: dict[str, object] = {}

        def _save(payload):
            saved.update(payload)
            return True

        result = apply_write_preview(
            preview=preview,
            workspace=workspace,
            load_config_fn=lambda: config_payload,
            save_config_fn=_save,
        )
        self.assertTrue(result.ok)
        bbox = primary_property_entry(saved if isinstance(saved, dict) else {}).get("bbox") or []
        self.assertEqual(bbox, ["1-2-3.30-1-1", "1-2-3.30-1-2"])


if __name__ == "__main__":
    unittest.main()
