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
        pol = out.get("rule_policy") if isinstance(out.get("rule_policy"), dict) else {}
        self.assertEqual(pol.get("status"), "standard")
        self.assertTrue(pol.get("can_use_default_lens"))

    def test_derive_rule_policy_matrix(self):
        rules = _load_rules_module()
        report = rules.understand_datums(_rows_payload())
        std = rules.derive_rule_policy(report.by_id["4-1-1"])
        self.assertTrue(std.write_allowed and std.can_publish)
        amb = rules.derive_rule_policy(report.by_id["4-1-2"])
        self.assertFalse(amb.write_allowed)
        self.assertTrue(amb.requires_manual_override)
        inv = rules.derive_rule_policy(report.by_id["3-1-2"])
        self.assertFalse(inv.write_allowed)
        tr = rules.derive_rule_policy(report.by_id["3-1-1"])
        self.assertEqual(tr.edit_mode, "limited")
        self.assertFalse(tr.can_publish)

    def test_evaluate_probe_write_without_rule_key_hint(self):
        rules = _load_rules_module()
        base = {
            "rows": {
                "1-1-1": {"identifier": "1-1-1", "reference": "0-0-6", "magnitude": "2"},
                "2-1-1": {"identifier": "2-1-1", "reference": "1-1-1", "magnitude": "3"},
                "3-1-1": {"identifier": "3-1-1", "reference": "2-1-1", "magnitude": "0"},
            }
        }
        probe_id = rules.compute_next_append_datum_id(base, 9, 1)
        row = rules.build_append_row_dict(
            datum_id=probe_id,
            label="probe",
            pairs=[{"reference": "3-1-1", "magnitude": "111"}],
            reference="3-1-1",
            magnitude="111",
        )
        ev = rules.evaluate_probe_write(
            base,
            probe_row_id=probe_id,
            probe_row_dict=row,
            rule_key_hint="",
            rule_write_override=False,
            pairs_for_hint=[{"reference": "3-1-1", "magnitude": "111"}],
            value_group_hint=1,
        )
        self.assertTrue(ev.get("ok"))
        self.assertEqual((ev.get("datum_understanding") or {}).get("family"), "isolate")

    def test_rule_key_hint_can_still_fail_stricter_than_engine(self):
        rules = _load_rules_module()
        base = _rows_payload()
        probe_id = rules.compute_next_append_datum_id(base, 9, 1)
        row = rules.build_append_row_dict(
            datum_id=probe_id,
            label="probe",
            pairs=[{"reference": "3-1-1", "magnitude": "01000011"}],
            reference="3-1-1",
            magnitude="01000011",
        )
        ev = rules.evaluate_probe_write(
            base,
            probe_row_id=probe_id,
            probe_row_dict=row,
            rule_key_hint="baciloid.sequence_space.v1",
            rule_write_override=False,
            pairs_for_hint=[{"reference": "3-1-1", "magnitude": "01000011"}],
            value_group_hint=1,
        )
        self.assertFalse(ev.get("ok"))


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
        pol = payload.get("rule_policy_by_id") if isinstance(payload.get("rule_policy_by_id"), dict) else {}
        self.assertEqual(((pol.get("4-1-1") or {}).get("ref_mode")), "filtered_default")

        filter_resp = self.client.post(
            "/portal/api/data/rules/reference_filter",
            json={"scope": "anthology", "rule_key": "babellette.transition.v1"},
        )
        self.assertEqual(filter_resp.status_code, 200)
        refs = [str(item.get("datum_id")) for item in ((filter_resp.get_json() or {}).get("references") or [])]
        self.assertIn("2-1-1", refs)

        inferred = self.client.post(
            "/portal/api/data/rules/reference_filter",
            json={"scope": "anthology", "value_group": 0},
        )
        self.assertEqual(inferred.status_code, 200)
        inferred_payload = inferred.get_json() or {}
        self.assertEqual(inferred_payload.get("resolved_rule_key"), "collection.namespace_order.v1")

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

        validate_no_key = self.client.post(
            "/portal/api/data/rules/validate_create",
            json={
                "scope": "anthology",
                "layer": 9,
                "reference": "3-1-1",
                "magnitude": "01000001",
                "value_group": 1,
                "label": "no-rule-key",
            },
        )
        self.assertEqual(validate_no_key.status_code, 200)
        vj = validate_no_key.get_json() or {}
        self.assertTrue(vj.get("ok"))
        self.assertEqual((vj.get("datum_understanding") or {}).get("family"), "isolate")

        lens = self.client.post(
            "/portal/api/data/rules/lens",
            json={"scope": "anthology", "datum_id": "4-1-1"},
        )
        self.assertEqual(lens.status_code, 200)
        self.assertIn("rule_policy", lens.get_json() or {})

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

        bad_save = self.client.post(
            "/portal/api/data/sandbox/resources/bad-rule-resource/save",
            json={"payload": {"resource_id": "bad", "anthology_compatible_payload": {"rows": _rows_payload()["rows"]}}},
        )
        self.assertEqual(bad_save.status_code, 400)
        ok_save = self.client.post(
            "/portal/api/data/sandbox/resources/bad-rule-resource/save",
            json={
                "rule_write_override": True,
                "rule_write_override_reason": "test suite",
                "payload": {"resource_id": "bad", "anthology_compatible_payload": {"rows": _rows_payload()["rows"]}},
            },
        )
        self.assertEqual(ok_save.status_code, 200)


if __name__ == "__main__":
    unittest.main()
