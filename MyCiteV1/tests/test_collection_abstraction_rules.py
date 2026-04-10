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


def _load_rules():
    portals_root = Path(__file__).resolve().parents[1] / "instances"
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return importlib.import_module("_shared.portal.data_engine.rules")


def _load_register_data_routes():
    path = Path(__file__).resolve().parents[1] / "instances" / "_shared" / "portal" / "api" / "data_workspace.py"
    portals_root = path.parents[4]
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    spec = importlib.util.spec_from_file_location("data_workspace_collection_rules", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.register_data_routes


def _base_chain_rows() -> dict[str, object]:
    """Two baciloid families under same bacillete (N=2): lengths 2 and 3."""
    return {
        "1-1-1": {"identifier": "1-1-1", "reference": "0-0-6", "magnitude": "2", "label": "bacillete-2"},
        "2-1-1": {"identifier": "2-1-1", "reference": "1-1-1", "magnitude": "2", "label": "baciloid-64-chain"},
        "2-1-2": {"identifier": "2-1-2", "reference": "1-1-1", "magnitude": "3", "label": "baciloid-32-chain"},
        "3-1-1": {"identifier": "3-1-1", "reference": "2-1-1", "magnitude": "0", "label": "babellette-a"},
        "3-1-2": {"identifier": "3-1-2", "reference": "2-1-2", "magnitude": "0", "label": "babellette-b"},
        "4-1-1": {"identifier": "4-1-1", "reference": "3-1-1", "magnitude": "10", "label": "iso-a"},
        "4-1-2": {"identifier": "4-1-2", "reference": "3-1-1", "magnitude": "11", "label": "iso-b"},
        "4-2-1": {"identifier": "4-2-1", "reference": "3-1-2", "magnitude": "101", "label": "iso-other-baciloid"},
    }


def _payload_with_collection_stack(*, mixed_collection: bool = False, bad_member: bool = False) -> dict[str, object]:
    rows = dict(_base_chain_rows())
    if bad_member:
        rows["5-0-1"] = {
            "identifier": "5-0-1",
            "label": "coll-bad",
            "pairs": [{"reference": "2-1-1", "magnitude": ""}],
        }
    elif mixed_collection:
        rows["5-0-1"] = {
            "identifier": "5-0-1",
            "label": "coll-mixed",
            "pairs": [{"reference": "4-1-1", "magnitude": ""}, {"reference": "4-2-1", "magnitude": ""}],
        }
    else:
        rows["5-0-1"] = {
            "identifier": "5-0-1",
            "label": "coll-good",
            "pairs": [{"reference": "4-1-2", "magnitude": ""}, {"reference": "4-1-1", "magnitude": ""}],
        }
    rows["6-1-1"] = {"identifier": "6-1-1", "reference": "5-0-1", "magnitude": "1", "label": "selectorate"}
    rows["7-1-1"] = {"identifier": "7-1-1", "reference": "6-1-1", "magnitude": "0", "label": "field-a"}
    rows["7-1-2"] = {"identifier": "7-1-2", "reference": "6-1-1", "magnitude": "0", "label": "field-b"}
    rows["8-2-1"] = {
        "identifier": "8-2-1",
        "label": "table-row",
        "pairs": [
            {"reference": "7-1-1", "magnitude": "2"},
            {"reference": "7-1-2", "magnitude": "1"},
        ],
    }
    return {"rows": rows}


class CollectionAbstractionRuleTests(unittest.TestCase):
    def test_ordinal_semantics_documented_one_based(self):
        rules = _load_rules()
        self.assertEqual(rules.ORDINAL_SEMANTICS_V1.get("ordinal_basis"), "one_based_inclusive")

    def test_valid_collection_and_order(self):
        rules = _load_rules()
        p = _payload_with_collection_stack()
        report = rules.understand_datums(p)
        coll = report.by_id["5-0-1"]
        self.assertEqual(coll.family, "collection")
        self.assertEqual(coll.status, "standard")
        self.assertEqual(coll.constraints.get("ordered_member_refs"), ["4-1-2", "4-1-1"])
        self.assertEqual(coll.constraints.get("ordinal_domain_min"), 1)
        self.assertEqual(coll.constraints.get("ordinal_domain_max"), 2)

    def test_mixed_baciloid_collection_rejected(self):
        rules = _load_rules()
        report = rules.understand_datums(_payload_with_collection_stack(mixed_collection=True))
        self.assertEqual(report.by_id["5-0-1"].status, "invalid")

    def test_non_isolate_member_rejected(self):
        rules = _load_rules()
        report = rules.understand_datums(_payload_with_collection_stack(bad_member=True))
        self.assertEqual(report.by_id["5-0-1"].status, "invalid")

    def test_selectorate_field_table_recognition(self):
        rules = _load_rules()
        report = rules.understand_datums(_payload_with_collection_stack())
        self.assertEqual(report.by_id["6-1-1"].family, "selectorate")
        self.assertEqual(report.by_id["7-1-1"].family, "field")
        self.assertEqual(report.by_id["8-2-1"].family, "table_like")
        self.assertEqual(report.by_id["8-2-1"].status, "standard")

    def test_table_like_rejects_non_field_ref(self):
        rules = _load_rules()
        p = _payload_with_collection_stack()
        rows = dict(p["rows"])  # type: ignore[arg-type]
        rows["8-2-1"] = {
            "identifier": "8-2-1",
            "label": "bad-table",
            "pairs": [{"reference": "4-1-1", "magnitude": "1"}],
        }
        report = rules.understand_datums({"rows": rows})
        self.assertEqual(report.by_id["8-2-1"].status, "invalid")

    def test_ordinal_out_of_range_invalid(self):
        rules = _load_rules()
        p = _payload_with_collection_stack()
        rows = dict(p["rows"])  # type: ignore[arg-type]
        rows["8-2-1"] = {
            "identifier": "8-2-1",
            "label": "table-bad-ord",
            "pairs": [
                {"reference": "7-1-1", "magnitude": "3"},
            ],
        }
        report = rules.understand_datums({"rows": rows})
        self.assertEqual(report.by_id["8-2-1"].status, "invalid")

    def test_collection_shrink_invalidates_table_like(self):
        rules = _load_rules()
        full = _payload_with_collection_stack()
        report_full = rules.understand_datums(full)
        self.assertEqual(report_full.by_id["8-2-1"].status, "standard")
        rows = dict(full["rows"])  # type: ignore[arg-type]
        rows["5-0-1"] = {
            "identifier": "5-0-1",
            "label": "coll-one",
            "pairs": [{"reference": "4-1-1", "magnitude": ""}],
        }
        report_small = rules.understand_datums({"rows": rows})
        self.assertEqual(report_small.by_id["8-2-1"].status, "invalid")

    def test_reference_filter_collection_with_anchor(self):
        rules = _load_rules()
        p = _payload_with_collection_stack()
        out_all = rules.reference_filter_options(p, rule_key="collection.namespace_order.v1")
        ids_all = [x["datum_id"] for x in out_all["references"]]
        self.assertIn("4-1-1", ids_all)
        self.assertIn("4-1-2", ids_all)
        out_f = rules.reference_filter_options(
            p,
            rule_key="collection.namespace_order.v1",
            filter_context={"selected_refs": ["4-1-1"]},
        )
        ids_f = [x["datum_id"] for x in out_f["references"]]
        self.assertIn("4-1-2", ids_f)
        self.assertNotIn("4-2-1", ids_f)

    def test_lens_collection_field_table(self):
        rules = _load_rules()
        p = _payload_with_collection_stack()
        c_lens = rules.resolve_lens_for_datum(p, datum_id="5-0-1")
        self.assertTrue(c_lens.get("ok"))
        self.assertEqual((c_lens.get("lens") or {}).get("render_mode"), "ordered_member_list")
        t_lens = rules.resolve_lens_for_datum(p, datum_id="8-2-1")
        self.assertEqual((t_lens.get("lens") or {}).get("render_mode"), "row_tuple")

    def test_validate_create_collection_pairs(self):
        rules = _load_rules()
        p = _payload_with_collection_stack()
        out = rules.validate_rule_create(
            p,
            rule_key="collection.namespace_order.v1",
            reference="",
            magnitude="",
            value_group=0,
            pairs=[{"reference": "4-1-1", "magnitude": ""}, {"reference": "4-1-2", "magnitude": ""}],
        )
        self.assertTrue(out.get("ok"))


class _WorkspaceStub:
    def __init__(self, *, data_dir: str, rows: dict[str, object]):
        self.storage = type("StorageStub", (), {"data_dir": data_dir})()
        self._rows = rows

    def list_tables(self):
        return []

    def get_state_snapshot(self):
        return {}


@unittest.skipUnless(HAS_FLASK, "flask is not installed in host python")
class CollectionRulesRouteTests(unittest.TestCase):
    def setUp(self):
        register_data_routes = _load_register_data_routes()
        self._rows = _payload_with_collection_stack()["rows"]
        self._tmpdir = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        register_data_routes(
            self.app,
            workspace=_WorkspaceStub(data_dir=self._tmpdir.name, rows=self._rows),
            anthology_payload_provider=lambda: {"rows": self._rows},
            active_config_provider=lambda: {},
            active_config_saver=lambda payload: True,
            msn_id_provider=lambda: "9-9-9",
            include_home_redirect=False,
            include_legacy_shims=False,
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_anthology_understanding_and_resource_scope(self):
        r = self.client.get("/portal/api/data/rules/understanding/anthology")
        self.assertEqual(r.status_code, 200)
        by_id = (r.get_json() or {}).get("by_id") or {}
        self.assertEqual((by_id.get("5-0-1") or {}).get("family"), "collection")
        save = self.client.post(
            "/portal/api/data/sandbox/resources/coll-res/save",
            json={
                "payload": {
                    "resource_id": "coll-res",
                    "canonical_state": {"compact_payload": self._rows},
                }
            },
        )
        self.assertEqual(save.status_code, 200)
        r2 = self.client.get("/portal/api/data/rules/understanding/resource/coll-res")
        self.assertEqual(r2.status_code, 200)
        by2 = (r2.get_json() or {}).get("by_id") or {}
        self.assertEqual((by2.get("8-2-1") or {}).get("family"), "table_like")

    def test_reference_filter_post_body(self):
        resp = self.client.post(
            "/portal/api/data/rules/reference_filter",
            json={
                "rule_key": "field.selector_field.v1",
                "scope": "anthology",
                "filter_context": {},
            },
        )
        self.assertEqual(resp.status_code, 200)
        refs = [x["datum_id"] for x in (resp.get_json() or {}).get("references") or []]
        self.assertIn("7-1-1", refs)


if __name__ == "__main__":
    unittest.main()
