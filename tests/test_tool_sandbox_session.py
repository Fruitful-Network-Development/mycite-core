from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    from flask import Flask

    HAS_FLASK = True
except ModuleNotFoundError:  # pragma: no cover
    HAS_FLASK = False
    Flask = None  # type: ignore[assignment]

from _shared.portal.data_engine.profile_config_refs import get_path
from _shared.portal.sandbox import LocalResourceLifecycleService, SandboxEngine
from _shared.portal.sandbox.tool_sandbox_session import (
    ToolSandboxPromotionHooks,
    ToolSandboxRuntimeDeps,
    ToolSandboxSessionManager,
)
from _shared.portal.sandbox.workspace_contract import AGRO_ERP_SANDBOX_DECLARATION


def _load_register_data_routes():
    import importlib.util

    path = (
        Path(__file__).resolve().parents[1]
        / "portals"
        / "_shared"
        / "portal"
        / "api"
        / "data_workspace.py"
    )
    portals_root = path.parents[4]
    token = str(portals_root)
    if token not in __import__("sys").path:
        __import__("sys").path.insert(0, token)
    spec = importlib.util.spec_from_file_location("data_workspace_tool_session_tests", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.register_data_routes


class _WorkspaceStub:
    def __init__(self, *, data_dir: str) -> None:
        self.storage = type("StorageStub", (), {"data_dir": data_dir})()

    def list_tables(self):
        return []

    def get_state_snapshot(self):
        return {}

    def update_anthology_profile(self, **kwargs):
        return {"ok": True, "errors": [], "warnings": [], "kwargs": kwargs}


class ToolSandboxSessionServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "sandbox" / "resources").mkdir(parents=True, exist_ok=True)
        self.engine = SandboxEngine(data_root=self.root)
        self.lr = LocalResourceLifecycleService(data_root=self.root, sandbox_engine=self.engine)
        self.mgr = ToolSandboxSessionManager()

    def tearDown(self):
        self.tmp.cleanup()

    def _deps(self, *, cfg=None, rows=None):
        cfg = cfg if cfg is not None else {}
        rows = rows if rows is not None else {"rows": {}}
        return ToolSandboxRuntimeDeps(
            data_root=self.root,
            sandbox_engine=self.engine,
            local_resource_service=self.lr,
            get_active_config=lambda: cfg,
            get_canonical_rows_payload=lambda: rows,
            get_path=get_path,
        )

    def test_open_stage_promote_resource(self):
        self.engine.save_resource("preloaded", {"resource_id": "preloaded", "note": "seed"})
        decl = {"tool_id": "t1", "required_resources": [{"resource_id": "preloaded", "required": True}]}
        sess = self.mgr.open_session(self._deps(), tool_key="t1", declaration=decl)  # type: ignore[arg-type]
        self.assertFalse(sess.errors)
        sess.stage_resource("preloaded", {"resource_id": "preloaded", "note": "updated"})
        prom = sess.promote(hooks=ToolSandboxPromotionHooks())
        self.assertTrue(prom.get("ok"))
        reread = self.engine.get_resource("preloaded")
        self.assertFalse(bool(reread.get("missing")))
        self.assertEqual(reread.get("note"), "updated")

    def test_required_resource_missing_records_error(self):
        decl = {"tool_id": "t1", "required_resources": [{"resource_id": "nope", "required": True}]}
        sess = self.mgr.open_session(self._deps(), tool_key="t1", declaration=decl)  # type: ignore[arg-type]
        self.assertTrue(any("nope" in e for e in sess.errors))

    def test_config_coordinate_paths_in_loaded_config_inputs(self):
        decl = {
            "tool_id": "t1",
            "config_coordinate_paths": ["agro.inherited.product_profile_ref"],
        }
        cfg = {"agro": {"inherited": {"product_profile_ref": "8-5-11"}}}
        sess = self.mgr.open_session(self._deps(cfg=cfg), tool_key="t1", declaration=decl)  # type: ignore[arg-type]
        self.assertEqual(sess.loaded_config_inputs.get("agro.inherited.product_profile_ref"), "8-5-11")

    def test_consumes_anthology_datum_ids_load_refs(self):
        rows = {
            "rows": {
                "1-1-1": {
                    "row_id": "1-1-1",
                    "identifier": "1-1-1",
                    "label": "L",
                    "pairs": [{"reference": "2-1-1", "magnitude": "1"}],
                    "reference": "2-1-1",
                    "magnitude": "1",
                }
            }
        }
        decl = {"tool_id": "t1", "consumes_anthology_datum_ids": ["1-1-1"]}
        sess = self.mgr.open_session(self._deps(rows=rows), tool_key="t1", declaration=decl)  # type: ignore[arg-type]
        self.assertIn("1-1-1", sess.loaded_anthology_refs)

    def test_anthology_promote_invokes_hook_with_override(self):
        rows = {
            "rows": {
                "1-1-1": {
                    "row_id": "1-1-1",
                    "identifier": "1-1-1",
                    "label": "L",
                    "pairs": [{"reference": "2-1-1", "magnitude": "1"}],
                    "reference": "2-1-1",
                    "magnitude": "1",
                }
            }
        }
        decl = {"tool_id": "t1", "consumes_anthology_datum_ids": ["1-1-1"]}
        sess = self.mgr.open_session(self._deps(rows=rows), tool_key="t1", declaration=decl)  # type: ignore[arg-type]
        updated = dict(sess.working_anthology_rows["1-1-1"])
        updated["label"] = "L2"
        sess.stage_anthology_row("1-1-1", updated)
        called: list[tuple[str, str]] = []

        def hook(did: str, row: dict):
            called.append((did, str(row.get("label") or "")))
            return {"ok": True, "errors": [], "warnings": []}

        prom = sess.promote(
            hooks=ToolSandboxPromotionHooks(update_anthology_row=hook),
            rule_write_override=True,
            rule_write_override_reason="unit test",
        )
        self.assertTrue(prom.get("ok"))
        self.assertEqual(called[0][1], "L2")

    def test_agro_declaration_tool_id_matches(self):
        decl = dict(AGRO_ERP_SANDBOX_DECLARATION)
        sess = self.mgr.open_session(self._deps(), tool_key="agro_erp", declaration=decl)  # type: ignore[arg-type]
        self.assertEqual(sess.tool_key, "agro_erp")
        self.assertFalse(sess.errors)


