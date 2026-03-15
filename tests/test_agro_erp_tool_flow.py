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
    path = Path(__file__).resolve().parents[1] / "portals" / "_shared" / "runtime" / "flavors" / "tff" / "portal" / "tools" / "agro_erp" / "__init__.py"
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
        self.app = Flask(__name__, template_folder=str(Path(__file__).resolve().parents[1] / "portals" / "_shared" / "runtime" / "flavors" / "tff" / "portal" / "ui" / "templates"))
        self.app.register_blueprint(self.module.agro_erp_bp)
        self.tmp = TemporaryDirectory()
        tmp_path = Path(self.tmp.name)
        private_dir = tmp_path / "private"
        public_dir = tmp_path / "public"
        data_dir = tmp_path / "data"
        private_dir.mkdir(parents=True, exist_ok=True)
        public_dir.mkdir(parents=True, exist_ok=True)
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "anthology.json").write_text(json.dumps({"rows": []}) + "\n", encoding="utf-8")
        self.app.config["MYCITE_MSN_ID"] = "3-2-3-17-77-2-6-3-1-6"
        self.app.config["MYCITE_PORTAL_INSTANCE_ID"] = "tff"
        self.app.config["MYCITE_ACTIVE_PRIVATE_CONFIG"] = {"property": {"title": "Test Farm", "geometry": {"type": "Polygon"}}}
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


if __name__ == "__main__":
    unittest.main()
