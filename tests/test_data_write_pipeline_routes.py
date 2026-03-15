from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

try:
    from flask import Flask

    HAS_FLASK = True
except ModuleNotFoundError:  # pragma: no cover
    HAS_FLASK = False
    Flask = None  # type: ignore[assignment]

def _load_register_data_routes():
    path = Path(__file__).resolve().parents[1] / "portals" / "_shared" / "portal" / "api" / "data_workspace.py"
    portals_root = path.parents[4]
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    spec = importlib.util.spec_from_file_location("data_workspace_test_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.register_data_routes


class _WorkspaceStub:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self._counter = 0

    def append_anthology_datum(self, *, layer, value_group, reference, magnitude, label, pairs=None):
        self._counter += 1
        identifier = f"{layer}-{value_group}-{self._counter}"
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
        return {
            "ok": True,
            "identifier": identifier,
            "contract_mss_sync": {"triggered": True, "reason": "test"},
        }


@unittest.skipUnless(HAS_FLASK, "flask is not installed in host python")
class DataWritePipelineRouteTests(unittest.TestCase):
    def setUp(self):
        register_data_routes = _load_register_data_routes()
        self.workspace = _WorkspaceStub()
        self.config_payload = {"display": {"title": "Before"}}
        self.app = Flask(__name__)
        register_data_routes(
            self.app,
            workspace=self.workspace,
            anthology_payload_provider=lambda: {"rows": []},
            active_config_provider=lambda: dict(self.config_payload),
            active_config_saver=self._save_config,
            include_home_redirect=False,
            include_legacy_shims=False,
        )
        self.client = self.app.test_client()

    def _save_config(self, payload):
        self.config_payload = dict(payload)
        return True

    def test_profile_field_preview_uses_contract_schema(self):
        response = self.client.post(
            "/portal/api/data/write/preview",
            json={
                "intent": {
                    "intent_type": "profile_field",
                    "field_id": "portal_title",
                    "template_id": "geometry.parcel",
                    "fields": {"local_id": "31-1-4", "title": "Parcel"},
                }
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json() or {}
        self.assertTrue(payload.get("ok"))
        contract = ((payload.get("validation") or {}).get("contract") or {})
        self.assertEqual(contract.get("field_id"), "portal_title")
        self.assertTrue(any(item.get("path") == "display.title" for item in payload.get("config_updates") or []))

    def test_apply_updates_anthology_and_config_ref(self):
        response = self.client.post(
            "/portal/api/data/write/apply",
            json={
                "intent": {
                    "intent_type": "profile_field",
                    "field_id": "portal_title",
                    "template_id": "geometry.parcel",
                    "fields": {"local_id": "31-1-9", "title": "Parcel Nine"},
                }
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json() or {}
        self.assertTrue(payload.get("ok"))
        self.assertTrue(payload.get("created_datum_refs"))
        self.assertEqual(((payload.get("contract_mss_sync") or {}).get("triggered")), True)
        self.assertEqual((((self.config_payload.get("display") or {})).get("title")), "31-1-9")

    def test_geometry_preview_and_apply_routes(self):
        preview = self.client.post(
            "/portal/api/data/geometry/preview",
            json={"template_id": "geometry.plot", "fields": {"local_id": "31-1-22", "title": "Plot 22"}},
        )
        self.assertEqual(preview.status_code, 200)
        apply_response = self.client.post(
            "/portal/api/data/geometry/apply",
            json={"template_id": "geometry.plot", "fields": {"local_id": "31-1-23", "title": "Plot 23"}},
        )
        self.assertEqual(apply_response.status_code, 200)
        self.assertTrue((apply_response.get_json() or {}).get("ok"))


if __name__ == "__main__":
    unittest.main()