@unittest.skipUnless(HAS_FLASK, "flask is not installed in host python")
class ToolSandboxSessionRouteTests(unittest.TestCase):
    def setUp(self):
        register_data_routes = _load_register_data_routes()
        self._tmpdir = tempfile.TemporaryDirectory()
        root = Path(self._tmpdir.name)
        (root / "sandbox" / "resources").mkdir(parents=True, exist_ok=True)
        self.app = Flask(__name__)
        register_data_routes(
            self.app,
            workspace=_WorkspaceStub(data_dir=str(root)),
            anthology_payload_provider=lambda: {},
            active_config_provider=lambda: {"agro": {"inherited": {"product_profile_ref": "8-5-11"}}},
            active_config_saver=lambda payload: True,
            msn_id_provider=lambda: "9-9-9",
            include_home_redirect=False,
            include_legacy_shims=False,
        )
        self.client = self.app.test_client()
        self.root = root

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_tool_session_open_get_stage_promote_close(self):
        op = self.client.post("/portal/api/data/sandbox/tool_session/open", json={"tool_key": "agro_erp"})
        self.assertEqual(op.status_code, 200, op.get_data(as_text=True))
        body = op.get_json() or {}
        sid = str(body.get("session_id") or "")
        self.assertTrue(sid)
        self.assertIn("agro.inherited.product_profile_ref", (body.get("loaded_config_inputs") or {}))

        g = self.client.get(f"/portal/api/data/sandbox/tool_session/{sid}")
        self.assertEqual(g.status_code, 200)

        st = self.client.post(
            f"/portal/api/data/sandbox/tool_session/{sid}/stage",
            json={"resources": {"plot.x": {"resource_id": "plot.x", "resource_kind": "plot_plan"}}},
        )
        self.assertEqual(st.status_code, 200)

        pr = self.client.post(f"/portal/api/data/sandbox/tool_session/{sid}/promote", json={})
        self.assertEqual(pr.status_code, 200)
        prom = pr.get_json() or {}
        self.assertTrue(prom.get("ok"))

        cl = self.client.delete(f"/portal/api/data/sandbox/tool_session/{sid}")
        self.assertEqual(cl.status_code, 200)
        self.assertTrue((cl.get_json() or {}).get("ok"))


if __name__ == "__main__":
    unittest.main()
