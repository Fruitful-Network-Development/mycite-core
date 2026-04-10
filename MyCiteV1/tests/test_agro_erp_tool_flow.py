from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

try:
    from flask import Flask

    HAS_FLASK = True
except ModuleNotFoundError:  # pragma: no cover
    HAS_FLASK = False
    Flask = None  # type: ignore[assignment]


def _load_agro_module():
    path = Path(__file__).resolve().parents[1] / "instances" / "_shared" / "runtime" / "flavors" / "tff" / "portal" / "tools" / "agro_erp" / "__init__.py"
    portals_root = path.parents[6]
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    spec = importlib.util.spec_from_file_location("agro_erp_test_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(HAS_FLASK, "flask is not installed in host python")
class AgroErpToolFlowTests(unittest.TestCase):
    def setUp(self):
        self.module = _load_agro_module()
        self.app = Flask(__name__, template_folder=str(Path(__file__).resolve().parents[1] / "instances" / "_shared" / "runtime" / "flavors" / "tff" / "portal" / "ui" / "templates"))
        self.app.register_blueprint(self.module.agro_erp_bp)
        self.tmp = TemporaryDirectory()
        tmp_path = Path(self.tmp.name)
        private_dir = tmp_path / "private"
        public_dir = tmp_path / "public"
        data_dir = tmp_path / "data"
        private_dir.mkdir(parents=True, exist_ok=True)
        public_dir.mkdir(parents=True, exist_ok=True)
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "anthology.json").write_text(json.dumps({}) + "\n", encoding="utf-8")
        (data_dir / "sandbox" / "resources").mkdir(parents=True, exist_ok=True)
        (data_dir / "sandbox" / "resources" / "txa.mvp.local.json").write_text(
            json.dumps(
                {
                    "schema": "mycite.sandbox.singular_mss_resource.v1",
                    "resource_id": "txa.mvp.local",
                    "resource_kind": "txa",
                    "origin_kind": "local",
                    "source_portal": "3-2-3-17-77-2-6-3-1-6",
                    "source_ref": "5-0-1",
                    "draft_state": {
                        "selected_ids": ["8-5-11", "8-4-22"],
                        "compact_payload": {
                            "8-5-11": [["8-5-11", "0-0-1", "1"], ["product"]],
                            "8-4-22": [["8-4-22", "0-0-1", "1"], ["invoice"]],
                        },
                    },
                    "canonical_state": {
                        "selected_ids": ["8-5-11", "8-4-22"],
                        "compact_payload": {
                            "8-5-11": [["8-5-11", "0-0-1", "1"], ["product"]],
                            "8-4-22": [["8-4-22", "0-0-1", "1"], ["invoice"]],
                        },
                    },
                    "mss_form": {"bitstring": "", "wire_variant": ""},
                    "abstraction_root": "8-5-11",
                    "compile_metadata": {"compiled": False, "warnings": []},
                    "updated_at": 0,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.app.config["MYCITE_MSN_ID"] = "3-2-3-17-77-2-6-3-1-6"
        self.app.config["MYCITE_PORTAL_INSTANCE_ID"] = "tff"
        active_cfg = {"property": {"title": "Test Farm", "geometry": {"type": "Polygon"}}}
        self.app.config["MYCITE_ACTIVE_PRIVATE_CONFIG"] = active_cfg
        # ``resolve_active_private_config_path`` only resolves existing files; seed disk so
        # ``_save_active_config_for_write`` can persist profile updates during MVP apply.
        msn_id = str(self.app.config["MYCITE_MSN_ID"] or "").strip()
        cfg_path = private_dir / f"mycite-config-{msn_id}.json"
        cfg_path.write_text(json.dumps(active_cfg, indent=2) + "\n", encoding="utf-8")
        self.app.config["MYCITE_DATA_WORKSPACE"] = type("WorkspaceStub", (), {"append_anthology_datum": lambda *args, **kwargs: {"ok": True}})()
        self.old_private = self.module.os.environ.get("PRIVATE_DIR")
        self.old_public = self.module.os.environ.get("PUBLIC_DIR")
        self.old_data = self.module.os.environ.get("DATA_DIR")
        self.module.os.environ["PRIVATE_DIR"] = str(private_dir)
        self.module.os.environ["PUBLIC_DIR"] = str(public_dir)
        self.module.os.environ["DATA_DIR"] = str(data_dir)
        self.client = self.app.test_client()

    def tearDown(self):
        if self.old_private is None:
            self.module.os.environ.pop("PRIVATE_DIR", None)
        else:
            self.module.os.environ["PRIVATE_DIR"] = self.old_private
        if self.old_public is None:
            self.module.os.environ.pop("PUBLIC_DIR", None)
        else:
            self.module.os.environ["PUBLIC_DIR"] = self.old_public
        if self.old_data is None:
            self.module.os.environ.pop("DATA_DIR", None)
        else:
            self.module.os.environ["DATA_DIR"] = self.old_data
        self.tmp.cleanup()

    def test_capability_spec_loads_and_validates(self):
        response = self.client.get("/portal/tools/agro_erp/capabilities.json")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json() or {}
        self.assertTrue(payload.get("ok"))
        capabilities = payload.get("capabilities") if isinstance(payload.get("capabilities"), dict) else {}
        self.assertEqual(capabilities.get("schema"), "mycite.agro_erp.capabilities.v1")
        self.assertTrue(any(str(item.get("template_id")) == "livestock.product_type" for item in capabilities.get("templates") or []))

    def test_resource_selection_flow_delegates_to_canonical_data_api(self):
        calls = []

        def _stub(method, path, payload=None):
            calls.append((method, path, payload))
            return 200, {"ok": True, "resources": [{"resource_id": "farm_metrics"}]}

        self.module._call_data_api = _stub
        response = self.client.get("/portal/tools/agro_erp/resources?source_msn_id=9-9-9-9")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any("/portal/api/data/external/resources" in item[1] for item in calls))

    def test_planner_preview_generation_uses_shared_core(self):
        def _stub(method, path, payload=None):
            if path == "/portal/api/data/write/preview":
                return 200, {
                    "ok": True,
                    "plan": {"ordered_writes": [{"action": "create_target", "canonical_ref": "20-1-9"}]},
                }
            return 404, {"ok": False}

        self.module._call_data_api = _stub
        response = self.client.post(
            "/portal/tools/agro_erp/plan_preview",
            json={
                "template_id": "livestock.product_type",
                "source_msn_id": "9-9-9-9",
                "resource_id": "farm_metrics",
                "fields": {"local_id": "20-1-9", "taxonomy_ref": "9-9-9-9.5-0-1", "title": "Heifer"},
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json() or {}
        self.assertTrue(payload.get("ok"))
        self.assertTrue(isinstance(payload.get("plan"), dict))

    def test_time_schema_uses_sandbox_anchor_not_utility_collection(self):
        data_dir = Path(self.module.os.environ["DATA_DIR"])
        sandbox_root = data_dir / "sandbox" / "agro-erp"
        sandbox_root.mkdir(parents=True, exist_ok=True)
        anchor_path = sandbox_root / "tool.3-2-3-17-77-2-6-3-1-6.agro-erp.json"
        anchor_path.write_text(
            json.dumps(
                {
                    "1-1-1": [
                        ["1-1-1", "0-0-1", "00000010001110000100001110011000100001100111111011111010001111101000101101101111100111100"],
                        ["UTC_mixed_radix"],
                    ]
                }
            )
            + "\n",
            encoding="utf-8",
        )
        utility_root = Path(self.module.os.environ["PRIVATE_DIR"]) / "utilities" / "tools" / "agro-erp"
        utility_root.mkdir(parents=True, exist_ok=True)
        (utility_root / anchor_path.name).write_text(
            json.dumps({"1-1-1": [["1-1-1", "0-0-1", "0"], ["wrong"]]}) + "\n",
            encoding="utf-8",
        )
        response = self.client.post("/portal/tools/agro_erp/time/filter", json={"selected_scope": "13-787-26-3-26"})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json() or {}
        authority = payload.get("schema_authority") if isinstance(payload.get("schema_authority"), dict) else {}
        self.assertIn("/data/sandbox/agro-erp/", str(authority.get("anchor_path") or ""))

    def test_apply_flow_for_product_type_and_gestation_uses_shared_write_pipeline(self):
        calls = []

        def _stub(method, path, payload=None):
            calls.append((method, path, payload))
            if path == "/portal/api/data/write/preview":
                return 200, {
                    "ok": True,
                    "intent": ((payload or {}).get("intent") or {}),
                    "plan": {"ordered_writes": [{"action": "create_target", "canonical_ref": "20-1-9"}]},
                }
            if path == "/portal/api/data/write/apply":
                return 200, {"ok": True, "created_datum_refs": ["20-1-9"], "mutation_summary": {"mutation_count": 1}}
            return 404, {"ok": False}

        self.module._call_data_api = _stub
        body = {
            "template_id": "livestock.product_type",
            "source_msn_id": "9-9-9-9",
            "resource_id": "farm_metrics",
            "fields": {"local_id": "20-1-9", "taxonomy_ref": "9-9-9-9.5-0-1", "title": "Heifer"},
        }
        product_apply = self.client.post("/portal/tools/agro_erp/apply", json=body)
        self.assertEqual(product_apply.status_code, 200)
        gestation_apply = self.client.post(
            "/portal/tools/agro_erp/apply",
            json={
                "template_id": "livestock.gestation_period",
                "source_msn_id": "9-9-9-9",
                "resource_id": "farm_metrics",
                "fields": {
                    "local_id": "20-1-10",
                    "taxonomy_ref": "9-9-9-9.5-0-1",
                    "duration_days": "280",
                    "title": "Heifer Gestation",
                },
            },
        )
        self.assertEqual(gestation_apply.status_code, 200)
        self.assertTrue(any(item[1] == "/portal/api/data/write/preview" for item in calls))
        self.assertTrue(any(item[1] == "/portal/api/data/write/apply" for item in calls))

    def test_mvp_live_state_gate_passes_with_extracted_resources(self):
        response = self.client.get("/portal/tools/agro_erp/mvp/live_state_gate")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json() or {}
        self.assertTrue(payload.get("ok"))
        checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
        self.assertTrue(checks)
        self.assertTrue(all(str(item.get("status")) == "PASS" for item in checks if isinstance(item, dict)))

    def test_mvp_local_resource_product_invoice_preview_apply_and_readback(self):
        selected = self.client.post(
            "/portal/tools/agro_erp/mvp/resource/select_or_load",
            json={"resource_ref": "sandbox:txa.mvp.local"},
        )
        self.assertEqual(selected.status_code, 200)
        selected_payload = selected.get_json() or {}
        self.assertTrue(selected_payload.get("ok"))
        session_id = str(selected_payload.get("sandbox_session_id") or "").strip()
        self.assertTrue(session_id)
        self.assertEqual(str((selected_payload.get("session") or {}).get("session_id") or ""), session_id)

        product_preview = self.client.post(
            "/portal/tools/agro_erp/mvp/product/preview",
            json={"resource_ref": "sandbox:txa.mvp.local", "sandbox_session_id": session_id},
        )
        self.assertEqual(product_preview.status_code, 200)
        product_apply = self.client.post(
            "/portal/tools/agro_erp/mvp/product/apply",
            json={"resource_ref": "sandbox:txa.mvp.local", "sandbox_session_id": session_id},
        )
        self.assertEqual(product_apply.status_code, 200)
        product_apply_payload = product_apply.get_json() or {}
        self.assertEqual(((product_apply_payload.get("mutation_summary") or {}).get("created_count")), 0)
        self.assertEqual(((product_apply_payload.get("mutation_summary") or {}).get("reused_count")), 1)
        product_items = (((product_apply_payload.get("readback") or {}).get("items")) or [])
        self.assertTrue(product_items)
        self.assertTrue(any(str(item.get("canonical_ref")) == "3-2-3-17-77-2-6-3-1-6.8-5-11" for item in product_items))

        invoice_preview = self.client.post(
            "/portal/tools/agro_erp/mvp/invoice/preview",
            json={"resource_ref": "sandbox:txa.mvp.local", "sandbox_session_id": session_id},
        )
        self.assertEqual(invoice_preview.status_code, 200)
        invoice_apply = self.client.post(
            "/portal/tools/agro_erp/mvp/invoice/apply",
            json={"resource_ref": "sandbox:txa.mvp.local", "sandbox_session_id": session_id},
        )
        self.assertEqual(invoice_apply.status_code, 200)
        invoice_apply_payload = invoice_apply.get_json() or {}
        self.assertEqual(((invoice_apply_payload.get("mutation_summary") or {}).get("created_count")), 0)
        self.assertEqual(((invoice_apply_payload.get("mutation_summary") or {}).get("reused_count")), 1)
        invoice_items = (((invoice_apply_payload.get("readback") or {}).get("items")) or [])
        self.assertTrue(invoice_items)
        self.assertTrue(any(str(item.get("canonical_ref")) == "3-2-3-17-77-2-6-3-1-6.8-4-22" for item in invoice_items))
        anthology = json.loads((Path(self.module.os.environ["DATA_DIR"]) / "anthology.json").read_text(encoding="utf-8"))
        self.assertFalse(any(str(key).startswith("4-1-") for key in anthology.keys()))

        readback = self.client.get("/portal/tools/agro_erp/mvp/workflow/readback?resource_ref=sandbox:txa.mvp.local")
        self.assertEqual(readback.status_code, 200)
        readback_payload = readback.get_json() or {}
        self.assertTrue((readback_payload.get("product_types") or {}).get("items"))
        self.assertTrue((readback_payload.get("invoice_log") or {}).get("items"))

    def test_mvp_external_origin_parity_uses_same_adapter_path(self):
        external_msn = "7-7-7"
        public_dir = Path(self.module.os.environ["PUBLIC_DIR"])
        (public_dir / f"{external_msn}.json").write_text(
            json.dumps(
                {
                    "public_resources": [
                        {
                            "resource_id": "foreign_txa",
                            "kind": "sandbox_resource",
                            "export_family": "mycite.sandbox.resource.v1",
                            "href": "foreign_txa_resource.json",
                        }
                    ]
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (public_dir / "foreign_txa_resource.json").write_text(
            json.dumps(
                {
                    "rows": [
                        {"identifier": "8-5-11", "label": "product"},
                        {"identifier": "8-4-22", "label": "invoice"},
                    ]
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        selected = self.client.post(
            "/portal/tools/agro_erp/mvp/resource/select_or_load",
            json={"source_msn_id": external_msn, "resource_id": "foreign_txa"},
        )
        self.assertEqual(selected.status_code, 200)
        payload = selected.get_json() or {}
        self.assertTrue(payload.get("ok"))
        bindings = (((payload.get("adapted_context") or {}).get("field_ref_bindings")) or {})
        self.assertIn(f"{external_msn}.8-5-11", list(bindings.get("product_profile_refs") or []))
        self.assertIn(f"{external_msn}.8-4-22", list(bindings.get("invoice_log_refs") or []))
        product_apply = self.client.post(
            "/portal/tools/agro_erp/mvp/product/apply",
            json={"resource_ref": f"{external_msn}.foreign_txa"},
        )
        self.assertEqual(product_apply.status_code, 200)
        self.assertEqual((((product_apply.get_json() or {}).get("mutation_summary") or {}).get("created_count")), 0)
        invoice_apply = self.client.post(
            "/portal/tools/agro_erp/mvp/invoice/apply",
            json={"resource_ref": f"{external_msn}.foreign_txa"},
        )
        self.assertEqual(invoice_apply.status_code, 200)
        self.assertEqual((((invoice_apply.get_json() or {}).get("mutation_summary") or {}).get("created_count")), 0)


if __name__ == "__main__":
    unittest.main()
