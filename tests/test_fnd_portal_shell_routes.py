from __future__ import annotations

import importlib.util
import json
import os
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


def _load_fnd_app_module(temp_root: Path):
    portals_root = Path(__file__).resolve().parents[1] / "portals"
    runtime_root = portals_root / "runtime"
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)

    private_dir = temp_root / "private"
    public_dir = temp_root / "public"
    data_dir = temp_root / "data"
    private_dir.mkdir(parents=True, exist_ok=True)
    public_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    msn_id = "3-2-3-17-77-1-6-4-1-4"
    (private_dir / "config.json").write_text(json.dumps({"msn_id": msn_id}) + "\n", encoding="utf-8")
    (public_dir / f"msn-{msn_id}.json").write_text(json.dumps({"msn_id": msn_id, "title": "FND"}) + "\n", encoding="utf-8")
    (public_dir / f"fnd-{msn_id}.json").write_text(json.dumps({"schema": "mycite.fnd.profile.v1", "msn_id": msn_id, "title": "FND", "summary": "Brand"}) + "\n", encoding="utf-8")
    remote_msn = "9-9-9-9"
    (public_dir / f"msn-{remote_msn}.json").write_text(
        json.dumps(
            {
                "msn_id": remote_msn,
                "title": "Remote",
                "public_resources": [
                    {
                        "resource_id": "farm_metrics",
                        "kind": "datum_export",
                        "export_family": "mycite.public.resource.v1",
                        "href": f"{remote_msn}-farm_metrics.json",
                        "lens_hint": "datum",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (public_dir / f"{remote_msn}-farm_metrics.json").write_text(
        json.dumps({"rows": [{"identifier": "5-0-1", "label": "Farm Metric"}]}) + "\n",
        encoding="utf-8",
    )

    os.environ["PRIVATE_DIR"] = str(private_dir)
    os.environ["PUBLIC_DIR"] = str(public_dir)
    os.environ["DATA_DIR"] = str(data_dir)
    os.environ["MSN_ID"] = msn_id
    os.environ["PORTAL_RUNTIME_FLAVOR"] = "fnd"
    os.environ["MYCITE_PORTALS_ROOT"] = str(portals_root)

    path = runtime_root / "app.py"
    spec = importlib.util.spec_from_file_location("fnd_portal_app_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(HAS_FLASK, "flask is not installed in host python")
class FndPortalShellRouteTests(unittest.TestCase):
    def test_shell_routes_follow_new_tabs_and_redirects(self):
        with TemporaryDirectory() as temp_dir:
            module = _load_fnd_app_module(Path(temp_dir))
            client = module.app.test_client()

            system_response = client.get("/portal/system")
            self.assertEqual(system_response.status_code, 200)
            system_html = system_response.get_data(as_text=True)
            self.assertIn('id="systemShellInspectorRoot"', system_html)
            self.assertIn('id="dtResourcesInspectorStack"', system_html)
            self.assertNotIn('class="page-tabs"', system_html)
            self.assertIn('data-context-collapsed="false"', system_html)
            self.assertIn('data-shell-toggle="context"', system_html)
            self.assertIn('data-shell-toggle="inspector"', system_html)
            self.assertIn('id="portalControlPanel"', system_html)
            self.assertIn('aria-label="Control panel"', system_html)
            self.assertIn("Context", system_html)
            self.assertIn("Details", system_html)
            self.assertNotIn("Local Resources", system_html)
            self.assertNotIn("Inheritance", system_html)
            self.assertNotIn("workbench=resources", system_html)
            self.assertNotIn("workbench=anthology", system_html)
            self.assertIn('id="dtSystemAitasStrip"', system_html)
            self.assertNotIn("Open AGRO ERP", system_html)
            self.assertNotIn("ide-activitylink--tool", system_html)
            self.assertNotIn("/portal/tools/agro_erp/home", system_html)
            resources_mode_html = client.get("/portal/system?tab=workbench&workbench=resources").get_data(as_text=True)
            self.assertIn('data-system-workbench-mode="system"', resources_mode_html)
            self.assertNotIn('id="systemResourceFileList"', resources_mode_html)
            self.assertIn('id="dtResourcesLayers"', resources_mode_html)
            self.assertIn('id="dtResourcesWorkbenchStatus"', resources_mode_html)
            self.assertIn('id="dtSystemAitasStrip"', resources_mode_html)
            self.assertIn("data_tool.js", resources_mode_html)
            self.assertIn("system_shell_runtime.js", resources_mode_html)

            lr_html = client.get("/portal/system?tab=local_resources").get_data(as_text=True)
            self.assertIn('data-system-tab="workbench"', lr_html)
            self.assertIn('data-system-compat-view="local_resources"', lr_html)
            self.assertIn('id="systemShellInspectorRoot"', lr_html)
            self.assertIn('id="dataToolApp"', lr_html)
            self.assertNotIn('id="systemResourceFileList"', lr_html)
            self.assertIn('id="dtResourcesLayers"', lr_html)
            self.assertIn('id="dtSystemAitasStrip"', lr_html)
            self.assertIn("system_shell_runtime.js", lr_html)
            self.assertIn("data_tool.js", lr_html)
            self.assertNotIn("system_compatibility_runtime.js", lr_html)
            self.assertNotIn("local_resources_workbench.js", lr_html)
            self.assertNotIn('id="lrWorkbenchRoot"', lr_html)
            self.assertNotIn('id="lrTabWorkspace"', lr_html)
            self.assertNotIn('id="lrPanelWorkspace"', lr_html)

            inh_html = client.get("/portal/system?tab=inheritance").get_data(as_text=True)
            self.assertIn('data-system-tab="workbench"', inh_html)
            self.assertIn('data-system-compat-view="inheritance"', inh_html)
            self.assertIn('id="systemShellInspectorRoot"', inh_html)
            self.assertIn('id="dataToolApp"', inh_html)
            self.assertNotIn('id="systemResourceFileList"', inh_html)
            self.assertIn('id="dtResourcesLayers"', inh_html)
            self.assertIn("system_shell_runtime.js", inh_html)
            self.assertIn("data_tool.js", inh_html)
            self.assertNotIn("system_compatibility_runtime.js", inh_html)
            self.assertNotIn("system_compatibility_views.js", inh_html)
            self.assertNotIn("inheritance_workbench.js", inh_html)
            self.assertNotIn('id="inheritanceCompatibilityDetailMount"', inh_html)
            self.assertNotIn('id="inhWorkbenchRoot"', inh_html)
            self.assertNotIn("ide-activitylink--tool", inh_html)
            self.assertNotIn("Sandbox</span><small>MSS/SAMRAS resources</small>", system_html)

            self.assertEqual(client.get("/portal/network?tab=hosted").status_code, 200)
            self.assertEqual(client.get("/portal/network?tab=profile").status_code, 200)
            contracts_response = client.get("/portal/network?tab=contracts")
            self.assertIn(contracts_response.status_code, {200, 302})
            contracts_html = client.get("/portal/network?tab=contracts&id=missing").get_data(as_text=True)
            self.assertIn("Contracts", contracts_html)
            self.assertEqual(client.get("/portal/utilities?tab=vault").status_code, 200)

            self.assertEqual(client.get("/portal/tools").status_code, 302)
            self.assertIn("/portal/utilities?tab=tools", client.get("/portal/tools").headers.get("Location", ""))
            self.assertIn("/portal/utilities?tab=vault", client.get("/portal/vault").headers.get("Location", ""))
            self.assertIn("/portal/network?tab=messages&kind=log&id=request_log", client.get("/portal/inbox").headers.get("Location", ""))
            self.assertIn("/portal/tools/data_tool/home", client.get("/portal/data").headers.get("Location", ""))
            self.assertIn("/portal/tools/data_tool/home", client.get("/portal/data/legacy").headers.get("Location", ""))

            self.assertEqual(client.get("/portal/api/data/state").status_code, 200)
            self.assertEqual(client.get("/portal/api/data/anthology/table").status_code, 200)
            self.assertEqual(client.get("/portal/api/config?msn_id=3-2-3-17-77-1-6-4-1-4").status_code, 200)
            mss_compile_legacy = client.post("/portal/api/data/mss/compile", json={"resource_id": "x", "selected_refs": []})
            self.assertEqual(mss_compile_legacy.status_code, 400)
            mss_compile_shared = client.post(
                "/portal/api/data/sandbox/mss/compile",
                json={"resource_id": "x", "selected_refs": []},
            )
            self.assertIn(mss_compile_shared.status_code, {200, 400})
            local_inventory = client.get("/portal/api/data/resources/local")
            self.assertEqual(local_inventory.status_code, 200)
            self.assertTrue((local_inventory.get_json() or {}).get("ok"))
            resource_wb = client.get("/portal/api/data/system/resource_workbench")
            self.assertEqual(resource_wb.status_code, 200)
            resource_wb_payload = resource_wb.get_json() or {}
            self.assertTrue(resource_wb_payload.get("ok"))
            filenames = {str(item.get("filename") or "") for item in list(resource_wb_payload.get("files") or [])}
            self.assertEqual(filenames, {"anthology.json", "samras-txa.json", "samras-msn.json"})
            self.assertEqual(
                [str(item) for item in resource_wb_payload.get("resource_surface_file_keys") or []],
                ["anthology", "txa", "msn"],
            )
            inherited_inventory = client.get("/portal/api/data/resources/inherited")
            self.assertEqual(inherited_inventory.status_code, 200)
            self.assertTrue((inherited_inventory.get_json() or {}).get("ok"))
            resources = client.get("/portal/api/data/external/resources?source_msn_id=9-9-9-9")
            self.assertEqual(resources.status_code, 200)
            resources_payload = resources.get_json() or {}
            self.assertTrue(any(str(item.get("resource_id") or "") == "farm_metrics" for item in resources_payload.get("resources") or []))

            fetch = client.post(
                "/portal/api/data/external/fetch",
                json={"source_msn_id": "9-9-9-9", "resource_id": "farm_metrics"},
            )
            self.assertEqual(fetch.status_code, 200)
            self.assertTrue((fetch.get_json() or {}).get("ok"))
            preview = client.post(
                "/portal/api/data/external/preview_closure",
                json={
                    "source_msn_id": "9-9-9-9",
                    "resource_id": "farm_metrics",
                    "target_refs": ["9-9-9-9.5-0-1"],
                },
            )
            self.assertEqual(preview.status_code, 200)
            plan = client.post(
                "/portal/api/data/external/plan_materialization",
                json={
                    "source_msn_id": "9-9-9-9",
                    "resource_id": "farm_metrics",
                    "target_ref": "5-9-9",
                    "required_refs": ["9-9-9-9.5-0-1"],
                    "allow_auto_create": False,
                },
            )
            self.assertEqual(plan.status_code, 200)
            self.assertTrue(((plan.get_json() or {}).get("plan") or {}).get("ok"))
            contracts = client.get("/portal/api/data/write/field_contracts")
            self.assertEqual(contracts.status_code, 200)
            self.assertTrue((contracts.get_json() or {}).get("ok"))
            write_preview = client.post(
                "/portal/api/data/write/preview",
                json={
                    "intent": {
                        "intent_type": "profile_field",
                        "field_id": "portal_title",
                        "template_id": "geometry.parcel",
                        "fields": {"local_id": "31-1-1", "title": "Parcel A"},
                    }
                },
            )
            self.assertIn(write_preview.status_code, {200, 400})
            geometry_preview = client.post(
                "/portal/api/data/geometry/preview",
                json={
                    "template_id": "geometry.parcel",
                    "fields": {"local_id": "31-1-2", "title": "Parcel B"},
                },
            )
            self.assertIn(geometry_preview.status_code, {200, 400})


if __name__ == "__main__":
    unittest.main()
