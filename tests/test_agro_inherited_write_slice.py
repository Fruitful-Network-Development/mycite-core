from __future__ import annotations

import importlib.util
import json
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


def _load_register_data_routes():
    path = Path(__file__).resolve().parents[1] / "instances" / "_shared" / "portal" / "api" / "data_workspace.py"
    portals_root = path.parents[4]
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    spec = importlib.util.spec_from_file_location("data_workspace_agro_slice_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.register_data_routes


class _WorkspaceStub:
    def __init__(self, *, anthology_rows: dict[str, object] | None = None, data_dir: str = ".") -> None:
        self.calls: list[dict[str, object]] = []
        self._counter = 0
        self._anthology_rows = anthology_rows if isinstance(anthology_rows, dict) else {}
        self.storage = type("StorageStub", (), {"data_dir": data_dir})()

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
        self._anthology_rows[identifier] = {"identifier": identifier, "magnitude": magnitude, "label": label}
        return {"ok": True, "identifier": identifier, "contract_mss_sync": {"triggered": True, "reason": "test"}}


@unittest.skipUnless(HAS_FLASK, "flask is not installed in host python")
class AgroInheritedWriteSliceTests(unittest.TestCase):
    def setUp(self):
        register_data_routes = _load_register_data_routes()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.anthology_rows: dict[str, object] = {
            "8-5-99": {
                "identifier": "8-5-99",
                "label": "agro-profile-field",
                "pairs": [],
                "magnitude": "{}",
            }
        }
        self.workspace = _WorkspaceStub(anthology_rows=self.anthology_rows, data_dir=self._tmpdir.name)
        self.config_payload = {"agro": {"inherited": {}}}
        self.app = Flask(__name__)
        register_data_routes(
            self.app,
            workspace=self.workspace,
            anthology_payload_provider=lambda: {"rows": self.anthology_rows},
            active_config_provider=lambda: dict(self.config_payload),
            active_config_saver=self._save_config,
            msn_id_provider=lambda: "9-9-9",
            include_home_redirect=False,
            include_legacy_shims=False,
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self._tmpdir.cleanup()

    def _save_config(self, payload):
        self.config_payload = dict(payload)
        return True

    def test_agro_inherited_write_headless_slice(self):
        # 1) compile isolated txa resource JSON
        singular_seed = {
            "schema": "mycite.sandbox.singular_mss_resource.v1",
            "resource_id": "agro-txa-1",
            "resource_kind": "txa",
            "origin_kind": "local",
            "source_portal": "9-9-9",
            "source_ref": "5-0-1",
            "draft_state": {
                "selected_ids": ["8-5-11", "8-4-22"],
                "compact_payload": {
                    "8-5-11": [["8-5-11", "0-0-1", "1"], ["agro-product-profile"]],
                    "8-4-22": [["8-4-22", "0-0-1", "1"], ["agro-invoice-log"]],
                },
            },
            "canonical_state": {
                "selected_ids": ["8-5-11", "8-4-22"],
                "compact_payload": {
                    "8-5-11": [["8-5-11", "0-0-1", "1"], ["agro-product-profile"]],
                    "8-4-22": [["8-4-22", "0-0-1", "1"], ["agro-invoice-log"]],
                },
            },
            "mss_form": {"bitstring": "", "wire_variant": ""},
            "abstraction_root": "8-5-11",
            "compile_metadata": {"compiled": False, "warnings": []},
            "updated_at": 0,
        }
        saved = self.client.post("/portal/api/data/sandbox/resources/agro-txa-1/save", json={"payload": singular_seed})
        self.assertEqual(saved.status_code, 200)
        compiled = self.client.post("/portal/api/data/sandbox/resources/agro-txa-1/compile", json={})
        self.assertEqual(compiled.status_code, 200)
        compiled_payload = compiled.get_json() or {}
        self.assertTrue(compiled_payload.get("ok"))
        resource_payload = (compiled_payload.get("compiled_payload") or {}) if isinstance(compiled_payload, dict) else {}
        self.assertTrue(((resource_payload.get("compile_metadata") or {}).get("compiled")))
        self.assertTrue(((resource_payload.get("published_value") or {}).get("descriptor_digest")))

        # 2) publish resource value through contact-card style surface
        exposed = self.client.get("/portal/api/data/sandbox/exposed/contact_card")
        self.assertEqual(exposed.status_code, 200)
        exposed_payload = exposed.get_json() or {}
        sandbox_exposed = exposed_payload.get("sandbox_exposed_resources") or []
        picked = [item for item in sandbox_exposed if str(item.get("resource_id")) == "agro-txa-1"]
        self.assertTrue(picked)
        published_value = ((picked[0] or {}).get("value") or {}) if isinstance(picked[0], dict) else {}
        self.assertTrue(((published_value.get("published_value") or {}).get("descriptor_digest")))

        # 3) adapt published value into inherited txa context
        adapted_resp = self.client.post(
            "/portal/api/data/sandbox/inherited/adapt_txa",
            json={"published_resource_value": published_value},
        )
        self.assertEqual(adapted_resp.status_code, 200)
        adapted = adapted_resp.get_json() or {}
        self.assertTrue(adapted.get("ok"))
        bindings = adapted.get("field_ref_bindings") if isinstance(adapted.get("field_ref_bindings"), dict) else {}
        self.assertIn("9-9-9.8-5-11", list(bindings.get("product_profile_refs") or []))
        self.assertIn("9-9-9.8-4-22", list(bindings.get("invoice_log_refs") or []))

        # 4) AITAS compiled_constraint includes inherited txa-aware structure
        self.anthology_rows["8-5-99"] = {
            "identifier": "8-5-99",
            "label": "agro-profile-field",
            "pairs": [],
            "magnitude": json.dumps({"inherited_context": adapted}, separators=(",", ":")),
        }
        inspect = self.client.post("/portal/api/data/aitas/archetype/inspect", json={"datum_ref": "8-5-99"})
        self.assertEqual(inspect.status_code, 200)
        inspected = inspect.get_json() or {}
        compiled_constraint = (((inspected.get("aitas") or {}).get("archetype") or {}).get("compiled_constraint") or {})
        self.assertEqual(compiled_constraint.get("constraint_family"), "samras")
        self.assertEqual(compiled_constraint.get("value_kind"), "txa_id")
        self.assertTrue(compiled_constraint.get("descriptor_digest"))
        self.assertTrue(compiled_constraint.get("inherited_resource_ref"))

        # 5-6) preview/apply product-profile and invoice-log inherited writes
        before_count = len(self.anthology_rows)

        product_intent = {
            "intent_type": "profile_field",
            "field_id": "inherited_product_profile_ref",
            "write_mode": "stage_inherited_ref",
            "resource_ref": "sandbox:agro-txa-1",
            "fields": {},
        }
        product_preview = self.client.post("/portal/api/data/write/preview", json={"intent": product_intent})
        self.assertEqual(product_preview.status_code, 200)
        product_apply = self.client.post("/portal/api/data/write/apply", json={"intent": product_intent})
        self.assertEqual(product_apply.status_code, 200)
        product_apply_payload = product_apply.get_json() or {}
        product_summary = product_apply_payload.get("mutation_summary") or {}
        self.assertEqual(product_summary.get("created_count"), 0)
        self.assertEqual(product_summary.get("reused_count"), 1)
        self.assertEqual((((self.config_payload.get("agro") or {}).get("inherited") or {}).get("product_profile_ref")), "9-9-9.8-5-11")

        invoice_intent = {
            "intent_type": "profile_field",
            "field_id": "inherited_supply_log_ref",
            "write_mode": "stage_inherited_ref",
            "resource_ref": "sandbox:agro-txa-1",
            "fields": {},
        }
        invoice_preview = self.client.post("/portal/api/data/write/preview", json={"intent": invoice_intent})
        self.assertEqual(invoice_preview.status_code, 200)
        invoice_apply = self.client.post("/portal/api/data/write/apply", json={"intent": invoice_intent})
        self.assertEqual(invoice_apply.status_code, 200)
        invoice_apply_payload = invoice_apply.get_json() or {}
        invoice_summary = invoice_apply_payload.get("mutation_summary") or {}
        self.assertEqual(invoice_summary.get("created_count"), 0)
        self.assertEqual(invoice_summary.get("reused_count"), 1)
        self.assertEqual((((self.config_payload.get("agro") or {}).get("inherited") or {}).get("supply_log_ref")), "9-9-9.8-4-22")

        # 7-8) no txa tree materialization into anthology
        after_count = len(self.anthology_rows)
        self.assertEqual(before_count, after_count)
        self.assertFalse(any(str(key).startswith("4-1-") for key in self.anthology_rows.keys()))

        # 9) resource JSON remains source-of-truth
        resource_path = Path(self._tmpdir.name) / "sandbox" / "resources" / "agro-txa-1.json"
        self.assertTrue(resource_path.exists())
        persisted = json.loads(resource_path.read_text(encoding="utf-8"))
        self.assertTrue(((persisted.get("compile_metadata") or {}).get("compiled")))
        self.assertEqual(str(persisted.get("resource_id") or ""), "agro-txa-1")


if __name__ == "__main__":
    unittest.main()
