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


CORRECTED_TXA_PATH = Path("/srv/mycite-state/instances/fnd/data/samras-txa.json")
CORRECTED_MSN_PATH = Path("/srv/mycite-state/instances/fnd/data/samras-msn.json")


def _load_samras_module():
    portals_root = Path(__file__).resolve().parents[1] / "portals"
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return importlib.import_module("_shared.portal.samras")


def _load_register_data_routes():
    repo_root = Path(__file__).resolve().parents[1]
    path = repo_root / "instances" / "_shared" / "portal" / "api" / "data_workspace.py"
    for candidate in (repo_root, repo_root / "instances", repo_root / "packages"):
        token = str(candidate)
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
    def test_canonical_encode_decode_roundtrip_uses_breadth_first_child_counts(self):
        samras = _load_samras_module()
        structure = samras.encode_canonical_structure_from_addresses(
            ["1", "2", "1-1", "1-2", "2-1"],
            root_ref="0-0-5",
        )
        self.assertEqual(structure.values, (2, 2, 1, 0, 0, 0))
        decoded = samras.decode_canonical_bitstream(structure.bitstream, root_ref="0-0-5")
        self.assertEqual(decoded.addresses, ("1", "2", "1-1", "1-2", "2-1"))
        self.assertEqual(decoded.values, structure.values)
        self.assertEqual(decoded.bitstream, structure.bitstream)

    def test_invalid_address_set_is_rejected(self):
        samras = _load_samras_module()
        with self.assertRaises(samras.InvalidSamrasStructure):
            samras.encode_canonical_structure_from_addresses(["1", "1-2"], root_ref="0-0-5")

    def test_invalid_stop_table_is_rejected(self):
        samras = _load_samras_module()
        invalid = samras.SamrasStructure(
            root_ref="0-0-5",
            bitstream="",
            address_width_bits=1,
            stop_count_width_bits=1,
            stop_count=2,
            stop_addresses=(2, 2),
            value_tokens=("1", "0", "0"),
            values=(1, 0, 0),
            addresses=("1",),
            source_format="canonical",
            canonical_state="canonical",
            warnings=(),
        )
        report = samras.validate_structure(invalid)
        self.assertFalse(report.ok)
        self.assertTrue(any("strictly increasing" in item for item in report.errors))

    def test_corrected_staging_files_load_through_structure_aware_workspace(self):
        samras = _load_samras_module()
        for path in [CORRECTED_TXA_PATH, CORRECTED_MSN_PATH]:
            if not path.is_file():
                self.skipTest(f"missing corrected staging file: {path}")
            payload = json.loads(path.read_text(encoding="utf-8"))
            workspace = samras.load_workspace_from_compact_payload(payload)
            self.assertEqual(workspace.structure.root_ref, "0-0-5")
            self.assertEqual(workspace.structure.canonical_state, "canonical")
            self.assertGreater(len(workspace.nodes), 0)
            self.assertTrue(any("reconstructed from staged address rows" in item for item in workspace.warnings))

    def test_sandbox_save_path_writes_canonical_binary_only(self):
        portals_root = Path(__file__).resolve().parents[1] / "portals"
        token = str(portals_root)
        if token not in sys.path:
            sys.path.insert(0, token)
        from _shared.portal.sandbox.engine import SandboxEngine

        with tempfile.TemporaryDirectory() as tmp:
            engine = SandboxEngine(data_root=Path(tmp))
            staged = engine.create_or_update_samras_resource(
                resource_id="msn.samras.fixture",
                structure_payload="1-1-0",
                rows=[{"address_id": "1", "title": "root"}],
                value_kind="msn_id",
                source="unit-test",
            )
            self.assertTrue(staged.ok, staged.errors)
            raw_payload = json.loads((Path(tmp) / "sandbox" / "resources" / "msn.samras.fixture.json").read_text(encoding="utf-8"))
            canonical = str(raw_payload.get("structure_payload") or "")
            self.assertTrue(canonical)
            self.assertTrue(set(canonical).issubset({"0", "1"}))
            self.assertNotIn("-", canonical)

    def test_sandbox_rejects_title_rows_outside_governing_structure(self):
        portals_root = Path(__file__).resolve().parents[1] / "portals"
        token = str(portals_root)
        if token not in sys.path:
            sys.path.insert(0, token)
        from _shared.portal.sandbox.engine import SandboxEngine

        with tempfile.TemporaryDirectory() as tmp:
            engine = SandboxEngine(data_root=Path(tmp))
            staged = engine.create_or_update_samras_resource(
                resource_id="txa.samras.fixture",
                structure_payload="1-1-0",
                rows=[{"address_id": "9-9-9", "title": "bad"}],
                value_kind="txa_id",
                source="unit-test",
            )
            self.assertFalse(staged.ok)
            self.assertTrue(any("governing structure" in item for item in staged.errors))

    def test_local_resource_payload_normalizes_samras_reference_rows(self):
        registry = _load_registry_module()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "resources" / "local" / "samras.msn.json"
            body = {
                "schema": "mycite.portal.resource.local.v1",
                "resource_id": "local:samras.msn",
                "resource_kind": "samras_msn",
                "anthology_compatible_payload": {
                    "3-1-1": [["3-1-1", "0-0-5", "1-1-0"], ["samras-local-row"]]
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

    def test_structure_routes_edit_by_address_and_reencode(self):
        upsert = self.client.post(
            "/portal/api/data/sandbox/samras/upsert",
            json={
                "resource_id": "txa.samras.fixture",
                "structure_payload": "1-1-0",
                "value_kind": "txa_id",
                "rows": [{"address_id": "1", "title": "root"}],
            },
        )
        self.assertEqual(upsert.status_code, 200)
        create_child = self.client.post(
            "/portal/api/data/sandbox/samras/txa.samras.fixture/node/create_child",
            json={"parent_address": "1", "value": 2},
        )
        self.assertEqual(create_child.status_code, 200)
        created = ((create_child.get_json() or {}).get("created_address") or "")
        self.assertEqual(created, "1-1")
        inspect = self.client.post(
            "/portal/api/data/sandbox/samras/txa.samras.fixture/node/inspect",
            json={"address_id": created},
        )
        self.assertEqual(inspect.status_code, 200)
        set_node = self.client.post(
            "/portal/api/data/sandbox/samras/txa.samras.fixture/node/set",
            json={"address_id": created, "value": 1},
        )
        self.assertEqual(set_node.status_code, 200)
        decoded = self.client.get("/portal/api/data/sandbox/samras/txa.samras.fixture/structure")
        self.assertEqual(decoded.status_code, 200)
        compiled = ((decoded.get_json() or {}).get("compiled_payload") or {})
        canonical = str(compiled.get("canonical_magnitude") or "")
        self.assertTrue(canonical)
        self.assertTrue(set(canonical).issubset({"0", "1"}))


if __name__ == "__main__":
    unittest.main()
