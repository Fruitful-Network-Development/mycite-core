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
    path = (
        Path(__file__).resolve().parents[1]
        / "portals"
        / "_shared"
        / "runtime"
        / "flavors"
        / "tff"
        / "portal"
        / "tools"
        / "agro_erp"
        / "__init__.py"
    )
    portals_root = path.parents[6]
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    spec = importlib.util.spec_from_file_location("agro_erp_plan_test_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(HAS_FLASK, "flask is not installed in host python")
class AgroPlanWorkspaceFlowTests(unittest.TestCase):
    def setUp(self):
        self.module = _load_agro_module()
        self.app = Flask(
            __name__,
            template_folder=str(
                Path(__file__).resolve().parents[1]
                / "portals"
                / "_shared"
                / "runtime"
                / "flavors"
                / "tff"
                / "portal"
                / "ui"
                / "templates"
            ),
        )
        self.app.register_blueprint(self.module.agro_erp_bp)
        self.tmp = TemporaryDirectory()
        tmp_path = Path(self.tmp.name)
        private_dir = tmp_path / "private"
        public_dir = tmp_path / "public"
        data_dir = tmp_path / "data"
        private_dir.mkdir(parents=True, exist_ok=True)
        public_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "sandbox" / "resources").mkdir(parents=True, exist_ok=True)
        anthology_payload = {
            "4-1-4": [["4-1-4", "3-1-4", "CF67E2F01893AD7E"], ["bbox-1"]],
            "4-1-5": [["4-1-5", "3-1-4", "CF69230E1894CAD8"], ["bbox-2"]],
            "4-1-6": [["4-1-6", "3-1-4", "CF69268F1894171F"], ["coordinate-1"]],
            "4-1-7": [["4-1-7", "3-1-4", "CF6927F21894C898"], ["coordinate-2"]],
            "4-1-8": [["4-1-8", "3-1-4", "CF68E8AF1894C710"], ["coordinate-3"]],
            "8-5-11": [["8-5-11", "0-0-1", "1"], ["product"]],
            "8-4-22": [["8-4-22", "0-0-1", "1"], ["invoice"]],
        }
        (data_dir / "anthology.json").write_text(json.dumps(anthology_payload, indent=2) + "\n", encoding="utf-8")
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
                    "compile_metadata": {"compiled": False, "warnings": []},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.app.config["MYCITE_MSN_ID"] = "3-2-3-17-77-2-6-3-1-6"
        self.app.config["MYCITE_PORTAL_INSTANCE_ID"] = "tff"
        self.app.config["MYCITE_ACTIVE_PRIVATE_CONFIG"] = {
            "property": [
                {
                    "title": "parcel-a",
                    "bbox": ["4-1-4", "4-1-5"],
                    "geometry": {"type": "Polygon", "coordinates": ["4-1-6", "4-1-7", "4-1-8", "4-1-6"]},
                }
            ]
        }
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

    def test_plan_workspace_hydrates_grid_preview_and_draft_roundtrip(self):
        model = self.client.get("/portal/tools/agro_erp/model.json")
        self.assertEqual(model.status_code, 200)
        model_payload = model.get_json() or {}
        parcels = (((model_payload.get("parcel_workspace") or {}).get("parcels")) or [])
        self.assertTrue(parcels)
        parcel_id = str((parcels[0] or {}).get("parcel_id") or "")
        self.assertTrue(parcel_id)

        preview = self.client.post(
            "/portal/tools/agro_erp/plan/grid_preview",
            json={"parcel_id": parcel_id, "grid_spec": {"rows": 2, "columns": 3, "spacing": 0, "inset": 0}},
        )
        self.assertEqual(preview.status_code, 200)
        preview_payload = preview.get_json() or {}
        self.assertTrue(preview_payload.get("ok"))
        overlay = preview_payload.get("overlay") if isinstance(preview_payload.get("overlay"), dict) else {}
        self.assertEqual(overlay.get("plot_count"), 6)

        anthology_before = json.loads((Path(self.module.os.environ["DATA_DIR"]) / "anthology.json").read_text(encoding="utf-8"))
        saved = self.client.post(
            "/portal/tools/agro_erp/plan/draft/save",
            json={
                "resource_id": "plot_plan.parcel-a",
                "parcel_id": parcel_id,
                "grid_spec": {"rows": 2, "columns": 2, "spacing": 0, "inset": 0},
            },
        )
        self.assertEqual(saved.status_code, 200)
        saved_payload = saved.get_json() or {}
        self.assertTrue(saved_payload.get("ok"))
        self.assertEqual(saved_payload.get("resource_id"), "plot_plan.parcel-a")

        loaded = self.client.get("/portal/tools/agro_erp/plan/draft/load?resource_id=plot_plan.parcel-a")
        self.assertEqual(loaded.status_code, 200)
        loaded_payload = loaded.get_json() or {}
        self.assertTrue(loaded_payload.get("ok"))
        draft = loaded_payload.get("draft") if isinstance(loaded_payload.get("draft"), dict) else {}
        self.assertEqual(draft.get("resource_kind"), "plot_plan")
        self.assertEqual(draft.get("selected_parcel_id"), parcel_id)
        self.assertEqual((((draft.get("plot_overlay") or {}).get("plot_count"))), 4)

        saved_again = self.client.post(
            "/portal/tools/agro_erp/plan/draft/save",
            json={
                "resource_id": "plot_plan.parcel-a",
                "parcel_id": parcel_id,
                "grid_spec": {"rows": 1, "columns": 2, "spacing": 0, "inset": 0},
            },
        )
        self.assertEqual(saved_again.status_code, 200)
        loaded_again = self.client.get("/portal/tools/agro_erp/plan/draft/load?resource_id=plot_plan.parcel-a")
        self.assertEqual(loaded_again.status_code, 200)
        updated = (loaded_again.get_json() or {}).get("draft") or {}
        self.assertEqual((((updated.get("plot_overlay") or {}).get("plot_count"))), 2)

        anthology_after = json.loads((Path(self.module.os.environ["DATA_DIR"]) / "anthology.json").read_text(encoding="utf-8"))
        self.assertEqual(anthology_before, anthology_after)

    def test_inventory_products_mvp_routes_still_work(self):
        selected = self.client.post(
            "/portal/tools/agro_erp/mvp/resource/select_or_load",
            json={"resource_ref": "sandbox:txa.mvp.local"},
        )
        self.assertEqual(selected.status_code, 200)
        self.assertTrue((selected.get_json() or {}).get("ok"))
        product_preview = self.client.post(
            "/portal/tools/agro_erp/mvp/product/preview",
            json={"resource_ref": "sandbox:txa.mvp.local"},
        )
        self.assertEqual(product_preview.status_code, 200)
        invoice_preview = self.client.post(
            "/portal/tools/agro_erp/mvp/invoice/preview",
            json={"resource_ref": "sandbox:txa.mvp.local"},
        )
        self.assertEqual(invoice_preview.status_code, 200)


if __name__ == "__main__":
    unittest.main()
