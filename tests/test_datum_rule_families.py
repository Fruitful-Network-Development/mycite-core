from __future__ import annotations

import importlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

try:
    from flask import Flask

    HAS_FLASK = True
except ModuleNotFoundError:  # pragma: no cover
    HAS_FLASK = False
    Flask = None  # type: ignore[assignment]


def _load_rules_module():
    portals_root = Path(__file__).resolve().parents[1] / "portals"
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return importlib.import_module("_shared.portal.data_engine.rules")


def _load_register_data_routes():
    path = Path(__file__).resolve().parents[1] / "portals" / "_shared" / "portal" / "api" / "data_workspace.py"
    portals_root = path.parents[4]
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    spec = importlib.util.spec_from_file_location("data_workspace_datum_rules_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.register_data_routes


def _rows_payload() -> dict[str, object]:
    return {
        "rows": {
            "1-1-1": {"identifier": "1-1-1", "reference": "0-0-6", "magnitude": "256", "label": "ascii namespace"},
            "2-1-1": {"identifier": "2-1-1", "reference": "1-1-1", "magnitude": "2", "label": "sequence-space"},
            "3-1-1": {"identifier": "3-1-1", "reference": "2-1-1", "magnitude": "0", "label": "transition"},
            "4-1-1": {"identifier": "4-1-1", "reference": "3-1-1", "magnitude": "01000001", "label": "value"},
            "3-1-2": {"identifier": "3-1-2", "reference": "2-1-1", "magnitude": "1", "label": "broken-transition"},
            "4-1-2": {"identifier": "4-1-2", "reference": "3-1-2", "magnitude": "01000010", "label": "descendant"},
        }
    }


class DatumRuleFamilyTests(unittest.TestCase):
    def test_family_recognition_and_statuses(self):
        rules = _load_rules_module()
        report = rules.understand_datums(_rows_payload())
        self.assertTrue(report.by_id["1-1-1"].family == "bacillete")
        self.assertTrue(report.by_id["2-1-1"].family == "baciloid")
        self.assertEqual(report.by_id["3-1-1"].status, "transitional")
        self.assertEqual(report.by_id["4-1-1"].status, "standard")
        self.assertEqual(report.by_id["3-1-2"].status, "invalid")
        self.assertEqual(report.by_id["4-1-2"].status, "ambiguous")

    def test_invalid_parent_family_rejection(self):
        rules = _load_rules_module()
        out = rules.validate_rule_create(
            _rows_payload(),
            rule_key="baciloid.sequence_space.v1",
            reference="3-1-1",
            magnitude="3",
            value_group=1,
            label="invalid-parent",
        )
        self.assertFalse(out.get("ok"))
        self.assertTrue(any("does not match selected rule" in str(item).lower() for item in [out.get("errors", [""])[0]]))

    def test_invalid_magnitude_rejection(self):
        rules = _load_rules_module()
        out = rules.validate_rule_create(
            _rows_payload(),
            rule_key="babellette.transition.v1",
            reference="2-1-1",
            magnitude="1",
            value_group=1,
        )
        self.assertFalse(out.get("ok"))
        self.assertTrue(any("exactly 0" in str(item) for item in list(out.get("errors") or [])))

    def test_isolate_domain_validation_math(self):
        rules = _load_rules_module()
        tiny = {
            "rows": {
                "1-1-1": {"identifier": "1-1-1", "reference": "0-0-6", "magnitude": "2"},
                "2-1-1": {"identifier": "2-1-1", "reference": "1-1-1", "magnitude": "3"},
                "3-1-1": {"identifier": "3-1-1", "reference": "2-1-1", "magnitude": "0"},
            }
        }
        invalid = rules.validate_rule_create(
            tiny,
            rule_key="isolate.binary_value.v1",
            reference="3-1-1",
            magnitude="1000",
            value_group=1,
        )
        self.assertFalse(invalid.get("ok"))
        self.assertTrue(any("out of domain" in str(item) for item in list(invalid.get("errors") or [])))
        valid = rules.validate_rule_create(
            tiny,
            rule_key="isolate.binary_value.v1",
            reference="3-1-1",
            magnitude="111",
            value_group=1,
        )
        self.assertTrue(valid.get("ok"))
        constraints = valid.get("constraints") if isinstance(valid.get("constraints"), dict) else {}
        self.assertEqual(constraints.get("max_value"), 7)
        self.assertEqual(constraints.get("bit_width"), 3)

    def test_reference_filtering_by_parent_family(self):
        rules = _load_rules_module()
        out = rules.reference_filter_options(_rows_payload(), rule_key="baciloid.sequence_space.v1")
        self.assertTrue(out.get("ok"))
        refs = [str(item.get("datum_id")) for item in list(out.get("references") or [])]
        self.assertEqual(refs, ["1-1-1"])
        out_isolate = rules.reference_filter_options(_rows_payload(), rule_key="isolate.binary_value.v1")
        refs_isolate = [str(item.get("datum_id")) for item in list(out_isolate.get("references") or [])]
        self.assertIn("3-1-1", refs_isolate)
        self.assertNotIn("3-1-2", refs_isolate)

    def test_lens_resolution_for_ascii_like_isolate(self):
        rules = _load_rules_module()
        out = rules.resolve_lens_for_datum(_rows_payload(), datum_id="4-1-1")
        self.assertTrue(out.get("ok"))
        lens = out.get("lens") if isinstance(out.get("lens"), dict) else {}
        self.assertEqual(lens.get("lens_key"), "lens.text.ascii_like.v1")
        self.assertTrue(lens.get("renderable"))
        self.assertEqual(lens.get("decoded_text"), "A")


class _WorkspaceStub:
    def __init__(self, *, data_dir: str) -> None:
        self.storage = type("StorageStub", (), {"data_dir": data_dir})()

    def list_tables(self):
        return []

    def get_state_snapshot(self):
        return {}


@unittest.skipUnless(HAS_FLASK, "flask is not installed in host python")
class DatumRulesRouteTests(unittest.TestCase):
    def setUp(self):
        register_data_routes = _load_register_data_routes()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        register_data_routes(
            self.app,
            workspace=_WorkspaceStub(data_dir=self._tmpdir.name),
            anthology_payload_provider=lambda: _rows_payload(),
            active_config_provider=lambda: {},
            active_config_saver=lambda payload: True,
            msn_id_provider=lambda: "9-9-9",
            include_home_redirect=False,
            include_legacy_shims=False,
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_rules_endpoints_anthology_and_resource_scope(self):
        anthology = self.client.get("/portal/api/data/rules/understanding/anthology")
        self.assertEqual(anthology.status_code, 200)
        payload = anthology.get_json() or {}
        by_id = payload.get("by_id") if isinstance(payload.get("by_id"), dict) else {}
        self.assertEqual(((by_id.get("3-1-1") or {}).get("status")), "transitional")
        self.assertEqual(((by_id.get("4-1-1") or {}).get("status")), "standard")

        filter_resp = self.client.post(
            "/portal/api/data/rules/reference_filter",
            json={"scope": "anthology", "rule_key": "babellette.transition.v1"},
        )
        self.assertEqual(filter_resp.status_code, 200)
        refs = [str(item.get("datum_id")) for item in ((filter_resp.get_json() or {}).get("references") or [])]
        self.assertIn("2-1-1", refs)

        validate_resp = self.client.post(
            "/portal/api/data/rules/validate_create",
            json={
                "scope": "anthology",
                "rule_key": "isolate.binary_value.v1",
                "reference": "3-1-1",
                "magnitude": "01000001",
                "value_group": 1,
            },
        )
        self.assertEqual(validate_resp.status_code, 200)

        save_resource = self.client.post(
            "/portal/api/data/sandbox/resources/rule-resource/save",
            json={
                "payload": {
                    "resource_id": "rule-resource",
                    "canonical_state": {"compact_payload": _rows_payload()["rows"]},
                }
            },
        )
        self.assertEqual(save_resource.status_code, 200)
        resource_understanding = self.client.get("/portal/api/data/rules/understanding/resource/rule-resource")
        self.assertEqual(resource_understanding.status_code, 200)
        resource_by_id = (resource_understanding.get_json() or {}).get("by_id") or {}
        self.assertEqual(((resource_by_id.get("1-1-1") or {}).get("family")), "bacillete")


if __name__ == "__main__":
    unittest.main()
