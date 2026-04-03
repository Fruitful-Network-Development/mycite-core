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


def _load_tff_app_module(temp_root: Path):
    repo_root = Path(__file__).resolve().parents[1]
    instances_root = repo_root / "instances"
    runtime_root = instances_root / "_shared" / "runtime" / "flavors" / "tff"
    token = str(repo_root)
    if token not in sys.path:
        sys.path.insert(0, token)

    private_dir = temp_root / "private"
    public_dir = temp_root / "public"
    data_dir = temp_root / "data"
    private_dir.mkdir(parents=True, exist_ok=True)
    public_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    msn_id = "3-2-3-17-77-2-6-3-1-6"
    (private_dir / "config.json").write_text(
        json.dumps(
            {
                "msn_id": msn_id,
                "tools_configuration": [
                    {"name": "fnd-ebi", "status": "enabled", "mount_target": "peripherals.tools"},
                    {"name": "aws-csm", "status": "enabled", "mount_target": "peripherals.tools"},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    icon_dir = private_dir / "utilities" / "tools" / "agro-erp" / "UI"
    icon_dir.mkdir(parents=True, exist_ok=True)
    (icon_dir / "farm.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>\n", encoding="utf-8")
    (public_dir / f"msn-{msn_id}.json").write_text(json.dumps({"msn_id": msn_id, "title": "TFF"}) + "\n", encoding="utf-8")
    (public_dir / f"fnd-{msn_id}.json").write_text(
        json.dumps({"schema": "mycite.fnd.profile.v1", "msn_id": msn_id, "title": "TFF", "summary": "Brand"}) + "\n",
        encoding="utf-8",
    )
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
    os.environ["PORTAL_RUNTIME_FLAVOR"] = "tff"
    os.environ["MYCITE_PORTALS_ROOT"] = str(instances_root)

    path = runtime_root / "app.py"
    spec = importlib.util.spec_from_file_location("tff_portal_app_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(HAS_FLASK, "flask is not installed in host python")
class TffPortalShellRouteTests(unittest.TestCase):
    def test_shell_routes_and_data_legacy_endpoints(self):
        with TemporaryDirectory() as temp_dir:
            module = _load_tff_app_module(Path(temp_dir))
            client = module.app.test_client()

            system_response = client.get("/portal/system")
            self.assertEqual(system_response.status_code, 200)
            system_html = system_response.get_data(as_text=True)
            self.assertIn('id="systemShellInspectorRoot"', system_html)
            self.assertIn('id="dtResourcesInspectorStack"', system_html)
            self.assertNotIn('class="page-tabs"', system_html)
            self.assertIn('data-control-panel-collapsed="false"', system_html)
            self.assertIn('data-shell-toggle="control-panel"', system_html)
            self.assertIn('data-shell-toggle="inspector"', system_html)
            self.assertNotIn("Local Resources", system_html)
            self.assertNotIn("Inheritance", system_html)
            self.assertNotIn('data-system-' + 'compat-view', system_html)
            self.assertNotIn('data-system-' + 'requested-tab', system_html)
            self.assertNotIn('data-system-' + 'workbench-mode', system_html)
            self.assertIn('id="portalControlPanel"', system_html)
            self.assertIn('aria-label="Control panel"', system_html)
            self.assertIn("Interface Panel", system_html)
            self.assertIn('id="dtSystemAitasStrip"', system_html)
            self.assertNotIn("Open AGRO ERP", system_html)
            self.assertNotIn("ide-activitylink--tool", system_html)
            self.assertNotIn("/portal/tools/agro_erp/home", system_html)
            self.assertIn("/portal/system?mediate_tool=aws_platform_admin", system_html)
            self.assertIn("/portal/system?mediate_tool=fnd_ebi", system_html)
            self.assertIn("data_tool.js", system_html)
            self.assertIn("system_shell_runtime.js", system_html)
            self.assertIn('data-shell-composition="system"', system_html)
            self.assertIn('data-foreground-shell-region="center-workbench"', system_html)
            tool_html = client.get("/portal/system?mediate_tool=fnd_ebi").get_data(as_text=True)
            self.assertIn('data-shell-composition="tool"', tool_html)
            self.assertIn('data-active-mediate-tool="fnd_ebi"', tool_html)
            self.assertIn('data-foreground-shell-region="interface-panel"', tool_html)
            self.assertIn('data-foreground-visible="false"', tool_html)
            self.assertIn('data-primary-surface="true"', tool_html)
            self.assertIn('data-surface-layout="primary-fill"', tool_html)
            self.assertIn('data-inspector-collapsed="false"', tool_html)
            self.assertIn('data-interface-panel-scroll-root="true"', tool_html)
            self.assertIn('data-interface-panel-active-root="tool"', tool_html)
            self.assertIn('id="systemToolInterfaceRoot"', tool_html)
            self.assertIn('data-interface-panel-root="system"', tool_html)
            self.assertIn('data-tool-primary-host="true"', tool_html)
            self.assertIn('data-interface-panel-root="tool"', tool_html)
            self.assertIn('data-tool-panel-fill="true"', tool_html)
            self.assertIn('data-interface-panel-root="transient"', tool_html)
            self.assertIn('id="systemToolContextMount"', tool_html)
            aws_tool_html = client.get("/portal/system?mediate_tool=aws_platform_admin").get_data(as_text=True)
            self.assertIn('data-shell-composition="tool"', aws_tool_html)
            self.assertIn('data-active-mediate-tool="aws_platform_admin"', aws_tool_html)
            self.assertIn('data-foreground-shell-region="interface-panel"', aws_tool_html)
            self.assertIn('data-foreground-visible="false"', aws_tool_html)
            self.assertIn('data-primary-surface="true"', aws_tool_html)
            self.assertIn('data-surface-layout="primary-fill"', aws_tool_html)
            self.assertIn('data-interface-panel-scroll-root="true"', aws_tool_html)
            self.assertIn('data-interface-panel-active-root="tool"', aws_tool_html)
            self.assertIn('id="systemToolInterfaceRoot"', aws_tool_html)
            self.assertIn('data-interface-panel-root="system"', aws_tool_html)
            self.assertIn('data-tool-primary-host="true"', aws_tool_html)
            self.assertIn('data-interface-panel-root="tool"', aws_tool_html)
            self.assertIn('data-tool-panel-fill="true"', aws_tool_html)
            self.assertIn('data-interface-panel-root="transient"', aws_tool_html)
            legacy_query = client.get("/portal/system?tab=legacy_split&workbench=legacy_mode&theme=forest", follow_redirects=False)
            self.assertEqual(legacy_query.status_code, 302)
            self.assertEqual(legacy_query.headers.get("Location", ""), "/portal/system?theme=forest")
            self.assertNotIn("Sandbox</span><small>MSS/SAMRAS resources</small>", system_html)
            self.assertEqual(client.get("/portal/network?tab=contracts").status_code, 200)
            self.assertEqual(client.get("/portal/utilities?tab=vault").status_code, 200)

            self.assertEqual("/portal/system", client.get("/portal/data").headers.get("Location", ""))
            self.assertEqual("/portal/system", client.get("/portal/data/legacy").headers.get("Location", ""))

            self.assertEqual(client.get("/portal/api/data/state").status_code, 200)
            self.assertEqual(client.get("/portal/api/tools/icons/agro-erp/farm.svg").status_code, 200)
            self.assertEqual(client.get("/portal/api/tools/icons/agro-erp/../../x.svg").status_code, 404)
            self.assertEqual(client.get("/portal/api/data/anthology/table").status_code, 200)
            self.assertEqual(client.get("/portal/api/config?msn_id=3-2-3-17-77-2-6-3-1-6").status_code, 200)
            self.assertEqual(
                client.post("/portal/api/data/mss/compile", json={"resource_id": "x", "selected_refs": []}).status_code,
                400,
            )
            self.assertEqual(
                client.post(
                    "/portal/api/data/sandbox/mss/compile",
                    json={"resource_id": "x", "selected_refs": []},
                ).status_code,
                400,
            )
            self.assertEqual(client.get("/portal/api/data/resources/local").status_code, 200)
            resource_wb = client.get("/portal/api/data/system/resource_workbench")
            self.assertEqual(resource_wb.status_code, 200)
            filenames = {str(item.get("filename") or "") for item in list((resource_wb.get_json() or {}).get("files") or [])}
            self.assertEqual(filenames, {"anthology.json", "samras-txa.json", "samras-msn.json"})
            self.assertEqual(
                [str(item) for item in (resource_wb.get_json() or {}).get("resource_surface_file_keys") or []],
                ["anthology", "txa", "msn"],
            )
            self.assertEqual(client.get("/portal/api/data/resources/inherited").status_code, 200)
            self.assertEqual(client.get("/portal/api/data/tables").status_code, 404)
            self.assertEqual(client.get("/portal/api/data/table/main/view").status_code, 404)
            resources = client.get("/portal/api/data/external/resources?source_msn_id=9-9-9-9")
            self.assertEqual(resources.status_code, 200)
            contracts = client.get("/portal/api/data/write/field_contracts")
            self.assertEqual(contracts.status_code, 200)
            self.assertTrue((contracts.get_json() or {}).get("ok"))
            write_preview = client.post(
                "/portal/api/data/write/preview",
                json={
                    "intent": {
                        "intent_type": "profile_field",
                        "field_id": "property_title",
                        "template_id": "geometry.field",
                        "fields": {"local_id": "31-1-7", "title": "North Field"},
                    }
                },
            )
            self.assertIn(write_preview.status_code, {200, 400})


if __name__ == "__main__":
    unittest.main()
