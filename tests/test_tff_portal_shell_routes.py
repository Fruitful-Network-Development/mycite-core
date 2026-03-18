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

    msn_id = "3-2-3-17-77-2-6-3-1-6"
    (private_dir / "config.json").write_text(json.dumps({"msn_id": msn_id}) + "\n", encoding="utf-8")
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
    os.environ["MYCITE_PORTALS_ROOT"] = str(portals_root)

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

            self.assertEqual(client.get("/portal/system").status_code, 200)
            system_html = client.get("/portal/system").get_data(as_text=True)
            self.assertIn("Local Resources", system_html)
            self.assertIn("Inheritance", system_html)
            self.assertNotIn("Sandbox</span><small>MSS/SAMRAS resources</small>", system_html)
            self.assertEqual(client.get("/portal/network?tab=contracts").status_code, 200)
            self.assertEqual(client.get("/portal/utilities?tab=vault").status_code, 200)

            self.assertIn("/portal/tools/data_tool/home", client.get("/portal/data").headers.get("Location", ""))
            self.assertIn("/portal/tools/data_tool/home", client.get("/portal/data/legacy").headers.get("Location", ""))

            self.assertEqual(client.get("/portal/api/data/state").status_code, 200)
            self.assertEqual(client.get("/portal/api/data/anthology/table").status_code, 200)
            self.assertEqual(client.get("/portal/api/data/resources/local").status_code, 200)
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
