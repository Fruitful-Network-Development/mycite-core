from __future__ import annotations

import importlib
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


def _load_sandbox_module():
    portals_root = Path(__file__).resolve().parents[1] / "portals"
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return importlib.import_module("_shared.portal.sandbox")


def _load_register_data_routes():
    path = Path(__file__).resolve().parents[1] / "portals" / "_shared" / "portal" / "api" / "data_workspace.py"
    portals_root = path.parents[4]
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    spec = importlib.util.spec_from_file_location("data_workspace_samras_rule_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.register_data_routes


def _load_registry_module():
    portals_root = Path(__file__).resolve().parents[1] / "portals"
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return importlib.import_module("_shared.portal.data_engine.resource_registry")


class _WorkspaceStub:
    def __init__(self, *, data_dir: str = "."):
        self.storage = type("StorageStub", (), {"data_dir": data_dir})()


class SamrasStructureRuleTests(unittest.TestCase):
    def test_asparagus_legacy_fixture_compiles_correct_stop_table(self):
        sandbox = _load_sandbox_module()
        structure = sandbox.decode_legacy_samras_value("1-10-10-1-100-0-0-0-0-0-0", root_ref="0-0-5")
        self.assertEqual(structure.root_ref, "0-0-5")
        self.assertEqual(structure.stop_count, 10)
        self.assertEqual(structure.stop_addresses, [1, 3, 5, 6, 9, 10, 11, 12, 13, 14])
        self.assertEqual(structure.decoded_value_count, 11)

    def test_canonical_decode_and_exact_roundtrip_stability(self):
        sandbox = _load_sandbox_module()
        legacy = sandbox.decode_legacy_samras_value("1-10-10-1-100-0-0-0-0-0-0", root_ref="0-0-5")
        canonical = sandbox.compile_canonical_samras_bitstring(legacy)
        decoded = sandbox.decode_canonical_samras_bitstring(canonical, root_ref="0-0-5")
        self.assertEqual(decoded.root_ref, "0-0-5")
        self.assertEqual(decoded.node_values, legacy.node_values)
        self.assertEqual(decoded.stop_addresses, legacy.stop_addresses)
        self.assertEqual(sandbox.compile_canonical_samras_bitstring(decoded), canonical)

    def test_structure_edit_reencodes_canonical_value(self):
        sandbox = _load_sandbox_module()
        structure = sandbox.decode_legacy_samras_value("1-10-10-1-100-0-0-0-0-0-0", root_ref="0-0-5")
        base_canonical = sandbox.compile_canonical_samras_bitstring(structure)
        edited = sandbox.set_node_value_by_address(structure, address_id="1-1-1", value=11)
        edited_canonical = sandbox.compile_canonical_samras_bitstring(edited)
        self.assertNotEqual(base_canonical, edited_canonical)
        self.assertTrue((sandbox.validate_samras_structure(edited) or {}).get("ok"))

    def test_invalid_stop_address_rejected(self):
        sandbox = _load_sandbox_module()
        invalid = sandbox.SamrasStructure(
            root_ref="0-0-5",
            address_width_bits=4,
            stop_count_width_bits=4,
            stop_count=2,
            stop_addresses=[2, 2],
            node_values=[1, 10, 0],
            address_map={"1": 1, "1-1": 10, "1-1-1": 0},
            source_format="canonical_binary",
            canonical_state="canonical",
            warnings=[],
        )
        result = sandbox.validate_samras_structure(invalid)
        self.assertFalse(result.get("ok"))
        self.assertTrue(any("strictly increasing" in str(item) for item in list(result.get("errors") or [])))

    def test_invalid_stop_count_rejected(self):
        sandbox = _load_sandbox_module()
        invalid = sandbox.SamrasStructure(
            root_ref="0-0-5",
            address_width_bits=4,
            stop_count_width_bits=4,
            stop_count=1,
            stop_addresses=[1, 3],
            node_values=[1, 10, 0],
            address_map={"1": 1, "1-1": 10, "1-1-1": 0},
            source_format="canonical_binary",
            canonical_state="canonical",
            warnings=[],
        )
        result = sandbox.validate_samras_structure(invalid)
        self.assertFalse(result.get("ok"))
        self.assertTrue(any("stop_count must equal" in str(item) for item in list(result.get("errors") or [])))

    def test_invalid_header_width_rejected(self):
        sandbox = _load_sandbox_module()
        invalid = sandbox.SamrasStructure(
            root_ref="0-0-5",
            address_width_bits=1,
            stop_count_width_bits=1,
            stop_count=10,
            stop_addresses=[1, 3, 5, 6, 9, 10, 11, 12, 13, 14],
            node_values=[1, 10, 10, 1, 100, 0, 0, 0, 0, 0, 0],
            address_map={},
            source_format="canonical_binary",
            canonical_state="canonical",
            warnings=[],
        )
        with self.assertRaises(ValueError):
            sandbox.compile_canonical_samras_bitstring(invalid)

    def test_sandbox_save_path_writes_canonical_binary_only(self):
        sandbox = _load_sandbox_module()
        with tempfile.TemporaryDirectory() as tmp:
            engine = sandbox.SandboxEngine(data_root=Path(tmp))
            staged = engine.create_or_update_samras_resource(
                resource_id="msn.samras.fixture",
                structure_payload="1-10-10-1-100-0-0-0-0-0-0",
                rows=[{"address_id": "1", "title": "asparagaceae"}],
                value_kind="msn_id",
                source="unit-test",
            )
            self.assertTrue(staged.ok)
            raw_payload = json.loads((Path(tmp) / "sandbox" / "resources" / "msn.samras.fixture.json").read_text(encoding="utf-8"))
            canonical = str(raw_payload.get("structure_payload") or "")
            self.assertTrue(canonical)
            self.assertTrue(set(canonical).issubset({"0", "1"}))
            self.assertNotIn("-", canonical)
            decoded = engine.decode_samras_resource("msn.samras.fixture")
            self.assertTrue(decoded.ok)
            self.assertEqual((((decoded.compiled_payload or {}).get("samras_structure") or {}).get("root_ref")), "0-0-5")

    def test_local_resource_payload_normalizes_samras_reference_rows(self):
        registry = _load_registry_module()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "resources" / "local" / "samras.msn.json"
            body = {
                "schema": "mycite.portal.resource.local.v1",
                "resource_id": "local:samras.msn",
                "resource_kind": "samras_msn",
                "anthology_compatible_payload": {
                    "3-1-1": [["3-1-1", "0-0-5", "1-10-10-1-100-0-0-0-0-0-0"], ["samras-local-row"]]
                },
            }
            written = registry.write_resource_file(target, body)
            normalized_payload = written.get("anthology_compatible_payload") if isinstance(written.get("anthology_compatible_payload"), dict) else {}
            compact_row = normalized_payload.get("3-1-1") if isinstance(normalized_payload.get("3-1-1"), list) else []
            magnitude = str((compact_row[0] or [None, None, ""])[2]) if compact_row else ""
            self.assertTrue(magnitude)
            self.assertTrue(set(magnitude).issubset({"0", "1"}))
            self.assertNotIn("-", magnitude)


@unittest.skipUnless(HAS_FLASK, "flask is not installed in host python")
class SamrasSandboxRouteTests(unittest.TestCase):
    def setUp(self):
        register_data_routes = _load_register_data_routes()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        workspace = _WorkspaceStub(data_dir=self._tmpdir.name)
        register_data_routes(
            self.app,
            workspace=workspace,
            anthology_payload_provider=lambda: {"rows": {}},
            active_config_provider=lambda: {},
            active_config_saver=lambda payload: True,
            msn_id_provider=lambda: "9-9-9",
            include_home_redirect=False,
            include_legacy_shims=False,
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_structure_routes_edit_by_address(self):
        upsert = self.client.post(
            "/portal/api/data/sandbox/samras/upsert",
            json={
                "resource_id": "txa.samras.fixture",
                "structure_payload": "1-10-10-1-100-0-0-0-0-0-0",
                "value_kind": "txa_id",
                "rows": [{"address_id": "1", "title": "root"}],
            },
        )
        self.assertEqual(upsert.status_code, 200)
        set_node = self.client.post(
            "/portal/api/data/sandbox/samras/txa.samras.fixture/node/set",
            json={"address_id": "1", "value": 0},
        )
        self.assertEqual(set_node.status_code, 200)
        create_child = self.client.post(
            "/portal/api/data/sandbox/samras/txa.samras.fixture/node/create_child",
            json={"parent_address": "1", "value": 1},
        )
        self.assertEqual(create_child.status_code, 200)
        created = ((create_child.get_json() or {}).get("created_address") or "")
        self.assertTrue(created.startswith("1-"))
        inspect = self.client.post(
            "/portal/api/data/sandbox/samras/txa.samras.fixture/node/inspect",
            json={"address_id": created},
        )
        self.assertEqual(inspect.status_code, 200)
        delete = self.client.post(
            "/portal/api/data/sandbox/samras/txa.samras.fixture/node/delete",
            json={"address_id": created},
        )
        self.assertEqual(delete.status_code, 200)
        decoded = self.client.get("/portal/api/data/sandbox/samras/txa.samras.fixture/structure")
        self.assertEqual(decoded.status_code, 200)
        canonical = str((((decoded.get_json() or {}).get("compiled_payload") or {}).get("canonical_magnitude") or ""))
        self.assertTrue(canonical)
        self.assertTrue(set(canonical).issubset({"0", "1"}))


if __name__ == "__main__":
    unittest.main()
