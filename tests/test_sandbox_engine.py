from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


def _load_sandbox_module():
    portals_root = Path(__file__).resolve().parents[1] / "instances"
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return importlib.import_module("_shared.portal.sandbox")


def _example_payload() -> dict[str, object]:
    return {
        "0-0-1": [["0-0-1", "0", "0"], ["top"]],
        "0-0-2": [["0-0-2", "0", "0"], ["tiu"]],
        "1-1-1": [["1-1-1", "0-0-2", "315569254450000000000000000000000000000"], ["sec-babel"]],
        "1-1-2": [["1-1-2", "0-0-1", "946707763350000000"], ["utc-bacillete"]],
        "2-1-1": [["2-1-1", "1-1-2", "1"], ["second-isolette"]],
        "3-1-1": [["3-1-1", "2-1-1", "0"], ["utc-babelette"]],
        "4-2-1": [["4-2-1", "1-1-1", "63072000000", "3-1-1", "1"], ["y2k-event"]],
        "5-0-1": [["5-0-1", "4-2-1", "[\"4-2-1\"]"], ["txa"]],
        "5-0-2": [["5-0-2", "4-2-1", "[\"4-2-1\"]"], ["msn"]],
    }


class SandboxEngineTests(unittest.TestCase):
    def test_samras_structure_encode_decode_and_validation(self):
        sandbox = _load_sandbox_module()
        descriptor = sandbox.decode_structure_payload(
            "3-3-0-0-1-1-4",
            value_kind="txa_id",
            source_ref="unit-test",
        )
        self.assertEqual(sandbox.encode_structure_payload(descriptor), "3-3-0-0-1-1-4")
        parts = sandbox.decode_node_value("3-2-3-17-77-1")
        result = sandbox.validate_node_value(parts, descriptor)
        self.assertFalse(result["ok"])
        # role default is definer; switch to value for validation path
        normalized = sandbox.normalize_descriptor(
            {"structure_payload": "3-3-0-0-1-1-4", "role": "value", "value_kind": "txa_id"}
        )
        ok_result = sandbox.validate_node_value(parts, normalized)
        self.assertTrue(ok_result["ok"])

    def test_sandbox_compiles_and_decodes_mss(self):
        sandbox = _load_sandbox_module()
        with tempfile.TemporaryDirectory() as tmp:
            engine = sandbox.SandboxEngine(data_root=Path(tmp))
            compiled = engine.compile_mss_resource(
                resource_id="unit-mss",
                selected_refs=["4-2-1"],
                anthology_payload=_example_payload(),
                local_msn_id="3-2-3-17-77-1-6-4-1-4",
            )
            self.assertTrue(compiled.ok)
            bitstring = str((compiled.compiled_payload or {}).get("bitstring") or "")
            self.assertTrue(bitstring)
            decoded = engine.decode_mss_resource(bitstring=bitstring, resource_id="unit-mss-decoded")
            self.assertTrue(decoded.ok)
            row_ids = [str(item.get("identifier") or "") for item in ((decoded.compiled_payload or {}).get("rows") or [])]
            self.assertIn("5-0-1", row_ids)

    def test_migration_extracts_samras_trees_into_isolated_resources(self):
        sandbox = _load_sandbox_module()
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            anthology_path = data_root / "anthology.json"
            payload = _example_payload()
            payload["5-0-1"] = [["5-0-1", "4-2-1", "[\"4-2-1\"]"], ["samras_set_local_txa"]]
            payload["5-0-2"] = [["5-0-2", "4-2-1", "[\"4-2-1\"]"], ["samras_set_local_msn"]]
            anthology_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            dry = sandbox.migrate_fnd_samras_rows_to_sandbox(
                anthology_path=anthology_path,
                data_root=data_root,
                apply_changes=False,
            )
            self.assertTrue(dry.ok)
            self.assertIn("5-0-1", dry.exact_live_txa_msn_rows)
            self.assertTrue(dry.resource_payload_paths)
            applied = sandbox.migrate_fnd_samras_rows_to_sandbox(
                anthology_path=anthology_path,
                data_root=data_root,
                apply_changes=True,
            )
            self.assertTrue(applied.ok)
            updated = json.loads(anthology_path.read_text(encoding="utf-8"))
            self.assertNotIn("5-0-1", updated)
            self.assertNotIn("5-0-2", updated)
            for rid in applied.sandbox_resources:
                self.assertTrue((data_root / "sandbox" / "resources" / f"{rid}.json").exists())

    def test_isolated_resource_compile_updates_publication_state(self):
        sandbox = _load_sandbox_module()
        with tempfile.TemporaryDirectory() as tmp:
            engine = sandbox.SandboxEngine(data_root=Path(tmp))
            seed = {
                "schema": "mycite.sandbox.singular_mss_resource.v1",
                "resource_id": "txa.samras.5-0-1",
                "resource_kind": "txa",
                "origin_kind": "local",
                "source_portal": "3-2-3-17-77-1-6-4-1-4",
                "source_ref": "5-0-1",
                "draft_state": {"selected_ids": ["4-2-1"], "compact_payload": _example_payload()},
                "canonical_state": {"selected_ids": ["4-2-1"], "compact_payload": _example_payload()},
                "mss_form": {"bitstring": "", "wire_variant": ""},
                "abstraction_root": "4-2-1",
                "compile_metadata": {"compiled": False, "warnings": []},
                "updated_at": 0,
            }
            saved = engine.save_resource("txa.samras.5-0-1", seed)
            self.assertTrue(saved.ok)
            compiled = engine.compile_isolated_mss_resource(resource_id="txa.samras.5-0-1")
            self.assertTrue(compiled.ok)
            compiled_payload = compiled.compiled_payload or {}
            mss_form = compiled_payload.get("mss_form") if isinstance(compiled_payload.get("mss_form"), dict) else {}
            self.assertTrue(str(mss_form.get("bitstring") or ""))
            exposed = engine.generate_exposed_resource_values(local_msn_id="3-2-3-17-77-1-6-4-1-4")
            self.assertTrue(any(str(item.get("resource_id")) == "txa.samras.5-0-1" for item in exposed))


if __name__ == "__main__":
    unittest.main()
